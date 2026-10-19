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
   cannot support an authoritative anything.

   What that establishes is narrow: the calculation excludes invalid-cycle
   events. This paragraph used to add that the exclusion "can only ever delay an
   exit, never manufacture one", and Codex refused the claim in cycle 03.
   Ignoring an invalid resolution does delay an exit. Ignoring an invalid RAISED
   or REOPENED removes an actionable finding, and a smaller OPEN set is how
   CONVERGED arrives early. The exclusion is not conservative in one direction,
   and calling it conservative made it sound safe in both.

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
# B01-F14: the shared run-metadata rule, so the controller and the runner refuse
# the same thing rather than each having their own idea of a usable run.
import run_pins  # noqa: E402
# D04-F01. One definition of "this field is present", shared, rather than the
# same `str(x).strip()` expression written out in two files and wrong in both.
import authority  # noqa: E402

VALIDATOR = REPO / "scripts" / "validate_cycle.py"
# One copy, in cycle_projection, where the valid cycles it counts are decided.
MAX_VALID_CYCLES = cycle_projection.MAX_VALID_CYCLES
TERMINAL = ("CONVERGED", "HUMAN_ADJUDICATION_REQUIRED", "STALLED",
            "MAX_4_REACHED")

# B01-F02, Alex Zamurko's ruling of 15 September. This controller offered a
# human authorization that cleared MAX_4_REACHED and continued the loop; the
# runner refused any cycle past the budget before it ever consulted the
# controller. Both behaviours were defensible on their own and they contradicted
# each other, so the system announced a permission it could not honour. Codex
# reproduced it: LOOP_STATUS: CONTINUE, then freeze exiting 1 on the budget.
#
# He chose the reading that keeps §2's sentence literal. Four valid cycles is
# the maximum and no authorization extends it. The other exits stay clearable,
# because STALLED and the adjudication outcomes are judgements about progress
# that a human can reasonably overrule; the budget is not a judgement.
UNCLEARABLE = ("MAX_4_REACHED",)

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


def authoritative_items(cycle_dir: Path) -> list[dict]:
    """What the runner extracted for this cycle, entries intact.

    C02-F04. This used to return identifiers only, and the `kind` the parser
    assigns each entry was dropped here, one step before the controller checks
    whether the ledger accounts for the review. A recurrence and a new finding
    became the same thing to every check downstream, which is how a reviewer
    saying a repair is still not demonstrated could sit beside a RESOLVED
    ledger entry with nothing to notice.

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
    # C02-F04. Filled from the reparse when there is one, and applied at the
    # return below so the classification every later check reads is the
    # reviewer's rather than the transcription's.
    raw_kinds: dict[str, str | None] | None = None

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
            structured = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CannotCalculate(f"{cycle_dir.name}/findings.json is not valid "
                                  f"JSON: {e}")
        # C03-F01. Read before the reparse, because the reparse needs it. The
        # runner records the grammar each cycle was parsed with, and this used
        # to reparse with today's instead, so amending the grammar changed what
        # a completed review meant. Codex: "a completed review's interpretation
        # depends on today's schema."
        #
        # The compatibility path is explicit and bounded: a cycle recorded
        # before the field existed carries no grammar, and only that case falls
        # back to the live schema. It is the same distinction C02-F03 draws, in
        # the one place left that was still reading the present tense.
        _grammar = structured.get("finding_id_grammar")
        try:
            import findings_format
            parsed, problems = findings_format.extract(
                raw.read_text(encoding="utf-8", errors="replace"), _grammar)
        except Exception as e:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review cannot be reparsed, so the "
                f"structured result cannot be checked against it: {e}")
        if problems:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review no longer parses "
                "deterministically:\n  " + "\n  ".join(problems))
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

        # C02-F04, raised again by cycle 03. Identifiers matched and the
        # classification did not have to. Codex: "removing kind, or changing it
        # to finding, in the structured entry leaves the raw recurrence and
        # identifiers unchanged. Reconciliation passes, but the reopening guard
        # skips the entry."
        #
        # So the classification comes from the reparse below, not from the
        # structured copy, and a structured copy that disagrees is refused
        # rather than overruled quietly. Overruling would be the better outcome
        # by accident: it would mean the loop is right while the record it
        # publishes says something else, and a reader of findings.json would be
        # misled in exactly the way the ledger exists to prevent.
        raw_kinds = {f["id"]: f.get("kind") for f in parsed}
        _mismatch = [
            f"{f['id']}: raw says {raw_kinds.get(f['id'])!r}, "
            f"findings.json says {f.get('kind')!r}"
            for f in structured.get("findings", [])
            if isinstance(f, dict) and f.get("id") in raw_kinds
            and f.get("kind") is not None
            and f.get("kind") != raw_kinds.get(f["id"])]
        if _mismatch:
            raise CannotCalculate(
                f"{cycle_dir.name}: findings.json classifies findings "
                "differently from the review it\n  was extracted from:\n    "
                + "\n    ".join(_mismatch) +
                "\n\n  A recurrence recorded as a new finding is a repair the "
                "loop stops checking,\n  and a new finding recorded as a "
                "recurrence is a defect with somebody else's\n  history. "
                "Re-record the cycle rather than editing this file.")

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
    out = [f for f in items if isinstance(f, dict) and "id" in f]

    # C02-F04. Codex also asked for "explicit handling for older entries
    # lacking kind". They are filled from the reparse, which is sound because
    # the raw review is the authority and it has just been read; and when there
    # is no raw to reparse the entry keeps whatever it has, which for a record
    # written before the field existed is nothing. That is the honest state: not
    # a recurrence, not a finding, and the reopening guard treats an absent
    # classification as absent rather than as either.
    if raw_kinds is not None:
        for f in out:
            if f.get("id") in raw_kinds:
                f["kind"] = raw_kinds[f["id"]]
    return out


def authoritative_findings(cycle_dir: Path) -> list[str]:
    """The finding IDs, in order.

    A view over `authoritative_items` rather than a second reader, because two
    readers of one file is how the two drift apart, which is the shape seven of
    cycle 01's eight findings had.
    """
    return [f["id"] for f in authoritative_items(cycle_dir)]


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

    MAX_4_REACHED is not among the outcomes an authorization can clear. One
    naming it is still readable and still recorded, and the controller says out
    loud that it is not being honoured, rather than dropping it without comment.
    See UNCLEARABLE.
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
        # D04-F01's rule, applied here too. `str(None)` is "None", which is
        # not empty, so every one of these checks accepted a JSON null. An
        # authorization with a null authorized_by passed the check that
        # exists to stop an unattributed one. The reviewer found this in
        # authority.py; it was in this file as well, which is why the repair
        # went to the rule rather than the three fields it named.
        #
        # after_valid_cycle is a number, so it is checked separately: a
        # string check on an integer would reject every valid record.
        missing = [k for k in ("outcome", "authorized_by", "reason")
                   if not authority.text(a, k)]
        if not isinstance(a.get("after_valid_cycle"), int):
            missing.insert(0, "after_valid_cycle")
        if missing:
            raise CannotCalculate(
                f"authorization {i} is missing {', '.join(missing)}.\n"
                "  An authorization to continue past a mandatory exit has to say "
                "which exit,\n  at which boundary, on whose authority, and why. "
                "Any of those blank and it\n  is not a recorded human transition, "
                "it is a switch the loop turned off for itself.")
        # A loop authorization does NOT yet require a source saying where it
        # was given, and a capture supersession does. That asymmetry is
        # deliberate for now and it is the wrong way round, since continuing
        # past a mandatory exit is the larger decision of the two.
        #
        # Alex Zamurko asked on 9 October 2026 that an authorisation be
        # verifiable rather than resting on a typed name. The requirement was
        # added here the same evening and reverted within the hour: it broke
        # the authorization fixtures in four suites, and at half past ten
        # after an eight-hour day, fixing four suites' fixtures is how a
        # careful change becomes a careless one. The capture-supersession half
        # he actually described is in authority.py and stands.
        #
        # Backlog, and not a long job with a clear head: add the same `source`
        # requirement here, and update the fixtures in test_ledger.py,
        # test_interfaces.py and test_run_review.py to carry one. The
        # authorization that will clear BOOTSTRAP-003's stall already has a
        # source block written, in specs/pending-authorization-cycle-04.json,
        # so the record will be checkable even while the code does not insist
        # on it.
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
    # SELF-F01, third pass. The approval package needs the reconstructed state
    # of each finding at the governing boundary, and had been reading the
    # `state` field cached in the ledger instead. BOOTSTRAP-003 cycle 02:
    # invalidate the cycle carrying a demonstration, leave the stale RESOLVED
    # in place, and the package reports "none unresolved, one resolved" while
    # this controller says OPEN and CONTINUE.
    #
    # A flag rather than a second computation in the package. The boundary walk
    # is long and exit order is load-bearing; a copy of it elsewhere would be
    # free to disagree, which is the defect class this layer keeps finding in
    # itself. This prints what the walk already produced, in a form a caller
    # can read without parsing prose.
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print the governing boundary and its §6 sets as "
                         "JSON, for callers that must not restate the rule. "
                         "Exits non-zero exactly as the ordinary run does.")
    a = ap.parse_args(argv[1:])
    try:
        return _run(a)
    except (CannotCalculate, cycle_projection.UnknownEvent) as e:
        # B03-F01, first half. replay() refuses an event it has no transition
        # for, which is right: silently skipping one would make the state a
        # function of whatever this version happens to recognise. But the
        # refusal escaped main() as a traceback, so the controller exited 1 with
        # no LOOP_STATUS, and the runner's check read that as neither terminal
        # nor undeterminable and opened the next cycle.
        #
        # Translated here so the operator gets the reason rather than a stack
        # trace, and so the exit code says "cannot calculate" rather than
        # "crashed". The runner refuses on any non-zero exit regardless, because
        # a caller that relies on this translation existing fails open the
        # moment a new exception type appears above it.
        e = (CannotCalculate(f"the ledger contains an event replay has no "
                             f"transition for: {e}")
             if isinstance(e, cycle_projection.UnknownEvent) else e)
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
        # B01-F14, the half cycle 04 found still open. This returned
        # ("UNKNOWN", "") and UNKNOWN matched neither branch in main: not
        # DEVELOPMENT, so no refusal and no label; not PROTOCOL, so the metadata
        # check below never ran. The outcome printed with no qualification at
        # all.
        #
        # Codex: removing mc1_enforcement from run.json exits 2, and removing
        # run.json entirely exits 0 with CONVERGED. Taking away one field
        # stopped it and taking away everything waved it through, which is the
        # shape of a check that guards the careful mistake and not the careless
        # one.
        #
        # There is no labelled fallback here. Labelling this "development
        # evidence" would itself be a claim about a run we cannot read, and the
        # honest statement is that we do not know what this is.
        raise CannotCalculate(
            f"there is no {run_json.name} beside this review, so what kind of "
            f"run it belongs to\n  cannot be established:\n    {run_json}\n\n"
            "  A loop state is an outcome about a run. Without the run's own "
            "record there is\n  nothing to say whether its cycles are protocol "
            "cycles or development evidence,\n  and an unlabelled outcome reads "
            "as the stronger of the two.")
    try:
        run = json.loads(run_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"{run_json} is not valid JSON: {e}")
    # C01-F05. This was `"DEVELOPMENT" if label.startswith("EXEMPT") else
    # "PROTOCOL"`, so a missing, empty or unrecognised label meant PROTOCOL.
    # Codex removed only `bootstrap_review` from a development run, left the
    # file and its valid enforcement status, and got an unqualified
    # "LOOP_STATUS: CONVERGED". Deleting the file was refused; deleting the
    # field that says what the file describes promoted the run.
    #
    # Same shape as the mc1 check below and now the same mechanism: the rule
    # is run_pins', shared with the runner and the approval package, and there
    # is no default. Absence is a run whose identity is not established.
    kind, problem = run_pins.run_kind(run)
    if problem:
        raise CannotCalculate(
            f"{run_json} does not establish what kind of run this is, so no "
            f"outcome can be\n  stated about it:\n  " + problem)

    # B01-F14, the half cycle 03 found still open. This function already read
    # run.json and already decided whether the run is authoritative, and then
    # asked nothing about whether the run is fit to produce an outcome. Codex
    # removed mc1_enforcement from a normal approved run with a completed valid
    # cycle; this printed an unqualified "LOOP_STATUS: CONVERGED".
    #
    # The rule is run_pins', not a second copy: the runner refuses the same
    # thing at freeze, and two implementations of one requirement is how they
    # come to disagree.
    #
    # Applied to PROTOCOL runs only. A development run's outcome is already
    # labelled as not a protocol result, so refusing it would be refusing
    # something that claims nothing. BOOTSTRAP-001 carries the field as
    # reconstructed and passes either way.
    if kind == run_pins.PROTOCOL:
        problem = run_pins.mc1_enforcement_problem(run)
        if problem:
            raise CannotCalculate(
                f"{run_json} cannot support an authoritative outcome:\n  "
                + problem)

    return kind, str(run.get("bootstrap_review", "")).strip()


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

    def labelled(status: str) -> str:
        """Every LOOP_STATUS this controller emits, carrying its run's kind.

        C02-F11. There are two places a status leaves here, and only one of them
        knew about the label. The other is the early return just below, for a
        run whose cycles all fail MC-2, and under --quiet it printed a bare
        LOOP_STATUS: CONTINUE. So a recognised development run could hand a
        caller an unqualified outcome through the machine interface, which is
        the exact property the label exists to hold.
        #
        The comment further down said the label had to survive the interface
        rather than merely appear in the report, and it was right about the path
        it guarded. It guarded one path. A rule in two places with one copy
        shorter than the other is the shape most of this run's findings have
        had, so this is one function and both callers go through it.
        """
        return (f"LOOP_STATUS: {status}" if kind != "DEVELOPMENT"
                else f"LOOP_STATUS: {status}  [DEVELOPMENT EVIDENCE — "
                     "NOT A PROTOCOL OUTCOME]")

    if not valid:
        # SELF-F04, raised by the BOOTSTRAP-003 cycle 03 reviewer. This return
        # sits far above the --json branch, so a caller that asked for machine
        # output got this paragraph of English under exit 0. The flag exists
        # precisely so that nothing downstream has to parse prose, and on the
        # one path where there is nothing to report it handed over prose.
        #
        # The sets are omitted rather than emitted empty. An empty list reads
        # as "nothing is open", which is the silent zero this layer keeps
        # finding in itself, and it would be indistinguishable from a genuine
        # clean boundary. sets_established says outright that no walk ran, and
        # the normal branch below carries the same field so a caller tests one
        # thing rather than inferring from which keys happen to be present.
        if getattr(a, "as_json", False):
            print(json.dumps({
                "governing_boundary": None,
                "status": "CONTINUE",
                "label": label,
                "valid_cycle_count": 0,
                "sets_established": False,
                "detail": "No valid cycle has been completed, so §6 has "
                          "nothing to measure. No boundary was walked and no "
                          "finding sets exist to report.",
            }, indent=2, sort_keys=True))
            return 0
        lines += ["", labelled("CONTINUE"),
                  "No valid cycle has been completed, so §6 has nothing to measure. "
                  "Repair the evidence and rerun."]
        print("\n".join(lines) if not a.quiet else labelled("CONTINUE"))
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

    # C01-F06. Being a KEY in the ledger is not the same as having a state.
    #
    # The check above asks only whether each reported identifier exists in
    # ledger["findings"]. `sets_at` then rebuilds each finding's state from
    # events in valid cycles, and a finding whose replay returns None enters
    # none of OPEN, RESOLVED or DISPUTED. Nothing reconciled that omission
    # with what the valid reviews actually reported.
    #
    # Codex's two cycles: C01-F01 raised in cycle 1 and recorded RAISED(1);
    # cycle 2 reports it as REPAIR NOT DEMONSTRATED. Both valid, the
    # controller says STALLED. Invalidate only cycle 1's target hash and
    # cycle 2 still carries the recurrence in both its raw and structured
    # review, yet:
    #
    #     cycle-02  1 finding(s): C01-F01
    #     every recorded finding is accounted for in the ledger
    #     OPEN_1 0   DISPUTED_1 0   RESOLVED_1 0
    #     LOOP_STATUS: CONVERGED
    #
    # Ignoring the invalid originating event is required and is not the
    # defect. Treating the surviving valid recurrence as satisfied because a
    # ledger key exists is. A valid reviewer result still reports an
    # unresolved defect, and convergence was derived from its absence.
    #
    # The correction offered two routes: refuse and identify, or define a
    # reconstruction rule that preserves the identifier and the valid review's
    # unresolved result. This takes the first. Inventing a state for a finding
    # whose origin is not authoritative would be this controller deciding what
    # a review found, and "do not infer resolution or zero findings" cuts both
    # ways: inferring OPEN is still inferring.
    # D01-F01, BOOTSTRAP-003 cycle 01. The replay above used to run over
    # `set(valid)`, every valid cycle in the run, while each boundary is
    # computed over `valid[:n]`. So a finding reported by cycle 1's reviewer,
    # whose RAISED event is dated to cycle 2, reached a state here and had none
    # at its own boundary, where it silently left OPEN_1 and the controller
    # reported CONVERGED at a boundary whose reviewer had reported it.
    #
    # The reviewer's fixture: two valid cycles, cycle 1 reporting one finding
    # and cycle 2 asserting zero. With RAISED(1) the controller says STALLED.
    # Moving only that event to RAISED(2), with `cycle_raised: 1` and the
    # reviewer evidence untouched, produced CONVERGED and exit 0.
    #
    # So the replay is limited to the cycles through the reporting boundary,
    # which is the question actually being asked: does this finding have a
    # state established by the cycles that had reported it by then.
    _stateless: list[str] = []
    _seen: set[str] = set()
    for num, d in dirs:
        if num not in valid:
            continue
        _through = {v for v in valid if v <= num}
        for i in authoritative_findings(d):
            if i in _seen:
                continue
            if state_after(ledger["findings"][i], _through) is None:
                _seen.add(i)
                _stateless.append(f"cycle-{num:02d}: {i}")
    if _stateless:
        raise CannotCalculate(
            "findings a valid review reported have no authoritative state:\n  "
            + "\n  ".join(_stateless) +
            "\n\n  Each is in the ledger, so the check above is satisfied, and "
            "none of them\n  reaches OPEN, RESOLVED or DISPUTED when the "
            "history is replayed over the\n  valid cycles. Usually the event "
            "that raised it sits in a cycle that was later\n  invalidated, "
            "leaving a recurrence in a valid cycle with nothing to recur "
            "from.\n\n  The loop state would be computed as though the valid "
            "review had reported\n  nothing, which is how an unresolved "
            "defect becomes CONVERGED. Repair the\n  invalidated cycle's "
            "evidence, or raise the finding in a cycle that counts.")
    lines.append("  and every one of them has a state the cycles that had "
                 "reported it produce")

    # D01-F01's second half, in the reviewer's words: "Refuse contradictory
    # originating-cycle metadata and history rather than allowing a later
    # RAISED event to satisfy an earlier review."
    #
    # An entry carries `cycle_raised` and a RAISED event carrying its own
    # cycle. Nothing compared them, so the fixture above could keep
    # `cycle_raised: 1` while the event said 2 and the file read as coherent.
    # The boundary rule above now refuses that case on its consequences; this
    # refuses it on its face, which is the better error message and does not
    # depend on a cycle happening to report the finding.
    _contradictory: list[str] = []
    for _fid, _entry in sorted(ledger.get("findings", {}).items()):
        _declared = _entry.get("cycle_raised")
        _events = [h.get("cycle") for h in _entry.get("history", [])
                   if h.get("event") == "RAISED"]
        if _declared is None or not _events:
            continue
        if any(c != _declared for c in _events):
            _contradictory.append(
                f"{_fid}: cycle_raised is {_declared}, its RAISED event(s) are "
                f"in {', '.join(str(c) for c in _events)}")
    if _contradictory:
        raise CannotCalculate(
            "a finding's recorded origin disagrees with its own history:\n  "
            + "\n  ".join(_contradictory) +
            "\n\n  One of the two is wrong and this controller cannot tell "
            "which. Taking the event\n  lets a later cycle satisfy an earlier "
            "review; taking the field lets the field\n  assert an origin no "
            "event supports. Correct the ledger rather than choosing here.")
    lines.append("  and none of them was raised in a cycle other than the one "
                 "it records")

    # C02-F04. Having a state is not the same as having the right one.
    #
    # A recurrence is a reviewer saying, of a finding it has seen before, that
    # the repair is still not demonstrated. Alex Zamurko, 9 September 2026,
    # issue 7: such a finding "transitions RESOLVED -> OPEN. The recurrence is
    # recorded as a reopen event with cycle and evidence."
    #
    # The two checks above ask whether the identifier is in the ledger and
    # whether it reaches any state at all. Neither asks whether that state
    # agrees with what the review said about it. So a valid cycle can report
    # REPAIR NOT DEMONSTRATED, the reopen can go unrecorded, and the finding
    # stays RESOLVED. OPEN and DISPUTED are then both empty at that boundary and
    # the loop reports CONVERGED over a defect the review says is still there.
    # Nothing has to be fabricated for this. A transcription step has to be
    # missed, which is the same weight as the omissions the two checks above
    # already refuse.
    #
    # Refused and named rather than inferred. Writing the reopen here would be
    # the controller deciding a finding's state from a document instead of from
    # the ledger, and the stateless check above declined to invent a state in
    # the other direction for the same reason.
    _unreopened: list[str] = []
    for num, d in dirs:
        if num not in valid:
            continue
        upto = {c for c in valid if c <= num}
        for item in authoritative_items(d):
            if item.get("kind") != "recurrence":
                continue
            f = ledger["findings"][item["id"]]
            if state_after(f, upto) == RESOLVED:
                _unreopened.append(f"cycle-{num:02d}: {item['id']}")
    if _unreopened:
        raise CannotCalculate(
            "a valid review reports these repairs as not demonstrated, and the "
            "ledger still\n  holds them RESOLVED at that cycle:\n  "
            + "\n  ".join(_unreopened) +
            "\n\n  Issue 7 of 9 September requires a recurrence to move the "
            "finding RESOLVED ->\n  OPEN, recorded as a reopen event carrying "
            "its cycle and evidence. Without it\n  the boundary sees nothing "
            "open and nothing disputed, and the loop converges\n  over a defect "
            "its own reviewer says is still present. Record the reopen "
            "against\n  the cycle that reported it.")
    lines.append("  and no recurrence is left standing against a RESOLVED "
                 "ledger entry")

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
        if status in UNCLEARABLE:
            # Named, not silently skipped. An authorization sitting in the file
            # with no effect and nothing said about it is how a reader concludes
            # the loop is continuing on an authority it does not have, which is
            # the finding in a quieter form.
            _ignored = cleared_by(auths, n, status)
            if _ignored is not None:
                lines.append(
                    f"        an authorization for {status} at n={n} from "
                    f"{_ignored['authorized_by']} is on record and is NOT "
                    f"honoured")
                lines.append(
                    "        Alex Zamurko, 15 September: the four-valid-cycle "
                    "maximum is an exit, not an obstacle to route around.")
            governing = (n, status, detail, cur, shown)
            break
        auth = cleared_by(auths, n, status)
        if auth is None:
            governing = (n, status, detail, cur, shown)
            break
        lines.append(f"        {status} at n={n} cleared by recorded "
                     f"authorization: {auth['authorized_by']}")
        lines.append(f"        reason: {auth['reason']}")
        overridden.append(f"n={n} {status} (authorized by {auth['authorized_by']})")
        # C01-F02. The ceiling was enforced only in the fallback below, which
        # runs for the LATEST boundary. So with a fifth cycle already on disk,
        # a cleared exit at n=4 was not the latest boundary, fell through, and
        # the walk simply continued to n=5 and took the loop's outcome from a
        # cycle outside the budget.
        #
        # Codex built exactly that: five MC-2-valid cycles, RAISED(1)
        # ACCEPT(1) DEMONSTRATED(5), STALLED cleared by recorded authorization
        # at boundaries 2, 3 and 4. The controller exited 0 reporting
        # VALID_CYCLE_COUNT 5 and LOOP_STATUS CONVERGED, having derived
        # convergence from the fifth-cycle demonstration and never reported
        # the fifth cycle as an unauthorized continuation.
        #
        # "The runner's refusal to create a fifth cycle is useful, but does not
        # repair the controller's handling of already-existing evidence."
        #
        # Clearing an exit says the loop may continue. It does not say there is
        # anywhere left to continue to, and that sentence has to hold at every
        # boundary rather than only the last one.
        if n >= MAX_VALID_CYCLES:
            lines.append(f"        {status} at n={n} was cleared, and the "
                         f"four-valid-cycle ceiling still binds")
            if len(valid) > n:
                lines.append(
                    f"        {len(valid) - n} valid cycle(s) exist beyond "
                    f"n={n} and are NOT evaluated; the budget ends here")
            detail = (
                f"The {status} at n={n} was cleared by a recorded human "
                f"authorization from {auth['authorized_by']}, and the loop "
                f"still ends here.\n"
                f"Reason given: {auth['reason']}\n\n"
                f"{n} valid cycles have been spent and §2 allows "
                f"{MAX_VALID_CYCLES}. An authorization clears one named exit "
                f"at one\nnamed boundary. It does not create a cycle to spend "
                f"it on, and no authorization\nextends the maximum: Alex "
                f"Zamurko, 15 September. Escalate to human review.")
            if len(valid) > n:
                detail += (
                    f"\n\n{len(valid) - n} valid cycle(s) exist beyond this "
                    f"boundary. Nothing in them was evaluated, and no\n"
                    f"authorization on record permits them.")
            governing = (n, "MAX_4_REACHED", detail, cur, shown)
            break
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
            # the next cycle is permitted within the four-valid-cycle budget.
            #
            # It cannot extend that budget. This comment used to say the
            # opposite, that clearing MAX_4_REACHED was a human decision to
            # spend a fifth cycle, and the runner had never agreed to that.
            #
            # B01-F02, the half cycle 04 found still open. Making MAX_4_REACHED
            # unclearable was not enough, because §6 evaluates STALLED BEFORE
            # the budget. A fourth boundary that genuinely stalls reports
            # STALLED, not MAX_4_REACHED, so it never met the unclearable list
            # at all — and clearing it arrived here and became CONTINUE with the
            # budget never consulted. Codex built exactly that: four valid
            # cycles, a stalled fourth, a matching STALLED authorization, and
            # the controller told the operator to open cycle five while the
            # runner refused it.
            #
            # So the ceiling is enforced here, on the way out, rather than
            # trusted to the shape of the exit that happened to be cleared.
            # Clearing an exit says the loop may continue; it does not say there
            # is anywhere left to continue to.
            # The ceiling check that used to sit here has moved into the walk,
            # where it binds at every boundary rather than only at the latest
            # one (C01-F02). `cleared_latest` is now set only for a boundary
            # BELOW the ceiling, because at or above it the walk stops with
            # MAX_4_REACHED and never reaches this fallback. So the branch that
            # re-tested the ceiling here could no longer fire, and a guard that
            # cannot fire reads as protection while providing none.
            _st, _auth = cleared_latest
            status = "CONTINUE"
            detail = (
                f"The {_st} at n={n_latest} was cleared by a recorded human "
                f"authorization from {_auth['authorized_by']}.\n"
                f"Reason given: {_auth['reason']}\n"
                "The loop continues on that authority. Repair the plan, "
                "produce a new version, and\nopen the next cycle with a new "
                "frozen target.")
        governing = (n_latest, status, detail, cur, shown)

    n, status, detail, cur, shown = governing

    # SELF-F01. The same values the report below is built from, handed over
    # before any of it is formatted, so a caller reads the walk's own result
    # rather than a second opinion or a parsed paragraph.
    # Alex Zamurko, 17 October 2026, on the terminal-exit question: "Preserve
    # the historical terminal result, but ensure that an unauthorised
    # continuation prevents downstream consumers from treating it as a valid
    # approval or convergence result. Test this through the actual consumer
    # path."
    #
    # The continuation was reported, in prose, printed after the status line.
    # specs/review/TERMINAL-EXIT-WITH-CYCLES-BEYOND-IT.md said what that meant
    # on 26 September and nobody tested it: the block "is prose under the
    # status line rather than part of the status, so it informs a reader and
    # not a caller." A caller asking for machine output received
    # status CONVERGED and nothing whatever to say the loop had been continued
    # without authority.
    #
    # The same values the prose is built from, computed once here and used by
    # both, so the two cannot drift into disagreeing about the same loop.
    _cont = None
    if status in TERMINAL and n < n_latest:
        _cont = {
            "terminal_at": n,
            "terminal_status": status,
            "cycles_after": [f"cycle-{c:02d}" for c in valid[n:]],
        }

    if getattr(a, "as_json", False):
        print(json.dumps({
            "governing_boundary": n,
            "status": status,
            "label": label,
            "valid_cycle_count": len(valid),
            # null when there is none, rather than absent. An absent key reads
            # as "this version does not report continuations", which is
            # indistinguishable from "there is no continuation" to a caller
            # that tests for presence, and that is the silent zero this layer
            # keeps finding in itself.
            "unauthorized_continuation": _cont,
            # SELF-F04. Carried on both branches so a caller asks one question,
            # "were the sets established", rather than guessing from whether
            # the keys are present. A caller that never looks at it still sees
            # the sets here and no sets on the other branch.
            "sets_established": True,
            "open": sorted(cur[OPEN]),
            "resolved": sorted(cur[RESOLVED]),
            "disputed": sorted(cur[DISPUTED]),
        }, indent=2, sort_keys=True))
        return 0

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

    lines += ["", labelled(status), detail]

    # Alex Zamurko, 28 September 2026, item 6: "Record the stop-time ledger
    # state separately from the terminal reason ... This prevents later ledger
    # changes from obscuring the state that existed when termination occurred."
    #
    # Two states, named apart. The first is the §6 sets at the boundary that
    # governed, which is what the status above means. The second is the ledger
    # replayed over every valid cycle, which is where the findings stand now.
    # Both are correct and they answer different questions, and until this block
    # existed nothing in the output said which one a reader was looking at. That
    # ambiguity is the terminal-exit question: a loop that stopped at n=2 keeps
    # reporting n=2's sets however far the ledger has moved since.
    #
    # Reported rather than written to a file. Persisting a computed state would
    # create a second authority able to disagree with the ledger it came from,
    # and which of the two wins is a ruling nobody has made.
    latest = sets_at(ledger, set(valid))
    lines += ["", f"ledger at the stop boundary, n={n}",
              f"  OPEN      {len(cur[OPEN]):>2}  {fmt(cur[OPEN])}",
              f"  DISPUTED  {len(cur[DISPUTED]):>2}  {fmt(cur[DISPUTED])}",
              f"  RESOLVED  {len(cur[RESOLVED]):>2}  {fmt(cur[RESOLVED])}"]
    if any(latest[k] != cur[k] for k in (OPEN, RESOLVED, DISPUTED)):
        lines += ["", "ledger now, replayed over every valid cycle",
                  f"  OPEN      {len(latest[OPEN]):>2}  {fmt(latest[OPEN])}",
                  f"  DISPUTED  {len(latest[DISPUTED]):>2}  {fmt(latest[DISPUTED])}",
                  f"  RESOLVED  {len(latest[RESOLVED]):>2}  {fmt(latest[RESOLVED])}",
                  "  This differs from the boundary above. The status reports "
                  "the boundary, because",
                  "  that is where the loop stopped. Neither set is wrong. They "
                  "answer different",
                  "  questions, and the difference is the thing worth seeing "
                  "rather than the thing to",
                  "  resolve by picking one."]

    # The cycles that should never have been opened. Reported rather than
    # silently absorbed, because the evidence in them was produced under a loop
    # that had already terminated and no one authorized restarting it.
    if _cont is not None:
        after = _cont["cycles_after"]
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
    if a.quiet:
        # The stop state is deliberately NOT here, and the reason is worth
        # keeping. It was here for one run, carrying four extra lines, and
        # test_interfaces refused: --quiet "prints that line and nothing else",
        # which is how the development label is proven to survive the machine
        # interface. Adding lines would have relaxed a control to fit a change,
        # which is the move this whole review exists to catch.
        #
        # So the stop state lives in the full report, which satisfies item 6 of
        # Alex Zamurko's 28 September list: it asks for the state to be recorded
        # apart from the terminal reason, not for it to travel on this
        # interface. Putting it here as well is a change to the quiet contract
        # and needs asking for rather than assuming.
        print(labelled(status))
    else:
        # `lines` already carries the labelled status, built by the same
        # function. It used to be inserted bare and patched back here by index,
        # which is what let the early return above emit an unlabelled one: the
        # patch only ever reached this path.
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
