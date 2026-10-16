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

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"


def cycle_dirs(review: Path) -> list[tuple[int, Path]]:
    out = []
    for d in sorted(review.iterdir()) if review.is_dir() else []:
        m = re.fullmatch(r"cycle-(\d{2})", d.name)
        if m and d.is_dir():
            out.append((int(m.group(1)), d))
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

        The limit of that second rule, stated rather than glossed: it applies
        only where some cycle directory exists to establish what the plausible
        range is. With none at all, horizon is None and every cycle number is
        allowed, because there is no evidence about which are real. In a live
        run freeze creates the directory before anything is recorded against the
        cycle, so the rule is in force whenever it can be.
        """
        if cycle in self.invalid:
            return False
        return self.horizon is None or cycle <= self.horizon

    def why_not(self, cycle: int) -> str:
        if cycle in self.invalid:
            return self.invalid[cycle]
        if self.horizon is not None and cycle > self.horizon:
            return (f"cycle {cycle:02d} does not exist; the highest cycle that "
                    f"can carry an event is {self.horizon:02d}")
        return ""


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
    state: str | None = None
    accepted = False
    for e in history:
        c = e["cycle"]
        if upto is not None and c not in upto:
            continue
        if not proj.authorizes(c):
            continue
        ev = e.get("event")
        if ev not in KNOWN_EVENTS:
            # Refusing rather than ignoring. A new event type that replay does
            # not know would otherwise pass through as a no-op, and the state it
            # was supposed to produce would silently not happen.
            raise UnknownEvent(
                f"no transition defined for event {ev!r} in cycle {c:02d}. "
                f"Known events: {', '.join(KNOWN_EVENTS)}.")
        if ev == "RAISED":
            state, accepted = OPEN, False
        elif ev == "ACCEPT":
            if state == OPEN:
                accepted = True
        elif ev == "REJECT_WITH_REASON":
            if state == OPEN:
                state = DISPUTED
        elif ev == "DEMONSTRATED":
            if state == OPEN and accepted:
                state = RESOLVED
        elif ev == "REOPENED":
            if state == RESOLVED:
                state, accepted = OPEN, False
    return state


def skipped_events(history: list[dict], proj: Projection) -> list[str]:
    """Events that carry authority but whose prerequisite was absent.

    Distinct from events disregarded for sitting in an invalid cycle. These are
    in a cycle that counts; the move they describe was simply not available from
    the state that actually obtained, usually because something they depended on
    was invalidated.
    """
    out: list[str] = []
    state: str | None = None
    accepted = False
    for e in history:
        c = e["cycle"]
        if not proj.authorizes(c):
            continue
        ev = e.get("event")
        if ev not in KNOWN_EVENTS:
            continue
        if ev == "RAISED":
            state, accepted = OPEN, False
        elif ev == "ACCEPT":
            if state == OPEN:
                accepted = True
            else:
                out.append(f"cycle {c:02d} ACCEPT (finding was "
                           f"{state or 'unraised'}, not OPEN)")
        elif ev == "REJECT_WITH_REASON":
            if state == OPEN:
                state = DISPUTED
            else:
                out.append(f"cycle {c:02d} REJECT_WITH_REASON (finding was "
                           f"{state or 'unraised'}, not OPEN)")
        elif ev == "DEMONSTRATED":
            if state == OPEN and accepted:
                state = RESOLVED
            else:
                why = "no ACCEPT in force" if state == OPEN else \
                    f"finding was {state or 'unraised'}, not OPEN"
                out.append(f"cycle {c:02d} DEMONSTRATED ({why})")
        elif ev == "REOPENED":
            if state == RESOLVED:
                state, accepted = OPEN, False
            else:
                out.append(f"cycle {c:02d} REOPENED (finding was "
                           f"{state or 'unraised'}, not RESOLVED)")
    return out


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
    """
    state: str | None = None
    accepted = False
    found = None
    for e in history:
        c = e["cycle"]
        if not proj.authorizes(c):
            continue
        ev = e.get("event")
        if ev not in KNOWN_EVENTS:
            continue
        applied = False
        if ev == "RAISED":
            state, accepted, applied = OPEN, False, True
        elif ev == "ACCEPT":
            if state == OPEN:
                accepted, applied = True, True
        elif ev == "REJECT_WITH_REASON":
            if state == OPEN:
                state, applied = DISPUTED, True
        elif ev == "DEMONSTRATED":
            if state == OPEN and accepted:
                state, applied = RESOLVED, True
        elif ev == "REOPENED":
            if state == RESOLVED:
                state, accepted, applied = OPEN, False, True
        if applied and ev == event:
            found = e
    return found
