#!/usr/bin/env python3
"""Ask the controller what state each blocking defect is actually in.

    python scripts/reconcile_blocking.py
    python scripts/reconcile_blocking.py --write

Exit 0 = every blocking item was located and its state established.
Exit 1 = at least one could not be, and which one is named.

Why this exists
---------------
specs/blocking-defects.json says so itself, in a field called
`examination_not_yet_reconciled`:

    The eight entries below carry independently_examined_in_cycle: null and
    repair_landed: null, and that is deliberate rather than researched. Their
    ledger histories have not yet been reconciled against the controller's own
    boundary walk, and the ledger's cached state field is exactly what SELF-F01
    proved cannot be trusted for this. Null is the conservative direction [...]
    Reconciling them with `loop_state.py --json` is the next step, and until it
    is done this file says less than it eventually will.

So EC-1 and EC-4 both report ten blocking defects open, and nobody can say
how many of those ten are open because a reviewer looked and was not
satisfied, versus open because nobody has looked at the question at all.
Those are different situations and the person who has to decide needs them
apart.

Where each answer comes from, and where it does not
---------------------------------------------------
The state comes from `loop_state.py --json`, which prints the §6 sets its own
boundary walk produced. Not from the ledger's cached `state` field: SELF-F01
is the finding that a cached state can disagree with the walk, and this is
the exact question it disagreed about. Not from `repair_status` either, which
ledger.py lists in NON_AUTHORITATIVE_FIELDS, so a finding reading
IMPLEMENTED_AWAITING_DEMONSTRATION tells you what somebody recorded about the
repair and nothing about whether a reviewer examined it.

A finding is independently examined when a DEMONSTRATED event sits in a cycle
that is valid at the governing boundary. That is precisely what RESOLVED
means in the walk's output, so membership of the RESOLVED set is the answer
and the cycle number is read back out of the history afterwards, restricted
to the valid cycles the walk named.

`repair_landed` is NOT derived here, and the absence is deliberate. Nothing
in the ledger records when a repair landed; the dates on D02-F01 and D04-F01
were put there by hand. Deriving them from git would mean guessing which
commit a repair was, and a guess written into a classification file is worse
than a null, because the null at least says it does not know.

The answer this turned out to give, which was not the one expected
------------------------------------------------------------------
All three bootstrap runs are marked NOT_A_PROTOCOL_CYCLE in their run.json,
so the controller refuses the default reading and this has to pass
--development to get an answer at all. Alex Zamurko, 10 September 2026:

    make the controller explicitly reject/exclude any run marked
    NOT_A_PROTOCOL_CYCLE from authoritative loop-state calculation ...
    bootstrap/development evidence can still exist and be tested, but it can
    never accidentally count as authoritative protocol evidence.

That settles the question in a direction nobody had written down.
`independently_examined_in_cycle` cannot be filled from these runs at any
point in the future, however much work goes into them, because the runs are
development evidence by ruling rather than by accident.

EC-1 says "Each has a repair that no reviewer has examined. Until one has,
this condition is not met", and EC-4 reads the same way. Both sentences
suggest the examination could come from the three reviews that exist. It
cannot. What they are waiting for is a protocol cycle, which has never been
run, and that is Alex Zamurko's safeguard 4 of 26 October: one independent
review and explicit human approval before MVP acceptance.

blocking-defects.json says reconciling with `loop_state.py --json` is the
next step. It is a useful step and it is not the one that unblocks anything,
and that file now says so.

So --write refuses
------------------
The flag is kept rather than removed, because somebody will reach for it and
a flag that explains the refusal is more use than a missing one that invites
a hand edit. What this program prints is development evidence, clearly
labelled, and the one thing it will not do is write a number into the field
two exit conditions read.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
SPECS = REPO / "specs"

OPEN, RESOLVED, DISPUTED = "open", "resolved", "disputed"

# What this program can conclude, and the three are kept apart on purpose.
EXAMINED = "EXAMINED"          # a DEMONSTRATED in a cycle valid at the boundary
NOT_EXAMINED = "NOT_EXAMINED"  # the walk placed it OPEN
DISPUTED_BY = "DISPUTED"       # a reviewer looked and did not agree
UNLOCATED = "UNLOCATED"        # no ledger holds it, or no walk ran


def reviews() -> list[Path]:
    base = REPO / "runs"
    if not base.is_dir():
        return []
    return sorted(p / "plan-review" for p in base.iterdir()
                  if (p / "plan-review" / "ledger.json").is_file())


def walk(review: Path) -> tuple[dict | None, str]:
    """The controller's own §6 sets at the governing boundary.

    Its exit code is deliberately ignored for the purpose of reading the
    sets: a run that reports CONTINUE or MAX_4_REACHED exits non-zero and has
    still produced a perfectly good boundary walk. What matters is whether
    the JSON parsed and whether it says a walk happened.
    """
    # --development, and the label it returns is carried all the way out.
    #
    # All three bootstrap runs are marked NOT_A_PROTOCOL_CYCLE in their
    # run.json, so the controller refuses the default reading. Alex Zamurko,
    # 10 September 2026: "make the controller explicitly reject/exclude any
    # run marked NOT_A_PROTOCOL_CYCLE from authoritative loop-state
    # calculation ... bootstrap/development evidence can still exist and be
    # tested, but it can never accidentally count as authoritative protocol
    # evidence."
    #
    # The flag is the right call here and it changes what this program can
    # conclude, which is the point of the next few paragraphs in the module
    # docstring. Passing it to get an answer and then presenting that answer
    # as the authoritative one is precisely the accident his instruction
    # names.
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "loop_state.py"),
         "--review", str(review), "--json", "--development"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))
    out = (r.stdout or "").strip()
    if not out:
        # stderr, not just the exit code. The first version of this reported
        # "printed nothing (exit 2)" seven times, which named the symptom and
        # discarded the one thing that said why: the controller had written
        # its reason to stderr and this threw it away. A reader that cannot
        # see the error reports an absence, which is the shape most of this
        # repository's findings have.
        err = (r.stderr or "").strip().splitlines()
        tail = " | ".join(x.strip() for x in err[-3:]) or "and said nothing"
        return None, (f"the controller exited {r.returncode} with no JSON: "
                      f"{tail}")
    try:
        d = json.loads(out)
    except json.JSONDecodeError as e:
        return None, f"the controller's --json did not parse: {e}"
    # SELF-F04's lesson, from the other side. The flag exists so a caller does
    # not parse prose, and on the path where no boundary was walked it used to
    # hand back prose under exit 0. It now carries sets_established, so this
    # asks that rather than inferring from which keys happen to be present.
    if not d.get("sets_established"):
        return None, ("the controller established no sets, so there is no "
                      "walk to read a state out of")
    return d, ""


def demonstrated_in(ledger: dict, fid: str, valid: list[int]) -> int | None:
    """The cycle of the DEMONSTRATED event, restricted to valid cycles.

    Read only after the walk has already placed the finding in RESOLVED. The
    walk is what decides; this recovers the number for a reader, and returns
    None rather than guessing if the history does not contain one, which
    would mean the two disagree and is worth seeing.
    """
    f = (ledger.get("findings") or {}).get(fid) or {}
    seen = [h.get("cycle") for h in f.get("history") or []
            if h.get("event") == "DEMONSTRATED" and h.get("cycle") in valid]
    return max(seen) if seen else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true",
                   help="record what the walk established, in the direction "
                        "it supports, and nothing else")
    a = p.parse_args()

    bf = SPECS / "blocking-defects.json"
    if not bf.is_file():
        print("  there is no blocking-defect classification to reconcile")
        return 1
    doc = json.loads(bf.read_text(encoding="utf-8"))
    blocking = doc.get("blocking") or {}
    if not blocking:
        print("  nothing is classified as blocking")
        return 1

    # One walk per review, not one per finding. The walk is the expensive
    # part and its answer is a property of the review, not of the finding.
    walks: dict[str, tuple[dict | None, str, dict]] = {}
    for rv in reviews():
        d, err = walk(rv)
        led = {}
        try:
            led = json.loads((rv / "ledger.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            err = err or f"its ledger could not be read: {e}"
        walks[rv.parent.name] = (d, err, led)

    print("blocking defects, reconciled against the controller's own walk")
    print(f"  {len(blocking)} classified blocking, "
          f"{len(walks)} review(s) walked\n")

    rows, problems, changes = [], [], []
    for fid in sorted(blocking):
        entry = blocking[fid]
        found = None
        for run_name, (d, err, led) in walks.items():
            if fid not in (led.get("findings") or {}):
                continue
            if d is None:
                problems.append(f"{fid} is in {run_name} and {err}")
                found = (run_name, UNLOCATED, None, err)
                break
            valid = sorted(d.get("valid_cycles") or [])
            if fid in (d.get(RESOLVED) or []):
                cyc = demonstrated_in(led, fid, valid)
                found = (run_name, EXAMINED, cyc,
                         f"RESOLVED at boundary "
                         f"{d.get('governing_boundary')}")
            elif fid in (d.get(DISPUTED) or []):
                found = (run_name, DISPUTED_BY, None,
                         f"DISPUTED at boundary "
                         f"{d.get('governing_boundary')}")
            elif fid in (d.get(OPEN) or []):
                found = (run_name, NOT_EXAMINED, None,
                         f"OPEN at boundary "
                         f"{d.get('governing_boundary')}")
            else:
                found = (run_name, UNLOCATED, None,
                         "in the ledger and in none of the walk's three sets")
                problems.append(f"{fid} is in {run_name}'s ledger and in none "
                                f"of OPEN, RESOLVED or DISPUTED")
            break

        if found is None:
            # An implementer-disclosed entry has no ledger and no cycle ever
            # produced an identifier for it, which is the whole membership
            # rule of that register. Saying UNLOCATED here would read as a
            # fault; it is a different kind of record and is named as one.
            where = str(entry.get("where", ""))
            if "implementer-disclosed" in where:
                rows.append((fid, "register", "NO_LEDGER", None,
                             "implementer-disclosed: no cycle produced an "
                             "identifier, so no walk can place it"))
                continue
            rows.append((fid, "-", UNLOCATED, None,
                         "no ledger holds this identifier"))
            problems.append(f"{fid} is classified blocking and no ledger "
                            f"holds it")
            continue

        run_name, verdict, cyc, why = found
        rows.append((fid, run_name, verdict, cyc, why))

        # What the file records against what the walk shows, kept and
        # printed rather than acted on. The two disagreeing is worth a
        # reader's attention even though nothing here may resolve it, and a
        # disagreement nobody prints is a disagreement nobody has.
        was = entry.get("independently_examined_in_cycle")
        if verdict == EXAMINED and cyc is not None and was != cyc:
            changes.append((fid, was, cyc))

    w = max(len(r[0]) for r in rows)
    for fid, run_name, verdict, cyc, why in rows:
        c = f"  cycle {cyc:02d}" if cyc else ""
        print(f"  {fid:<{w}}  {run_name:<14}  {verdict:<13}{c}")
        print(f"  {'':<{w}}  {why}")

    examined = sum(1 for r in rows if r[2] == EXAMINED)
    unexamined = sum(1 for r in rows if r[2] == NOT_EXAMINED)
    disputed = sum(1 for r in rows if r[2] == DISPUTED_BY)
    register = sum(1 for r in rows if r[2] == "NO_LEDGER")

    print(f"\n  development evidence: {examined} demonstrated, "
          f"{unexamined} open, {disputed} disputed, "
          f"{register} in the register with no cycle to walk")

    if changes:
        print("\n  the development walk disagrees with what the file "
              "records:")
        for fid, was, cyc in changes:
            print(f"    {fid}: file says {was!r}, walk demonstrates in "
                  f"cycle {cyc}")
        print("  Neither is written. The walk is development evidence and "
              "the file's\n  field is for an authoritative one.")

    # The conclusion this program exists to reach, and it is a refusal.
    #
    # Everything above came from a walk over runs marked NOT_A_PROTOCOL_CYCLE.
    # `independently_examined_in_cycle` is the field EC-1 and EC-4 read to
    # decide whether a blocking repair has been independently examined, and
    # filling it from development evidence would make those two conditions
    # answer yes on the strength of a run that is, by Alex Zamurko's own
    # ruling, not a protocol outcome. That is the accident the ruling exists
    # to prevent, arriving by the back door of a helpful script.
    #
    # So --write does not write, and says so. The flag is kept rather than
    # removed: somebody will reach for it, and a flag that explains the
    # refusal is better than a missing one that invites a hand edit.
    print("\n  " + "-" * 64)
    print("  NOTHING ABOVE CAN CLOSE A BLOCKING ITEM, and that is not a "
          "defect in\n  this program.")
    print()
    print("  Every cycle above belongs to a run marked NOT_A_PROTOCOL_CYCLE.")
    print("  Alex Zamurko, 10 September 2026: bootstrap evidence \"can never")
    print("  accidentally count as authoritative protocol evidence\".")
    print()
    print("  So independently_examined_in_cycle cannot be filled from these")
    print("  runs at any point in the future, no matter how much work goes")
    print("  into them. EC-1's message reads as though it could, and EC-4's")
    print("  reads the same way. What they are waiting for is a protocol")
    print("  cycle, which does not yet exist.")
    print()
    print("  That is Alex Zamurko's safeguard 4 of 26 October, in his words:")
    print("  \"One independent review and explicit human approval are "
          "required")
    print("  before MVP acceptance, but not for individual development "
          "PRs.\"")
    if a.write:
        print("\n  --write refused: see above. The classification file is "
              "unchanged.")
        return 1

    if problems:
        print("\n  could not be established:")
        for pr in problems[:10]:
            print(f"    {pr}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
