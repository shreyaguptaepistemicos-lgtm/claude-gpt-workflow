#!/usr/bin/env python3
"""Finding and state ledger.

Tracks every Codex finding through OPEN / RESOLVED / DISPUTED across the cycles
of one review loop, with a full audit trail and no illegal transitions.

    python scripts/ledger.py raise   --review <dir> --cycle 1 --id C01-F01 \
        --class "UNTESTED RULE" --requirement R-B7
    python scripts/ledger.py respond --review <dir> --cycle 1 --id C01-F01 \
        --disposition ACCEPT --note "..."
    python scripts/ledger.py resolve --review <dir> --cycle 2 --id C01-F01 \
        --evidence "repaired in 02-PLAN.md §4"
    python scripts/ledger.py show    --review <dir> [--cycle N]

Exit 0 = done, 1 = refused, 2 = could not run.

The three states are the protocol's, §6: OPEN, RESOLVED, DISPUTED. There is no
fourth.

Why ACCEPT does not resolve
---------------------------
§5: on ACCEPT the finding's state becomes RESOLVED "once the repair is
demonstrated in the next review target". So accepting records a disposition and
leaves the state OPEN. Only a later cycle can move it to RESOLVED, and this
ledger refuses to do it in the same cycle as the ACCEPT.

That is not pedantry. If ACCEPT alone resolved a finding, the implementing agent
would close its own findings by asserting it intended to fix them, which is the
authority inversion MC-1 exists to prevent.

Who declares a repair demonstrated
----------------------------------
The protocol does not say mechanically, and this ledger does not invent an
answer. `resolve` requires an explicit evidence string and refuses without a
prior ACCEPT, so the assertion is recorded and attributable rather than implied.
See DECISIONS below.

DISPUTED is terminal here
-------------------------
§5 says a dispute "requires human adjudication" and §7.1 puts that at the human
gate. Nothing in the automated loop may move a finding out of DISPUTED, so this
ledger refuses. Adjudication belongs to the approval record, not here.

Invalid cycles do not authorize and do not block
------------------------------------------------
B01-F11. Transition authority is computed through `cycle_projection`, the same
module the loop controller uses, rather than from the stored state. An event
recorded in a cycle that fails MC-2 stays in the history as evidence and is
printed by `show`, but it cannot satisfy a precondition and it cannot stand in
the way of a valid transition. Before this, an ACCEPT in an invalid cycle could
authorize a closure and a DEMONSTRATED in an invalid cycle could prevent one
forever.

The stored `state` field is a cache of that projection, rewritten on every
command. Nothing reads it to decide anything.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycle_projection  # noqa: E402

# B02-F03. This was `\A[A-Z]?(\d{2})-F(\d{2,3})\Z` — one optional letter, where
# the schema's FINDING_ID_GRAMMAR allows up to two. So `AB02-F01` parsed cleanly
# and the ledger then refused it, and a finding that was valid at capture could
# not be recorded unchanged. A second grammar, inside the component whose
# purpose is to stop there being more than one.
#
# Alex Zamurko, 9 September: "Prompt, parser, and ledger must not independently
# impose different grammars." And 10 September: "Have the ledger consume the
# canonical grammar and preserve every valid identifier. Keep any origin-cycle
# validation separate from prefix-length assumptions."
#
# Which is why the local copy existed at all: the ledger needed a capture group
# for the cycle digits, and the canonical pattern has none. The two jobs are now
# separate. Validity is the schema's question; the cycle digits are found by
# their position relative to the -F, which holds for any prefix length.
CYCLE_DIGITS = re.compile(r"(\d{2})-F\d{2,3}\Z")

# §4, and the vocabulary "remains unchanged across cycles so that finding sets
# remain comparable". Anything outside it is refused rather than recorded.
CLASSES = (
    "MISSING REQUIREMENT",
    "WRONG OWNERSHIP",
    "NONDETERMINISTIC WHERE D POSSIBLE",
    "SEMANTIC STEP TOO BROAD",
    "UNTESTED RULE",
    "CONTRADICTORY IMPLEMENTATION MAPPING",
)

# Kept out of CLASSES deliberately, and refused by name rather than falling
# through the generic "not one of the six" message, because the reason it is
# refused is specific and worth printing.
#
# Alex Zamurko, 8 September 2026: OUT OF VOCABULARY is kept in the review prompts
# "only as a non-finding, human-visible diagnostic ... no Finding ID, must not be
# written to findings.json, must not enter OPEN / RESOLVED / DISPUTED, and must
# not affect loop-state calculation."
#
# The prompts say so; this refuses it, which is the difference between a rule and
# a request. An OUT OF VOCABULARY item admitted here would be a seventh class in
# everything but name, and would silently gain the power to block convergence.
NON_FINDING = "OUT OF VOCABULARY"

OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"
STATES = (OPEN, RESOLVED, DISPUTED)


class Refused(Exception):
    """A transition the protocol does not permit. Exit 1, change nothing."""


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_lf(p: Path, text: str) -> None:
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def ledger_path(review: Path) -> Path:
    """State history, deliberately not called findings.json.

    Alex Zamurko, issue 4: "Separate authoritative findings from response/state
    history." They were both findings.json, at different levels — the schema
    documented a per-cycle file written by the runner, and this wrote a
    review-level one. Two files with one name is how a reader ends up believing
    the wrong one is authoritative.

    cycle-NN/findings.json  what the reviewer found, written by the runner
    ledger.json             what happened to each finding since, written here
    """
    return review / "ledger.json"


def load(review: Path) -> dict:
    p = ledger_path(review)
    if not p.is_file():
        return {"review": review.name, "findings": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"findings.json is not valid JSON: {e}")


def save(review: Path, data: dict) -> None:
    review.mkdir(parents=True, exist_ok=True)
    write_lf(ledger_path(review), json.dumps(data, indent=2, sort_keys=True) + "\n")


def check_id(fid: str, cycle: int) -> None:
    # Validity from the one authoritative declaration, read at the point of use
    # rather than copied. A copy is what B02-F03 was.
    try:
        import findings_format
        grammar = findings_format.canonical_id_grammar()
    except Exception as e:
        raise Refused(
            f"the canonical Finding ID grammar cannot be read, so no identifier "
            f"can be judged: {e}\n"
            "  Refusing rather than falling back to a local pattern. A fallback "
            "grammar is a\n  second grammar, which is the defect.")
    if not grammar.fullmatch(fid):
        raise Refused(f"finding id {fid!r} does not match the canonical grammar "
                      f"{grammar.pattern}\n"
                      "  Declared in specs/evidence-schema-v1.0.md as "
                      "FINDING_ID_GRAMMAR.")
    m = CYCLE_DIGITS.search(fid)
    if not m:
        raise Refused(
            f"{fid} matches the canonical grammar but carries no readable cycle "
            "digits.\n  The grammar and the cycle rule disagree, which is a "
            "defect in one of them.")
    if int(m.group(1)) != cycle:
        raise Refused(f"{fid} declares cycle {int(m.group(1))} but was raised in "
                      f"cycle {cycle}. The identifier is persistent and carries the "
                      "cycle it was raised in; a mismatch makes the history unreadable.")


def get(data: dict, fid: str) -> dict:
    f = data["findings"].get(fid)
    if f is None:
        raise Refused(f"no such finding: {fid}. Raise it before responding to it.")
    return f


def check_not_before_raise(f: dict, fid: str, cycle: int, event: str) -> None:
    """B01-F12. No event may predate the cycle that raised the finding.

    Alex Zamurko, 10 September: "require every ACCEPT, RESOLVE, or DISPUTE event
    to occur in the raising cycle or a later valid cycle. Reject any
    earlier-dated event. Why it works: the ledger cannot contain impossible
    causal history."

    Nothing checked this. A finding raised in cycle 3 could be accepted in cycle
    1 and resolved in cycle 2, and the history would read as a decision taken
    about something that had not been found yet. §6 then measures those sets at
    boundaries where the finding did not exist.

    Ordering only. Whether the cycle is VALID is the projection's question, and
    asking it here would put a second opinion on validity in the ledger, which
    is the divergence B01-F11 was about.
    """
    raised = int(f.get("cycle_raised", cycle))
    if cycle < raised:
        raise Refused(
            f"{fid} was raised in cycle {raised:02d} and cannot be "
            f"{event}ed in cycle {cycle:02d}.\n"
            "  An event earlier than the finding it acts on is not a late "
            "record, it is a\n  history that could not have happened. Record it "
            "in the raising cycle or later.")


def last_event(f: dict, event: str) -> dict | None:
    """Unfiltered. Kept for reporting; never for authority. See `authorized`."""
    for e in reversed(f["history"]):
        if e["event"] == event:
            return e
    return None


# ------------------------------------------------- the projection (B01-F11)

def projection(review: Path) -> cycle_projection.Projection:
    return cycle_projection.project(review)


def effective_state(f: dict, proj: cycle_projection.Projection) -> str:
    """The state this finding is actually in, ignoring events without authority.

    This replaces every former read of f["state"]. The difference only shows up
    once a cycle has been judged and failed, which is precisely the case B01-F11
    is about.
    """
    return cycle_projection.replay(f["history"], proj) or OPEN


def authorized(f: dict, event: str,
               proj: cycle_projection.Projection) -> dict | None:
    return cycle_projection.last_authorized(f["history"], event, proj)


def note_ignored(f: dict, proj: cycle_projection.Projection) -> str:
    """The events being disregarded, so a refusal is legible.

    Without this, a resolve that is refused for want of an ACCEPT looks wrong to
    an operator who can see an ACCEPT sitting in the history.

    Two separate reasons an event can fail to count, and they need different
    remedies, so they are reported separately (B01-F11):

      * it sits in a cycle that fails MC-2, or names a cycle that does not
        exist. Repair the evidence and it counts again.
      * it carries authority, but the move it describes was not available from
        the state that actually obtained — usually because a prerequisite was
        invalidated. Repairing that cycle is what brings it back.
    """
    parts = []
    ignored = [f"cycle {e['cycle']:02d} {e.get('event')}"
               for e in f["history"] if not proj.authorizes(e["cycle"])]
    if ignored:
        parts.append(
            "\n  Disregarded, recorded in a cycle that does not count: "
            + "; ".join(ignored)
            + "\n  They remain in the history as evidence. Repair the cycle's "
            "evidence and they\n  count again.")
    skipped = cycle_projection.skipped_events(f["history"], proj)
    if skipped:
        parts.append(
            "\n  In a cycle that counts, but never took effect: "
            + "; ".join(skipped)
            + "\n  The transition was not available from the state that "
            "obtained at the time.")
    return "".join(parts)


def restate(f: dict, proj: cycle_projection.Projection) -> None:
    f["state"] = effective_state(f, proj)


# ---------------------------------------------------------------- commands

def cmd_raise(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    check_id(a.id, a.cycle)
    if a.id in data["findings"]:
        # B01-F13. The refusal is right; its guidance was not. Telling the
        # operator to create a new finding for a recurrence contradicts V40 and
        # defeats §6's re-raise detection, which needs the identity to persist.
        # Issue 7 gave the recurrence its own transition, so this now points at
        # it instead of instructing a rename.
        raise Refused(
            f"{a.id} already exists, and identifiers are persistent (V40).\n"
            f"  If this is the same underlying finding recurring after it was "
            "resolved, use\n  `reopen`, which keeps the identifier and moves "
            "RESOLVED -> OPEN.\n"
            "  If it is genuinely a different finding, it needs its own "
            "identifier.")
    if a.klass.strip().upper() == NON_FINDING:
        raise Refused(
            f"{NON_FINDING} is not a finding and cannot enter the ledger.\n"
            "  It is a human-visible diagnostic only: no Finding ID, never in\n"
            "  findings.json, never OPEN / RESOLVED / DISPUTED, no effect on\n"
            "  loop state. Ruled by Alex Zamurko, 8 September 2026.\n"
            "  It reaches the human at the review gate, in the raw Codex output.\n"
            "  If the issue must block convergence it has to fit one of the six;\n"
            "  if it genuinely cannot, that mismatch is the thing being reported.")
    if a.klass not in CLASSES:
        raise Refused(f"class must be one of the six in §4, got {a.klass!r}\n  "
                      + "\n  ".join(CLASSES))

    data["findings"][a.id] = {
        "cycle_raised": a.cycle,
        "class": a.klass,
        "requirement_id": a.requirement or "",
        "state": OPEN,
        "history": [{"cycle": a.cycle, "event": "RAISED", "state": OPEN,
                     "at": now(), "note": a.note or ""}],
    }
    save(review, data)
    print(f"{a.id}  RAISED  cycle {a.cycle:02d}  {a.klass}  -> {OPEN}")
    return 0


def cmd_respond(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)
    proj = projection(review)
    state = effective_state(f, proj)
    check_not_before_raise(f, a.id, a.cycle, "respond")

    if state == RESOLVED:
        raise Refused(f"{a.id} is RESOLVED. Responding again is not how a "
                      "recurrence is recorded:\n  use `reopen` with evidence, "
                      "which keeps the identifier and moves\n  RESOLVED -> OPEN "
                      "per §7 of the 9 September ruling.")
    if state == DISPUTED:
        raise Refused(f"{a.id} is DISPUTED and requires human adjudication (§5, §7.1). "
                      "The automated loop does not move findings out of DISPUTED.")

    for e in f["history"]:
        if e["cycle"] == a.cycle and e["event"] in ("ACCEPT", "REJECT_WITH_REASON"):
            raise Refused(f"{a.id} already has a disposition in cycle {a.cycle:02d}: "
                          f"{e['event']}. §5 permits exactly one per finding.")

    if a.disposition == "ACCEPT":
        # State deliberately unchanged. See the module docstring.
        f["history"].append({"cycle": a.cycle, "event": "ACCEPT", "state": OPEN,
                             "at": now(), "note": a.note or ""})
        print(f"{a.id}  ACCEPT  cycle {a.cycle:02d}  -> still {OPEN}")
        print("       §5: RESOLVED only once the repair is demonstrated in the next")
        print("       review target. Use `resolve` from a later cycle.")
    else:
        # §5's REJECT_WITH_REASON block names Reason and Spec evidence as two
        # fields, and they answer different questions: why the reviewer is wrong,
        # and what in the specification says so. One free-text note satisfied the
        # first and let the second go unwritten, which is how a rejection ends up
        # resting on the implementing agent's judgement rather than on the spec.
        # Alex Zamurko, 8 September 2026: "DISPUTE ... requires reason/spec
        # evidence".
        if not (a.note or "").strip():
            raise Refused("REJECT_WITH_REASON requires --note, the Reason of §5. "
                          "A rejection without one is a silent dismissal.")
        if not (a.spec_evidence or "").strip():
            raise Refused(
                "REJECT_WITH_REASON requires --spec-evidence, the Spec evidence "
                "field of §5.\n"
                "  Reason says why you disagree. Spec evidence says what in the "
                "specification\n"
                "  supports you, and it is the half a human adjudicating the "
                "dispute needs.\n"
                "  A rejection resting only on the implementing agent's reading "
                "is the\n  authority inversion MC-1 exists to prevent.")
        f["history"].append({"cycle": a.cycle, "event": "REJECT_WITH_REASON",
                             "state": DISPUTED, "at": now(), "note": a.note,
                             "spec_evidence": a.spec_evidence})
        print(f"{a.id}  REJECT_WITH_REASON  cycle {a.cycle:02d}  -> {DISPUTED}")
        print("       Requires human adjudication at the plan gate.")

    restate(f, proj)
    save(review, data)
    return 0


def cmd_reopen(a: argparse.Namespace) -> int:
    """RESOLVED -> OPEN when the same underlying finding recurs.

    Alex Zamurko, 9 September 2026, issue 7:

        If a previously RESOLVED finding is raised again as the same underlying
        finding, the persistent Finding ID is retained and its state transitions
        RESOLVED -> OPEN. The recurrence is recorded as a reopen event with
        cycle and evidence. No new authoritative finding state is introduced.

    Before this the ledger refused outright, which was wrong in both directions:
    a recurrence either had to be recorded under a new identifier, breaking V40
    and §6's re-raise detection, or not recorded at all. There is still no fourth
    state; the controller sees an ordinary member of OPEN_n.
    """
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)
    proj = projection(review)
    state = effective_state(f, proj)
    check_not_before_raise(f, a.id, a.cycle, "reopen")

    if state != RESOLVED:
        raise Refused(f"{a.id} is {state}, not RESOLVED. Reopening applies "
                      "only to a finding that was resolved and has recurred."
                      + note_ignored(f, proj))
    if not (a.evidence or "").strip():
        raise Refused(
            "--evidence is required. A reopen asserts that the same underlying "
            "finding is\n  present again, and the record has to say what shows "
            "it rather than leaving\n  the claim bare.")

    last = authorized(f, "DEMONSTRATED", proj)
    if last and a.cycle <= last["cycle"]:
        raise Refused(
            f"{a.id} was resolved in cycle {last['cycle']:02d} and cannot "
            f"recur in cycle {a.cycle:02d}.\n  A recurrence is observed in a "
            "later cycle than the resolution it undoes.")

    f["history"].append({"cycle": a.cycle, "event": "REOPENED", "state": OPEN,
                         "at": now(), "note": a.evidence,
                         "prior_state": RESOLVED})
    restate(f, proj)
    save(review, data)
    print(f"{a.id}  REOPENED  cycle {a.cycle:02d}  {RESOLVED} -> {OPEN}")
    print("       The identifier is retained; §6 counts it as an ordinary "
          "member of OPEN_n.")
    return 0


def cmd_resolve(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)
    proj = projection(review)
    state = effective_state(f, proj)
    check_not_before_raise(f, a.id, a.cycle, "resolv")

    if state == RESOLVED:
        raise Refused(f"{a.id} is already RESOLVED.")
    if state == DISPUTED:
        raise Refused(f"{a.id} is DISPUTED. A dispute is resolved by human "
                      "adjudication at the gate, not by demonstrating a repair.")

    acc = authorized(f, "ACCEPT", proj)
    if acc is None:
        raise Refused(f"{a.id} has no ACCEPT. §5 gives RESOLVED only to a finding "
                      "that was accepted and then repaired; a finding cannot become "
                      "resolved without first having been accepted."
                      + note_ignored(f, proj))
    if a.cycle <= acc["cycle"]:
        raise Refused(f"{a.id} was accepted in cycle {acc['cycle']:02d} and cannot be "
                      f"resolved in cycle {a.cycle:02d}. §5 requires the repair to be "
                      "demonstrated in the NEXT review target, so resolution belongs "
                      "to a later cycle than the acceptance.")
    if not (a.evidence or "").strip():
        raise Refused("--evidence is required. The protocol resolves a finding when "
                      "the repair is demonstrated; recording what demonstrates it is "
                      "the difference between a demonstration and an assertion.")

    f["history"].append({"cycle": a.cycle, "event": "DEMONSTRATED", "state": RESOLVED,
                         "at": now(), "note": a.evidence})
    restate(f, proj)
    save(review, data)
    print(f"{a.id}  DEMONSTRATED  cycle {a.cycle:02d}  -> {RESOLVED}")
    return 0


def state_after(f: dict, cycle: int) -> str:
    """The finding's state as at the end of the given cycle.

    §6 defines OPEN_n and the _NEW_n sets over cycle boundaries, so the loop
    controller needs history, not just the current state.
    """
    state = None
    for e in f["history"]:
        if e["cycle"] <= cycle:
            state = e["state"]
    return state or ""


def snapshot(data: dict, cycle: int,
             proj: cycle_projection.Projection | None = None) -> dict[str, set[str]]:
    """Per-cycle view. Also projected, or `show --cycle` would contradict `show`."""
    out = {OPEN: set(), RESOLVED: set(), DISPUTED: set()}
    for fid, f in data["findings"].items():
        if proj is None:
            s = state_after(f, cycle)
        else:
            s = cycle_projection.replay(
                f["history"], proj,
                upto={e["cycle"] for e in f["history"] if e["cycle"] <= cycle})
        if s in out:
            out[s].add(fid)
    return out


def cmd_show(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    if not data["findings"]:
        print(f"no findings recorded in {review}")
        return 0

    if a.cycle is not None:
        snap = snapshot(data, a.cycle, projection(review))
        print(f"state after cycle {a.cycle:02d}")
        for s in STATES:
            ids = sorted(snap[s])
            print(f"  {s:<9} {len(ids):>2}  {', '.join(ids) if ids else '-'}")
        return 0

    proj = projection(review)
    print(f"findings ledger — {review}")
    if proj.invalid:
        print("  cycles failing MC-2, whose events are evidence only: "
              + ", ".join(f"{c:02d}" for c in sorted(proj.invalid)))
    for fid in sorted(data["findings"]):
        f = data["findings"][fid]
        print(f"\n  {fid}  [{effective_state(f, proj)}]  {f['class']}"
              + (f"  ({f['requirement_id']})" if f["requirement_id"] else ""))
        for e in f["history"]:
            note = f"  {e['note'][:60]}" if e.get("note") else ""
            mark = "" if proj.authorizes(e["cycle"]) else "  [no authority]"
            print(f"      cycle {e['cycle']:02d}  {e['event']:<18} -> "
                  f"{e['state']}{mark}{note}")
    print()
    counts = {s: 0 for s in STATES}
    for f in data["findings"].values():
        counts[effective_state(f, proj)] += 1
    for s in STATES:
        print(f"  {s:<9} {counts[s]}")
    return 0


# ---------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledger.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--review", required=True,
                        help="the review directory, e.g. runs/A1E-001/plan-review")

    r = sub.add_parser("raise", help="record a Codex finding")
    common(r)
    r.add_argument("--cycle", type=int, required=True)
    r.add_argument("--id", required=True)
    # No argparse `choices` here. argparse would reject an out-of-vocabulary
    # class with a generic usage error and exit 2, before the refusals above can
    # explain why. The reason is the useful part, so validation happens in
    # cmd_raise and every refusal exits 1 with a stated cause.
    r.add_argument("--class", dest="klass", required=True,
                   metavar="CLASS")
    r.add_argument("--requirement")
    r.add_argument("--note", default="")
    r.set_defaults(fn=cmd_raise)

    d = sub.add_parser("respond", help="ACCEPT or REJECT_WITH_REASON")
    common(d)
    d.add_argument("--cycle", type=int, required=True)
    d.add_argument("--id", required=True)
    d.add_argument("--disposition", required=True,
                   choices=("ACCEPT", "REJECT_WITH_REASON"))
    d.add_argument("--note", default="",
                   help="§5 Reason. Required for REJECT_WITH_REASON.")
    d.add_argument("--spec-evidence", dest="spec_evidence", default="",
                   help="§5 Spec evidence. Required for REJECT_WITH_REASON: what "
                        "in the specification supports the rejection.")
    d.set_defaults(fn=cmd_respond)

    v = sub.add_parser("resolve", help="record that an accepted repair was demonstrated")
    common(v)
    v.add_argument("--cycle", type=int, required=True)
    v.add_argument("--id", required=True)
    v.add_argument("--evidence", default="")
    v.set_defaults(fn=cmd_resolve)

    o = sub.add_parser("reopen", help="record that a RESOLVED finding recurred")
    common(o)
    o.add_argument("--cycle", type=int, required=True)
    o.add_argument("--id", required=True)
    o.add_argument("--evidence", default="",
                   help="what shows the same underlying finding is present again")
    o.set_defaults(fn=cmd_reopen)

    s = sub.add_parser("show", help="print the ledger, or a per-cycle snapshot")
    common(s)
    s.add_argument("--cycle", type=int)
    s.set_defaults(fn=cmd_show)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    try:
        return args.fn(args)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
