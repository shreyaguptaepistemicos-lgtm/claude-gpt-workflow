#!/usr/bin/env python3
"""Loop-state controller.

Computes CONVERGED / HUMAN_ADJUDICATION_REQUIRED / STALLED / MAX_4_REACHED /
CONTINUE for one review loop, per §6 and §13 of the protocol, and shows the
working.

    python scripts/loop_state.py --review runs/A1E-001/plan-review

Exit 0 = a state was determined, 2 = could not run.
The state itself is on stdout as LOOP_STATUS; it is not an exit code, because
CONTINUE is not a failure and STALLED is not an error.

Validity is computed, not trusted
---------------------------------
§2 : "Only cycles that pass the MC-2 conformance gate count toward this maximum."
§3 : an invalid cycle "cannot support an authoritative Codex finding" and
     "cannot consume one of the four valid review cycles".

So this runs scripts/validate_cycle.py on every cycle directory rather than
reading a recorded verdict. A loop controller that accepted an asserted PASS
would let an invalid cycle consume the budget, which is the exact defect the
"MAX 4 counts valid cycles" note exists to prevent.

Two consequences, both deliberate and both worth disagreeing with if you see it
differently:

1. §6's n indexes VALID cycles, not directory numbers. If cycle-02 fails the
   gate, then cycle-03 is n=2. Otherwise |OPEN_n| would be compared against a
   cycle whose evidence is not authoritative.

2. Events recorded in an invalid cycle are ignored entirely, including
   resolutions. A finding accepted in valid cycle 1 and marked demonstrated in
   invalid cycle 2 stays OPEN, because the cycle that would demonstrate it
   cannot support an authoritative anything. This is the conservative reading
   and it can only ever delay an exit, never manufacture one.

What this does not do
---------------------
It does not decide whether a repair was demonstrated; the ledger records that
assertion and this reads it. It does not adjudicate disputes. And CONVERGED
here means the finding sets are empty, not that the plan is good.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycle_projection  # noqa: E402

VALIDATOR = REPO / "scripts" / "validate_cycle.py"
MAX_VALID_CYCLES = 4
TERMINAL = ("CONVERGED", "HUMAN_ADJUDICATION_REQUIRED", "STALLED",
            "MAX_4_REACHED")

OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"

# B01-F11: both live in cycle_projection now, so the ledger and this controller
# cannot drift apart about which cycles count.
cycle_dirs = cycle_projection.cycle_dirs
gate = cycle_projection.gate


class CannotCalculate(Exception):
    """Loop state is not determinable from the evidence present. Exit 2."""


def load_ledger(review: Path) -> dict:
    """State history. Absent means no findings have been responded to yet.

    Distinct from the per-cycle authoritative findings, which are checked
    separately below and whose absence is a refusal rather than a zero.
    """
    p = review / "ledger.json"
    if not p.is_file():
        return {"findings": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"ledger.json is not valid JSON: {e}")


def authoritative_findings(cycle_dir: Path) -> list[str]:
    """The finding IDs the runner extracted for this cycle.

    Alex Zamurko, issue 4: "Controller refuses to calculate loop state if
    findings.json is missing or invalid."

    Absence used to mean zero. That is the path by which a review full of
    findings produces CONVERGED: nobody transcribes them, the ledger is empty,
    and empty reads as clean. So a valid cycle without an authoritative findings
    record is not a cycle with no findings; it is a cycle whose result nobody
    can determine, and the controller says so rather than guessing.
    """
    # Requirements 3 and 4: the structured result must still account for the
    # raw review, and identifiers must be unchanged along the whole chain
    #
    #     codex-output-raw.md -> findings.json -> ledger.json
    #
    # Checked here rather than only at record time, because findings.json is an
    # ordinary file afterwards. A finding quietly dropped from it, or renamed,
    # would otherwise never be noticed again.
    raw = cycle_dir / "codex-output-raw.md"
    p = cycle_dir / "findings.json"

    # Issue 6: "controller reads only the designated authoritative capture."
    # codex-output-raw.md is written from that attempt, so the two must agree.
    # If they do not, someone edited the working copy after the designation, and
    # the loop would be measuring a review nobody designated.
    clog = cycle_dir / "capture-log.json"
    if clog.is_file() and raw.is_file():
        try:
            cl = json.loads(clog.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CannotCalculate(f"{cycle_dir.name}/capture-log.json is not "
                                  f"valid JSON: {e}")
        chosen = cl.get("authoritative")
        if chosen is None:
            raise CannotCalculate(
                f"{cycle_dir.name} has capture attempts but none is designated "
                "authoritative.\n  Every attempt failed the validity "
                "requirements, so there is no review to evaluate.")
        import hashlib
        actual = hashlib.sha256(raw.read_bytes()).hexdigest()
        if actual != cl.get("authoritative_sha256"):
            raise CannotCalculate(
                f"{cycle_dir.name}: codex-output-raw.md does not match "
                f"attempt-{chosen:02d}, the designated authoritative capture.\n"
                f"  designated  {cl.get('authoritative_sha256')}\n"
                f"  on disk     {actual}\n"
                "  The loop must read the designated capture and nothing else.")

    if raw.is_file() and p.is_file():
        try:
            import findings_format
            parsed, problems = findings_format.extract(
                raw.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review cannot be reparsed, so the "
                f"structured result cannot be checked against it: {e}")
        if problems:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review no longer parses "
                "deterministically:\n  " + "\n  ".join(problems))
        try:
            structured = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CannotCalculate(f"{cycle_dir.name}/findings.json is not valid "
                                  f"JSON: {e}")
        raw_ids = [f["id"] for f in parsed]
        got_ids = [f.get("id") for f in structured.get("findings", [])]
        if raw_ids != got_ids:
            raise CannotCalculate(
                f"{cycle_dir.name}: findings.json does not match the raw review "
                "it was extracted from.\n"
                f"  raw        {raw_ids}\n"
                f"  structured {got_ids}\n"
                "  A finding dropped or renamed here is a finding the loop will "
                "never see.")

    if not p.is_file():
        raise CannotCalculate(
            f"{p.parent.name} passed MC-2 but has no findings.json.\n"
            "  Absence is not zero. Either the runner did not record this cycle "
            "or the file\n  was removed; both make the loop state "
            "undeterminable. Re-record the cycle.")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"{p.parent.name}/findings.json is not valid "
                              f"JSON: {e}")
    if d.get("schema") != "cycle-findings/1":
        raise CannotCalculate(
            f"{p.parent.name}/findings.json declares schema "
            f"{d.get('schema')!r}, expected 'cycle-findings/1'")
    items = d.get("findings")
    if not isinstance(items, list) or "count" not in d:
        raise CannotCalculate(f"{p.parent.name}/findings.json is malformed: "
                              "needs a findings list and a count")
    if d["count"] != len(items):
        raise CannotCalculate(
            f"{p.parent.name}/findings.json says count={d['count']} but carries "
            f"{len(items)} findings")
    if not items and not d.get("zero_findings_asserted"):
        raise CannotCalculate(
            f"{p.parent.name}/findings.json records zero findings without "
            "zero_findings_asserted.\n  Zero has to be asserted, never inferred.")
    return [f["id"] for f in items if isinstance(f, dict) and "id" in f]


def state_after(f: dict, valid_upto: set[int]) -> str | None:
    """State as at the end of the valid cycles in `valid_upto`.

    Events in cycles outside the set are skipped, per consequence 2 above. The
    replay itself lives in cycle_projection so the ledger applies the identical
    rule when it decides whether a transition is permitted (B01-F11).
    """
    # The projection here authorizes exactly the cycles being asked about: the
    # `upto` set has already established that they are valid, so nothing further
    # needs disqualifying. Built from that set rather than left empty, because
    # an empty projection now has a horizon of 1 (B01-F11's nonexistent-cycle
    # half) and would silently refuse authority to every cycle above the first.
    scoped = cycle_projection.Projection(sorted(valid_upto), {})
    return cycle_projection.replay(f["history"], scoped, upto=valid_upto)


def load_authorizations(review: Path) -> list[dict]:
    """Recorded human authorizations to run another loop past a terminal exit.

    B01-F02's correction: "Refuse further automated cycles after that outcome
    unless an explicitly recorded human transition authorizes another loop."

    An authorization has to name both the boundary and the outcome it clears. A
    blanket "keep going" would restore the defect under a different spelling: it
    would let any later cycle override any earlier mandatory termination, which
    is the finding.
    """
    p = review / "loop-authorizations.json"
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"loop-authorizations.json is not valid JSON: {e}")
    if d.get("schema") != "loop-authorization/1":
        raise CannotCalculate(
            f"loop-authorizations.json declares schema {d.get('schema')!r}, "
            "expected 'loop-authorization/1'")
    items = d.get("authorizations")
    if not isinstance(items, list):
        raise CannotCalculate("loop-authorizations.json has no authorizations list")
    for i, a in enumerate(items):
        missing = [k for k in ("after_valid_cycle", "outcome", "authorized_by",
                               "reason") if not str(a.get(k, "")).strip()]
        if missing:
            raise CannotCalculate(
                f"authorization {i} is missing {', '.join(missing)}.\n"
                "  An authorization to continue past a mandatory exit has to say "
                "which exit,\n  at which boundary, on whose authority, and why. "
                "Any of those blank and it\n  is not a recorded human transition, "
                "it is a switch the loop turned off for itself.")
    return items


def cleared_by(auths: list[dict], n: int, outcome: str) -> dict | None:
    for a in auths:
        if a.get("after_valid_cycle") == n and a.get("outcome") == outcome:
            return a
    return None


def sets_at(ledger: dict, valid_upto: set[int]) -> dict[str, set[str]]:
    out = {OPEN: set(), RESOLVED: set(), DISPUTED: set()}
    for fid, f in ledger["findings"].items():
        s = state_after(f, valid_upto)
        if s in out:
            out[s].add(fid)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", required=True)
    ap.add_argument("--quiet", action="store_true", help="print LOOP_STATUS only")
    ap.add_argument("--development", action="store_true",
                    help="compute the loop state of a run marked "
                         "NOT_A_PROTOCOL_CYCLE. The result is labelled "
                         "development evidence and is not an authoritative "
                         "protocol outcome. B01-F08.")
    a = ap.parse_args(argv[1:])
    try:
        return _run(a)
    except CannotCalculate as e:
        print(f"CANNOT CALCULATE LOOP STATE: {e}", file=sys.stderr)
        print()
        print("No LOOP_STATUS is emitted. An undeterminable state is not "
              "CONTINUE, and it is\nnot CONVERGED; treating it as either is the "
              "failure this refusal exists to stop.", file=sys.stderr)
        return 2


def run_classification(review: Path) -> tuple[str, str]:
    """(label, bootstrap_review) for the run this review belongs to.

    B01-F08. Codex, cycle 02: "scripts/loop_state.py and
    scripts/cycle_projection.py still do not read the run's bootstrap
    classification. An isolated run initialized with --bootstrap-exempt, frozen
    and recorded through the runner with explicit zero findings returned
    LOOP_STATUS: CONVERGED through the ordinary controller interface."

    The runner has labelled exempt runs since B01-F14, and the gate refuses to
    let them become real cycles. But nothing stopped the controller reading one
    and emitting an outcome indistinguishable from a protocol result, which is
    the half of the finding that stayed open: development evidence reaching
    authoritative loop state.
    """
    run_json = review.parent / "run.json"
    if not run_json.is_file():
        return "UNKNOWN", ""
    try:
        run = json.loads(run_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"{run_json} is not valid JSON: {e}")
    label = str(run.get("bootstrap_review", "")).strip()
    return ("DEVELOPMENT" if label.startswith("EXEMPT") else "PROTOCOL"), label


def _run(a) -> int:
    review = Path(a.review).resolve()
    if not review.is_dir():
        print(f"not a directory: {review}", file=sys.stderr)
        return 2

    # Alex Zamurko, 10 September: "make the controller explicitly reject/exclude
    # any run marked NOT_A_PROTOCOL_CYCLE from authoritative loop-state
    # calculation ... bootstrap/development evidence can still exist and be
    # tested, but it can never accidentally count as authoritative protocol
    # evidence."
    #
    # So the refusal is against the DEFAULT reading, not against the evidence.
    # --development still computes it, and says on every line of output what it
    # is. Removing the ability to analyse bootstrap evidence would break the
    # bootstrap review itself, which is the one loop that has to run before any
    # protocol run exists.
    kind, label = run_classification(review)
    if kind == "DEVELOPMENT" and not a.development:
        print(f"REFUSED: {review.parent.name} is marked {label}\n\n"
              "  Its cycles are development evidence. A loop state computed "
              "over them is not a\n  protocol outcome, and nothing in the "
              "output would have said so.\n\n"
              "  Pass --development to compute it anyway. The result is "
              "labelled and must not be\n  cited as an authoritative protocol "
              "result.", file=sys.stderr)
        return 2
    if kind == "PROTOCOL" and a.development:
        print(f"REFUSED: {review.parent.name} is a protocol run, so "
              "--development does not apply.\n"
              "  Labelling a protocol outcome as development evidence would "
              "understate it just as\n  badly as the reverse overstates it.",
              file=sys.stderr)
        return 2

    lines: list[str] = [f"loop state — {review}"]
    if kind == "DEVELOPMENT":
        lines += ["",
                  "DEVELOPMENT EVIDENCE — NOT A PROTOCOL OUTCOME",
                  f"  {label}",
                  "  The status below describes bootstrap evidence and does "
                  "not establish a protocol",
                  "  result. §2 and §3 reserve authoritative outcomes to valid "
                  "protocol cycles."]

    dirs = cycle_dirs(review)
    if not dirs:
        print(f"no cycle directories in {review}", file=sys.stderr)
        return 2

    lines += ["", "cycles"]
    valid: list[int] = []
    for num, d in dirs:
        ok, why = gate(d)
        if ok:
            valid.append(num)
            lines.append(f"  cycle-{num:02d}  VALID    -> n={len(valid)}")
        else:
            lines.append(f"  cycle-{num:02d}  INVALID  {why}")
            lines.append("            does not count toward the budget and its "
                         "events are ignored")
    lines += ["", f"VALID_CYCLE_COUNT: {len(valid)}"]

    if not valid:
        lines += ["", "LOOP_STATUS: CONTINUE",
                  "No valid cycle has been completed, so §6 has nothing to measure. "
                  "Repair the evidence and rerun."]
        print("\n".join(lines) if not a.quiet else "LOOP_STATUS: CONTINUE")
        return 0

    # Every valid cycle must carry an authoritative findings record, and the
    # ledger must account for everything in it. Without this the controller
    # measures only what someone remembered to transcribe, and silence reads as
    # a clean review.
    ledger = load_ledger(review)
    lines += ["", "authoritative findings"]
    unaccounted: list[str] = []
    for num, d in dirs:
        if num not in valid:
            continue
        ids = authoritative_findings(d)
        missing = [i for i in ids if i not in ledger["findings"]]
        lines.append(f"  cycle-{num:02d}  {len(ids)} finding(s)"
                     + (f": {', '.join(ids)}" if ids else ", explicitly zero"))
        unaccounted += [f"cycle-{num:02d}: {i}" for i in missing]
    if unaccounted:
        raise CannotCalculate(
            "findings the reviewer recorded are absent from the ledger:\n  "
            + "\n  ".join(unaccounted) +
            "\n\n  The loop state would be computed over a smaller finding set "
            "than the review\n  produced, which is how a review full of findings "
            "reaches CONVERGED.")
    lines.append("  every recorded finding is accounted for in the ledger")

    # B01-F02. Every valid cycle boundary is evaluated in order, and the first
    # terminal outcome governs. Evaluating only the latest boundary let a later
    # cycle overwrite an earlier mandatory exit: one finding accepted in cycle
    # 01, untouched in 02 and resolved in 03 reported CONVERGED, even though
    # cycle 02 had already required STALLED and the loop should never have
    # reached 03.
    auths = load_authorizations(review)
    governing = None          # (n, status, detail, cur)
    overridden: list[str] = []
    # (status, authorization) when the LATEST boundary's exit was cleared. The
    # distinction matters: clearing a historical boundary lets evaluation move
    # past it, clearing the latest one is permission for the next cycle.
    cleared_latest: tuple[str, dict] | None = None
    lines += ["", "boundaries, in order"]

    for n in range(1, len(valid) + 1):
        cur, prev, resolved_new, disputed_new = sets_at_boundary(ledger, valid, n)
        status, detail, shown = decide(cur, prev, resolved_new, disputed_new, n)
        lines.append(f"  n={n} (cycle-{valid[n-1]:02d})  OPEN {len(cur[OPEN])}  "
                     f"DISPUTED {len(cur[DISPUTED])}  RESOLVED {len(cur[RESOLVED])}"
                     f"   -> {status}")
        if status == "CONTINUE":
            continue
        auth = cleared_by(auths, n, status)
        if auth is None:
            governing = (n, status, detail, cur, shown)
            break
        lines.append(f"        {status} at n={n} cleared by recorded "
                     f"authorization: {auth['authorized_by']}")
        lines.append(f"        reason: {auth['reason']}")
        overridden.append(f"n={n} {status} (authorized by {auth['authorized_by']})")
        if n == len(valid):
            cleared_latest = (status, auth)

    n_latest = len(valid)
    if governing is None:
        cur, prev, resolved_new, disputed_new = sets_at_boundary(
            ledger, valid, n_latest)
        status, detail, shown = decide(cur, prev, resolved_new, disputed_new,
                                       n_latest)
        if cleared_latest is not None:
            # B01-F02, the half cycle 02 found still broken. The loop above
            # cleared the exit at the latest boundary, then this fallback called
            # decide() again — and decide() knows nothing about authorizations,
            # so it returned the very exit that had just been cleared. The output
            # said "STALLED at n=2 cleared by recorded authorization" and then
            # "LOOP_STATUS: STALLED", and the runner refused the next cycle.
            #
            # Codex: "the explicitly authorized continuation required by the
            # original correction and decision I does not work at the point the
            # runner needs it." My own control never caught it because it only
            # authorized historical boundaries, never the latest one.
            #
            # A cleared latest boundary is permission to continue, not the exit
            # re-imposed. Resumed-loop semantics, stated rather than implied:
            # the authorization clears one named exit at one named boundary, so
            # the next cycle is permitted and the budget is whatever the cleared
            # exit allowed. Clearing MAX_4_REACHED is therefore a human decision
            # to spend more than four valid cycles, and it has to name that exit
            # explicitly — cleared_by matches on the outcome, so an
            # authorization for STALLED cannot quietly extend the budget.
            _st, _auth = cleared_latest
            status = "CONTINUE"
            detail = (
                f"The {_st} at n={n_latest} was cleared by a recorded human "
                f"authorization from {_auth['authorized_by']}.\n"
                f"Reason given: {_auth['reason']}\n"
                "The loop continues on that authority. Repair the plan, produce "
                "a new version, and\nopen the next cycle with a new frozen "
                "target.")
        governing = (n_latest, status, detail, cur, shown)

    n, status, detail, cur, shown = governing

    def fmt(ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "-"

    lines += ["", f"§6 sets and exits at the governing boundary, n={n}"] + shown

    # Only when nothing has already explained the CONTINUE. decide() returns an
    # empty detail for an ordinary continuation, whereas a continuation resting
    # on a cleared exit arrives here carrying the authorization it rests on —
    # and this used to overwrite it with the generic text, so the output named
    # no authority for a decision that existed only because of one.
    if status == "CONTINUE" and not detail:
        detail = (f"Repair the plan, produce a new version, and open cycle "
                  f"{dirs[-1][0] + 1:02d} with a new frozen target.")

    lines += ["", f"LOOP_STATUS: {status}", detail]

    # The cycles that should never have been opened. Reported rather than
    # silently absorbed, because the evidence in them was produced under a loop
    # that had already terminated and no one authorized restarting it.
    if status in TERMINAL and n < n_latest:
        after = [f"cycle-{c:02d}" for c in valid[n:]]
        lines += ["",
                  f"UNAUTHORIZED CONTINUATION: the loop reached {status} at n={n} "
                  f"(cycle-{valid[n-1]:02d}).",
                  f"  {len(after)} further valid cycle(s) were run after it: "
                  + ", ".join(after),
                  "  §6's exits are mandatory, so the first one governs and the "
                  "later cycles do",
                  "  not override it. Record a human authorization in "
                  "loop-authorizations.json if",
                  "  another loop was genuinely approved, or take the outcome "
                  "above to the gate."]
    if overridden:
        lines += ["", "Earlier terminal outcomes cleared by recorded "
                  "authorization: " + "; ".join(overridden)]

    if status != "CONTINUE" and cur[DISPUTED]:
        lines.append("")
        lines.append(f"Disputes for adjudication ({len(cur[DISPUTED])}): "
                     f"{fmt(cur[DISPUTED])}")
        lines.append("§7 requires disputes and unresolved findings to reach the human "
                     "as separate lists.")

    # The label travels with the status itself, not only in the preamble.
    # --quiet prints this line alone, and a caller parsing it would otherwise
    # get a bare CONVERGED off development evidence with nothing to mark it.
    # That is the finding restated: the distinction has to survive the
    # interface, not just appear in the report.
    status_line = (f"LOOP_STATUS: {status}" if kind != "DEVELOPMENT"
                   else f"LOOP_STATUS: {status}  [DEVELOPMENT EVIDENCE — "
                        "NOT A PROTOCOL OUTCOME]")
    if a.quiet:
        print(status_line)
    else:
        lines[lines.index(f"LOOP_STATUS: {status}")] = status_line
        print("\n".join(lines))
    return 0


def sets_at_boundary(ledger: dict, valid: list[int], n: int):
    """The §6 sets as at valid cycle boundary n, plus the _NEW_n deltas."""
    upto_n = set(valid[:n])
    cur = sets_at(ledger, upto_n)
    prev = sets_at(ledger, set(valid[:n - 1])) if n > 1 else None
    resolved_new: set[str] = set()
    disputed_new: set[str] = set()
    if prev is not None:
        for fid in prev[OPEN]:
            s = state_after(ledger["findings"][fid], upto_n)
            if s == RESOLVED:
                resolved_new.add(fid)
            elif s == DISPUTED:
                disputed_new.add(fid)
    return cur, prev, resolved_new, disputed_new


def decide(cur, prev, resolved_new: set[str], disputed_new: set[str],
           n: int) -> tuple[str, str, list[str]]:
    """The §6 exit test at one boundary.

    Exits are tested in the protocol's order, and the order is load-bearing.
    HUMAN_ADJUDICATION_REQUIRED sits between CONVERGED and STALLED because a loop
    with nothing open and a dispute outstanding is not stalled: it finished
    everything automation can do. Test STALLED first and it swallows the case a
    cycle later, which is what v1.0 did.
    """
    def fmt(ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "-"

    shown = [
        f"  OPEN_{n}          {len(cur[OPEN]):>2}  {fmt(cur[OPEN])}",
        f"  DISPUTED_{n}      {len(cur[DISPUTED]):>2}  {fmt(cur[DISPUTED])}",
        f"  RESOLVED_{n}      {len(cur[RESOLVED]):>2}  {fmt(cur[RESOLVED])}",
    ]
    if prev is not None:
        shown += [
            f"  OPEN_{n-1}          {len(prev[OPEN]):>2}  {fmt(prev[OPEN])}",
            f"  RESOLVED_NEW_{n}  {len(resolved_new):>2}  {fmt(resolved_new)}",
            f"  DISPUTED_NEW_{n}  {len(disputed_new):>2}  {fmt(disputed_new)}",
        ]

    if not cur[OPEN] and not cur[DISPUTED]:
        shown.append(f"  A CONVERGED                    OPEN_{n} = 0 and "
                     f"DISPUTED_{n} = 0        yes")
        return ("CONVERGED",
                "Nothing open and nothing disputed. Proceed to human plan review.",
                shown)

    if not cur[OPEN] and cur[DISPUTED]:
        shown.append(f"  B HUMAN_ADJUDICATION_REQUIRED  OPEN_{n} = 0 and "
                     f"DISPUTED_{n} != 0     yes")
        return ("HUMAN_ADJUDICATION_REQUIRED",
                "Everything actionable is resolved or disputed, and no further "
                "automated repair is available. Stop now rather than spending a "
                "cycle on a plan with nothing open to repair. Proceed to human "
                "plan review.", shown)

    if prev is None:
        shown.append("  C STALLED                      not testable at n=1 "
                     "(§6 requires n > 1)")
    else:
        stalled = (len(cur[OPEN]) >= len(prev[OPEN])
                   and not resolved_new and not disputed_new)
        shown.append(
            f"  C STALLED                      |OPEN_{n}| >= |OPEN_{n-1}|"
            f" ({len(cur[OPEN])} >= {len(prev[OPEN])})"
            f" and no new resolved/disputed   {'yes' if stalled else 'no'}")
        if stalled:
            return ("STALLED",
                    "The last valid cycle reduced nothing, resolved nothing and "
                    "disputed nothing. Stop now rather than spending the "
                    "remaining budget. Proceed to human plan review.", shown)

    maxed = n >= MAX_VALID_CYCLES
    shown.append(f"  D MAX_4_REACHED                VALID_CYCLE_COUNT = {n}"
                 f"                  {'yes' if maxed else 'no'}")
    if maxed:
        return ("MAX_4_REACHED",
                "Budget exhausted with findings still open. Proceed to human "
                "plan review with the unresolved matters exposed.", shown)

    return ("CONTINUE", "", shown)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
