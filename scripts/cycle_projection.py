#!/usr/bin/env python3
"""What counts as a cycle, decided once and imported by everyone who asks.

B01-F11: "The ledger authorizes transitions from its unfiltered stored state and
history, while the controller filters events by valid cycles." Decision G was
implemented in `loop_state.py` alone, so the two components disagreed about what
a cycle is, and the disagreement was exploitable in both directions:

  * a DEMONSTRATED recorded in an invalid cycle left the ledger permanently
    RESOLVED, so a later valid resolution was refused while the controller still
    counted the finding OPEN. The finding could never be closed.
  * an ACCEPT recorded in an invalid cycle satisfied the ledger's precondition
    for `resolve`, so an invalid acceptance could authorize a closure the
    controller then counted as real.

Neither is fixable in one component. Filtering harder in the controller does not
stop the ledger from refusing; filtering harder in the ledger does not stop it
from authorizing. So the projection lives here, and both import it.

Three states, not two
--------------------
The distinction that makes this workable is between a cycle that has been judged
and failed and one that has not been judged yet.

    VALID     the directory exists and passes the MC-2 gate
    INVALID   the directory exists and fails it
    UNJUDGED  no directory yet

Only INVALID strips authority. An UNJUDGED cycle is the one being assembled
right now: findings get raised in it before its evidence is complete, and a
ledger that refused to record them would be unusable. Its events carry authority
provisionally, and lose it the moment the cycle is judged and fails, because
authority is recomputed on every read rather than frozen at write time.

Loop calculation is stricter and uses VALID only, per §2 and §3: an invalid cycle
"cannot consume one of the four valid review cycles", and an unjudged one has no
evidence to measure.

Nothing is ever deleted. Invalid events stay in the history as evidence of what
was recorded and when; they simply stop authorizing transitions and stop
blocking them.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_pins  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"

# §2's four-valid-cycle maximum, held once. The runner and the controller each
# carried their own `4`, which is B02-F03's defect class: the schema and the
# ledger each had their own idea of a valid identifier and quietly disagreed.
# Nothing had gone wrong with these two yet, and that is the only reason it
# looked harmless.
#
# It belongs beside the projection because the budget is counted in valid
# cycles, and this file is what decides which cycles those are. Both components
# import the count and the rule that counts it from the same place.
MAX_VALID_CYCLES = 4


def cycle_dirs(review: Path) -> list[tuple[int, Path]]:
    # C02-F05. The grammar is run_pins', not a second copy written here. This
    # one and MC-2 check 7 disagreed, and the checker was the looser of the two,
    # so a directory could be an accepted cycle to conformance and not a cycle
    # at all to the budget that counts them.
    out = []
    for d in sorted(review.iterdir()) if review.is_dir() else []:
        n = run_pins.cycle_dir_number(d.name)
        if n is not None and d.is_dir():
            out.append((n, d))
    return sorted(out)


def gate(cycle_dir: Path) -> tuple[bool, str]:
    """Run the MC-2 conformance gate. Never read a recorded verdict.

    A loop controller that accepted an asserted PASS would let an invalid cycle
    consume the budget, which is the exact defect the "MAX 4 counts valid cycles"
    note exists to prevent.
    """
    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle_dir)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        return False, "checker could not run"
    reason = ""
    if r.returncode != 0:
        fails = [l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l]
        reason = fails[0] if fails else "MC-2 FAIL"
    return r.returncode == 0, reason


class Projection:
    """Which cycles exist, which passed, and which events may authorize.

    `valid`   ordered cycle numbers that exist and pass MC-2. Loop arithmetic.
    `invalid` cycle number -> why it failed. Evidence only.
    `horizon` the highest cycle an event may name: the last one that exists,
              plus the one being assembled.
    """

    def __init__(self, valid: list[int], invalid: dict[int, str],
                 horizon: int | None = None):
        self.valid = valid
        self.invalid = invalid
        known = list(valid) + list(invalid)
        # None means "no basis to judge", not "zero". With no cycle directories
        # at all there is nothing to say which cycle numbers are plausible, and
        # the ledger legitimately runs before any exist. Defaulting to 1 there
        # made every event above cycle 1 unauthorized, which is a different bug
        # wearing this one's clothes.
        self.horizon = horizon if horizon is not None else (
            max(known) + 1 if known else None)

    def authorizes(self, cycle: int) -> bool:
        """May an event recorded in this cycle authorize a state transition?

        Two disqualifiers, not one.

        Judged-and-failed is the first: an invalid cycle cannot support an
        authoritative anything.

        The second is B01-F11's other half, which Codex found in cycle 02: this
        returned True for every cycle number absent from the invalid map,
        including cycles that do not exist. An event naming cycle 99 authorized
        transitions the loop controller would never count, because its
        arithmetic runs over cycles that exist. Beyond the horizon there is no
        cycle to have recorded anything.

        B01-F11 again, and the part cycle 03 found still open. The horizon rule
        above admitted every number up to max(known)+1, so an INTERIOR gap
        authorized: Projection([1, 3], {}) has horizon 4 and returned True for
        cycle 02, which never existed. Codex recorded RAISED in 01, ACCEPT in a
        nonexistent 02, and DEMONSTRATED in 03; the ledger reported RESOLVED
        while the controller, which counts only cycles that exist, kept the
        finding OPEN and returned STALLED. Two components disagreeing about one
        finding is the whole of B01-F11.

        What is closed here is the INTERIOR gap, which is what Codex
        reproduced. A cycle number below the frontier that is in neither the
        valid nor the invalid set has no evidence directory at all; it is not a
        cycle awaiting judgement, it is a cycle that never happened.

        What is deliberately NOT changed is the frontier, and the case where no
        cycle exists yet. Alex Zamurko's decision H:

            cycle_projection distinguishes three states, not two: VALID,
            INVALID and UNJUDGED. Only INVALID strips authority. A cycle with
            no directory yet is the one being assembled, and a ledger that
            refused to record into it would be unusable.

        Making UNJUDGED strip authority outright would close the rest of what
        Codex asked for and would contradict that decision, so it is his to
        make rather than one to take here while repairing a finding. The
        remaining exposure is stated in the cycle-04 prompt rather than left to
        be rediscovered: an event in the cycle currently being assembled carries
        authority before that cycle has passed MC-2.
        """
        if cycle in self.invalid:
            return False
        if cycle in self.valid:
            return True
        # Neither judged nor passed: no directory exists for this cycle.
        # Decision H keeps the frontier, and the no-evidence case, permissive.
        if self.horizon is None:
            return True
        return cycle == self.horizon

    def why_not(self, cycle: int) -> str:
        if cycle in self.invalid:
            return self.invalid[cycle]
        if cycle in self.valid:
            return ""
        if self.horizon is not None and cycle > self.horizon:
            return (f"cycle {cycle:02d} does not exist; the highest cycle that "
                    f"can carry an event is {self.horizon:02d}")
        if self.valid or self.invalid:
            return (f"cycle {cycle:02d} has no evidence directory, so nothing "
                    f"recorded against it has passed MC-2")
        return ("no cycle has passed MC-2 yet, so no event carries authority "
                "in this review")


def project(review: Path) -> Projection:
    valid: list[int] = []
    invalid: dict[int, str] = {}
    for num, d in cycle_dirs(review):
        ok, why = gate(d)
        if ok:
            valid.append(num)
        else:
            invalid[num] = why or "MC-2 FAIL"
    return Projection(valid, invalid)


OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"

# What each event requires to have happened, and what it produces. §5's
# transitions, written as data so that replay cannot quietly disagree with the
# ledger about which moves are legal.
#
#   RAISED               -> OPEN                      (no prerequisite)
#   ACCEPT               requires OPEN                (state unchanged; arms
#                                                      the ACCEPT that resolve
#                                                      needs)
#   REJECT_WITH_REASON   requires OPEN   -> DISPUTED
#   DEMONSTRATED         requires OPEN and an armed ACCEPT  -> RESOLVED
#   REOPENED             requires RESOLVED            -> OPEN, disarms
KNOWN_EVENTS = ("RAISED", "ACCEPT", "REJECT_WITH_REASON", "DEMONSTRATED",
                "REOPENED")


class UnknownEvent(Exception):
    """History contains an event replay has no transition for. Not skippable."""


def _before_raise(raised_at: int, what: str) -> str:
    """C02-F02, raised again by cycle 03. One wording, used by both guards.

    A disposition answers a finding. One dated before the finding was raised
    answers nothing that existed yet, and the ledger commands refused it from
    the start while replay accepted it, so a history illegal to write was legal
    to read.
    """
    return (f"{what} in a cycle before the finding was raised in cycle "
            f"{raised_at:02d}; a disposition cannot answer a finding that did "
            f"not yet exist")


class Walk:
    """One pass over a finding's history, and the only place transitions live.

    Three questions, one evaluator. `replay` wants the state it ends in,
    `last_authorized` wants which events are still in force, and
    `skipped_events` wants which authorized events did not apply. Those were
    three separate loops until 26 September, each with its own copy of the
    transition rules, and they disagreed.

    C01-F01, which is B01-F11 surviving in the functions that determine the
    authoritative state. The reopening guard had been added to
    `last_authorized` alone, so a backdated acceptance was refused as the
    prerequisite for a NEW resolve command while state reconstruction from an
    EXISTING history honoured the same acceptance. Codex supplied the history
    and got three answers from one record:

        RAISED(1) ACCEPT(1) DEMONSTRATED(2) REOPENED(3) ACCEPT(2) DEMONSTRATED(4)

        replay                  RESOLVED
        last_authorized ACCEPT  None
        skipped_events          []

    A ledger and a controller saying RESOLVED while the prerequisite lookup
    says there is no acceptance is not a disagreement anyone can act on, and
    the diagnostic that exists to explain such a gap reported nothing skipped.

    The reviewer asked for one shared transition evaluator so the three
    implementations cannot disagree. This is it. Adding a rule here reaches
    all three by construction, which is the property that was missing.
    """

    __slots__ = ("state", "accepted", "reopened_at", "raised_at", "accepted_at",
                 "demonstrated_at", "live", "skipped")

    def __init__(self) -> None:
        self.state: str | None = None
        self.accepted = False
        # The cycle of the most recent reopening still in force. An ACCEPT
        # dated before it answers the repair that reopening already spent.
        self.reopened_at: int | None = None
        # C02-F02. The cycles of the acceptance and the demonstration in force.
        # §5 resolves a finding once the repair is demonstrated in the NEXT
        # review target, and a recurrence is observed later than the resolution
        # it undoes. Both rules existed, in the write commands, and not here, so
        # replay honoured histories the commands would have refused to write.
        # C02-F02, raised again by cycle 03. The cycle the finding was raised
        # in. Codex: "cycle_projection does not retain the raising cycle, and
        # Walk.apply does not enforce this chronological restriction... With
        # cycles 1 to 4 valid, the stored history RAISED(3), ACCEPT(1),
        # DEMONSTRATED(4) reconstructs RESOLVED."
        #
        # The command path refused that acceptance, because it predates the
        # finding it answers. Replay did not, so the same history was illegal to
        # write and legal to read, which is the whole shape of this finding and
        # the third time it has been found in a different rule.
        self.raised_at: int | None = None
        self.accepted_at: int | None = None
        self.demonstrated_at: int | None = None
        # The most recent event of each kind whose effect STILL obtains,
        # rather than the most recent one that was applied at the time.
        self.live: dict[str, dict] = {}
        # Authorized events whose move was not available from the state that
        # actually obtained. Distinct from events disregarded for sitting in
        # an invalid cycle: these are in a cycle that counts.
        self.skipped: list[str] = []

    def _not_open(self) -> str:
        return f"finding was {self.state or 'unraised'}, not OPEN"

    def apply(self, ev: str, c: int) -> tuple[bool, str | None]:
        """Apply one event. Returns (applied, why not).

        Every transition rule in this system is in this method. If a rule is
        added anywhere else, the divergence C01-F01 describes is back.
        """
        if ev == "RAISED":
            self.state, self.accepted, self.reopened_at = OPEN, False, None
            self.raised_at = c
            self.accepted_at = self.demonstrated_at = None
            # A finding starting over carries nothing forward.
            self.live.clear()
            return True, None
        if ev == "ACCEPT":
            if self.state != OPEN:
                return False, self._not_open()
            if self.reopened_at is not None and c < self.reopened_at:
                # Insertion order says when a thing was written down. The
                # cycle says which review it belongs to. A disposition has to
                # answer the transition it follows, and one dated before the
                # reopening answers a different question: it was a response to
                # the first repair, which the reopening spent.
                return False, (f"dated before the cycle {self.reopened_at:02d} "
                               f"reopening it would have to answer")
            if self.raised_at is not None and c < self.raised_at:
                return False, _before_raise(self.raised_at, "accepted")
            self.accepted, self.accepted_at = True, c
            return True, None
        if ev == "REJECT_WITH_REASON":
            if self.state != OPEN:
                return False, self._not_open()
            # C02-F02. The same guard ACCEPT has, for the same reason. A
            # disposition answers the transition it follows, and §5 gives a
            # finding two of them, so a rejection dated before the reopening
            # answers the repair that reopening undid just as an acceptance
            # would. cmd_respond refused both; only one was refused here.
            if self.reopened_at is not None and c < self.reopened_at:
                return False, (f"dated before the cycle {self.reopened_at:02d} "
                               f"reopening it would have to answer")
            if self.raised_at is not None and c < self.raised_at:
                return False, _before_raise(self.raised_at, "rejected")
            self.state = DISPUTED
            return True, None
        if ev == "DEMONSTRATED":
            if self.state != OPEN:
                return False, self._not_open()
            if not self.accepted:
                return False, "no ACCEPT in force"
            # C02-F02. §5: RESOLVED "once the repair is demonstrated in the next
            # review target", so the demonstration belongs to a later cycle than
            # the acceptance. cmd_resolve refused a same-cycle demonstration and
            # replay accepted one, which is a resolution the protocol would
            # never have allowed to be written being honoured once it exists.
            if self.accepted_at is not None and c <= self.accepted_at:
                return False, (f"accepted in cycle {self.accepted_at:02d}; §5 "
                               f"demonstrates the repair in a LATER cycle")
            self.state, self.demonstrated_at = RESOLVED, c
            return True, None
        if ev == "REOPENED":
            if self.state != RESOLVED:
                return False, (f"finding was {self.state or 'unraised'}, "
                               f"not RESOLVED")
            # C02-F02. A recurrence is observed in a later cycle than the
            # resolution it undoes. cmd_reopen refused otherwise; replay did not.
            if self.demonstrated_at is not None and c <= self.demonstrated_at:
                return False, (f"resolved in cycle {self.demonstrated_at:02d}; "
                               f"a recurrence is observed LATER than the "
                               f"resolution it undoes")
            self.state, self.accepted, self.reopened_at = OPEN, False, c
            self.accepted_at = self.demonstrated_at = None
            # The acceptance and the demonstration it produced are both spent.
            # Their events remain in the history and in `show`; they are simply
            # no longer the prerequisite for anything.
            self.live.pop("ACCEPT", None)
            self.live.pop("DEMONSTRATED", None)
            return True, None
        raise UnknownEvent(f"no transition defined for event {ev!r}")


def would_apply(f: dict, proj: Projection, event: str,
                cycle: int) -> tuple[bool, str | None]:
    """Is `event` at `cycle` available from this finding's history?

    C02-F02. The write commands ask this instead of testing the ordering rules
    themselves. Each of them used to carry its own copy while the evaluator
    carried none, so a history the commands would have refused to write was
    honoured once it existed by any other route. Asking here means admission and
    replay cannot disagree, because there is only one answer to give.

    The command still writes the refusal, because it knows what the operator was
    trying to do and this does not. What it no longer does is decide.
    """
    return walk(f.get("history", []), proj).apply(event, cycle)


def walk(history: list[dict], proj: Projection,
         upto: set[int] | None = None) -> Walk:
    """Replay a finding's authorized history once.

    `upto` restricts to a set of cycle numbers, which is how the controller
    asks for the state at an earlier cycle boundary. The ledger passes None and
    means "as things stand".

    An unknown event refuses here rather than being ignored, and refuses for
    all three callers rather than only for `replay`. That asymmetry was its own
    instance of the same defect: `replay` would have raised while
    `last_authorized` skipped past and returned a stale prerequisite, so a
    resolve could proceed on an authority the state rebuild would not grant.
    """
    w = Walk()
    for e in history:
        c = e["cycle"]
        if upto is not None and c not in upto:
            continue
        if not proj.authorizes(c):
            continue
        ev = e.get("event")
        if ev not in KNOWN_EVENTS:
            # A new event type that replay does not know would otherwise pass
            # through as a no-op, and the state it was supposed to produce
            # would silently not happen.
            raise UnknownEvent(
                f"no transition defined for event {ev!r} in cycle {c:02d}. "
                f"Known events: {', '.join(KNOWN_EVENTS)}.")
        applied, why = w.apply(ev, c)
        if applied:
            w.live[ev] = e
        elif why:
            w.skipped.append(f"cycle {c:02d} {ev} ({why})")
    return w


def replay(history: list[dict], proj: Projection,
           upto: set[int] | None = None) -> str | None:
    """The state a finding reached, by replaying legal transitions.

    B01-F11, and the part cycle 02 found still broken. The first repair filtered
    which events were MEMBERS of the projection and then did `state =
    e["state"]` — it copied the state the event recorded. So a DEMONSTRATED in a
    valid cycle still produced RESOLVED even when the ACCEPT it depended on had
    been skipped for sitting in an invalid cycle. Codex reproduced it: RAISED in
    valid 01, ACCEPT in then-valid 02, DEMONSTRATED in valid 03; invalidate 02
    afterwards and `show` marked the ACCEPT as having no authority while the
    finding stayed RESOLVED and the controller returned CONVERGED.

    Alex Zamurko, 10 September: "rebuild finding state by replaying only valid
    events in chronological order, rather than copying the last retained state
    after filtering. Why it works: a later RESOLVE cannot survive if its
    required earlier ACCEPT was invalid. State becomes a consequence of valid
    history, not of a cached result."

    So each event is applied only if its prerequisite holds in the state built
    so far. An event whose prerequisite is absent is not an error in the record
    — it is a transition that never had authority — and it leaves the state
    untouched. `skipped_events` reports them so a refusal can say which.

    `upto` additionally restricts to a set of cycle numbers, which is how the
    controller asks for the state at an earlier cycle boundary. The ledger passes
    None and means "as things stand".
    """
    return walk(history, proj, upto).state


def skipped_events(history: list[dict], proj: Projection) -> list[str]:
    """Events that carry authority but whose prerequisite was absent.

    Distinct from events disregarded for sitting in an invalid cycle. These are
    in a cycle that counts; the move they describe was simply not available from
    the state that actually obtained, usually because something they depended on
    was invalidated.

    This reported nothing for the backdated acceptance in C01-F01, because it
    carried its own copy of the rules and that copy had no reopening guard. A
    diagnostic that exists to explain why a state is what it is has to be
    reading the same rules that produced the state.
    """
    return walk(history, proj).skipped


def last_authorized(history: list[dict], event: str,
                    proj: Projection) -> dict | None:
    """The most recent event of this kind that is in force.

    An ACCEPT in an invalid cycle is still in the history and still visible in
    `show`. It just cannot be the ACCEPT that `resolve` requires.

    B01-F11: "in force" is stronger than "in a cycle that counts". An ACCEPT
    recorded against a finding that was already DISPUTED never took effect, so
    it cannot be the prerequisite for anything later either. This replays
    alongside the state so that only events the replay actually applied are
    returned — the same rule `replay` uses, rather than a second opinion about
    which events matter.

    Cycles 03 and 04 of BOOTSTRAP-001 each found a way for this to disagree
    with the state: an event undone later still handed back as a prerequisite,
    then an ACCEPT appended after a reopening but carrying an earlier cycle
    number re-arming the finding. Both were repaired here and only here, which
    is what left C01-F01 open. The rules now live in `Walk.apply`, so this
    function cannot hold an opinion the state rebuild does not share.
    """
    return walk(history, proj).live.get(event)
