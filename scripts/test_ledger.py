#!/usr/bin/env python3
"""Negative controls for the finding ledger and the loop-state controller.

Every refusal in ledger.py and every exit in loop_state.py is demonstrated on a
fixture built to produce exactly that outcome.

The loop controller is the piece where a bug is invisible. A controller that can
never return STALLED simply burns all four cycles every time and nothing looks
wrong, so each exit is shown firing AND shown not firing when it should not.

    python scripts/test_ledger.py

Exit 0 = every expectation held.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# SELF-F16/F20/F25. The Windows console encodes at the locale code page,
# cp1252, and this program holds characters it has no room for. Without
# this the work completes and the print raises UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parent


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")


def make_repo() -> tuple[Path, str]:
    tmp = Path(tempfile.mkdtemp(prefix="ledger-")).resolve()
    (tmp / "scripts").mkdir()
    # run_pins is here because loop_state imports it for the shared
    # run-metadata rule (B01-F14). Without it the controller fails at import,
    # emits no LOOP_STATUS, and every control in this suite that expects an
    # outcome reports the wrong thing. The suite exited 1 at 49 of 73 controls
    # when this list was five names long.
    # authority.py joined this list on 11 October, when loop_state began
    # using its definition of "this field is present" rather than keeping a
    # second copy of the same expression. D04-F01: the two copies had the
    # same defect, so a JSON null satisfied every check meant to require a
    # value, in both files. One definition is the repair; the cost is one
    # more name here, and the fixture said so loudly rather than letting the
    # controls pass without a loop state to measure.
    for n in ("ledger.py", "loop_state.py", "validate_cycle.py",
              "findings_format.py", "cycle_projection.py", "run_pins.py",
              "authority.py"):
        shutil.copy2(SRC / n, tmp / "scripts" / n)
    # The parser reads the canonical Finding ID grammar from the schema, and the
    # controller reparses the raw review, so a fixture without it cannot compute
    # a loop state at all.
    (tmp / "specs").mkdir()
    shutil.copy2(SRC.parent / "specs" / "evidence-schema-v1.0.md",
                 tmp / "specs" / "evidence-schema-v1.0.md")
    # B01-F14, the half cycle 04 found still open. These fixtures had no
    # run.json at all, and every loop control in this suite passed because of
    # the defect they should have caught: run_classification returned UNKNOWN
    # for a missing file, UNKNOWN matched neither branch in main, and the
    # controller printed an unqualified outcome for a run it could not identify.
    #
    # A run directory without run.json is not something the runner can produce.
    # The fixture now looks like what it is meant to represent: an approved
    # protocol run, which also means these controls exercise the PROTOCOL path
    # rather than a gap in it.
    (tmp / "runs" / "T-001").mkdir(parents=True)
    write_lf(tmp / "runs" / "T-001" / "run.json", json.dumps({
        "run_id": "T-001",
        "bootstrap_review": "APPROVED",
        "mc1_enforcement": "CONVENTION_ONLY",
    }, indent=2) + "\n")
    write_lf(tmp / "plan.md", "# plan\n\nbody\n")
    sh("git", "init", "-q", cwd=tmp)
    sh("git", "config", "user.email", "t@t", cwd=tmp)
    sh("git", "config", "user.name", "t", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "fixture", cwd=tmp)
    return tmp, sh("git", "rev-parse", "HEAD", cwd=tmp).stdout.strip()


def make_cycle(root: Path, review: Path, n: int, commit: str, valid: bool = True) -> None:
    """A cycle directory that passes MC-2, or one deliberately broken."""
    c = review / f"cycle-{n:02d}"
    c.mkdir(parents=True)
    target = {
        "review_type": "plan", "run_id": "T-001", "cycle": n,
        "protocol_commit": commit, "protocol_sha256": "2" * 64,
        "spec_sha256": "0" * 64, "frozen_at": "2026-09-08T00:00:00Z",
        "plan_files": [{"path": "plan.md",
                        "sha256": hashlib.sha256((root / "plan.md").read_bytes()).hexdigest()}],
    }
    snap = c / "artifacts" / "plan.md"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_bytes((root / "plan.md").read_bytes())
    write_lf(c / "target.json", json.dumps(target, indent=2))
    digest = hashlib.sha256((c / "target.json").read_bytes()).hexdigest()
    write_lf(c / "target.sha256", digest + "\n")
    write_lf(c / "codex-input.md", f"target {digest}\n")
    write_lf(c / "codex-output-raw.md", "findings\n")
    write_lf(c / "findings.json", json.dumps({
        "schema": "cycle-findings/1", "cycle": n, "count": 0,
        "zero_findings_asserted": True, "findings": [],
    }, indent=2))
    if not valid:
        # Break check 5: a required file is empty.
        write_lf(c / "codex-output-raw.md", "")


def report_recurrence(review: Path, n: int, fid: str) -> None:
    """Make cycle n's review report `fid` as a recurrence, in both files.

    Both, because the controller reparses codex-output-raw.md and requires the
    structured result to match it identifier for identifier. Writing only
    findings.json would fail that check instead of reaching the one under test,
    and the control would be green for the wrong reason.
    """
    c = review / f"cycle-{n:02d}"
    write_lf(c / "codex-output-raw.md",
             f"Finding ID: {fid}\nStatus: REPAIR NOT DEMONSTRATED\n")
    write_lf(c / "findings.json", json.dumps({
        "schema": "cycle-findings/1", "cycle": n, "count": 1,
        "zero_findings_asserted": False,
        "findings": [{"id": fid, "class": None, "kind": "recurrence"}],
    }, indent=2))


def restate_kind(review: Path, n: int, fid: str, kind: str | None) -> None:
    """Rewrite only the structured classification, leaving the raw review alone.

    C02-F04, raised again by cycle 03. Codex asked for exactly this fixture:
    "extend the existing control by changing only the structured classification
    while retaining the raw recurrence, IDs, counts, and capture hashes." The
    raw file is untouched, so every check that compares the two by identifier,
    by count, or by capture digest still passes, and the only thing different is
    what the transcription says the finding is.

    `kind=None` removes the field, which is the shape of a record written before
    the parser assigned one.
    """
    c = review / f"cycle-{n:02d}"
    d = json.loads((c / "findings.json").read_text(encoding="utf-8"))
    for f in d["findings"]:
        if f.get("id") == fid:
            f.pop("kind", None)
            if kind is not None:
                f["kind"] = kind
    write_lf(c / "findings.json", json.dumps(d, indent=2))


# Fixture-validity audit, Alex Zamurko 16 September: "each negative control
# should first establish that its fixture satisfies all prerequisites except the
# single condition it intends to violate."
#
# The failure this closes, twice observed on 17 September. A scenario builds its
# fixture by calling the ledger a few times and ignoring what comes back, then
# asserts a loop state. When those calls started failing — a newly required
# argument, in that instance — the ledger stayed empty, the loop correctly
# reported CONVERGED over nothing, and five controls reported a wrong exit code
# rather than a broken fixture. The controls were pointing at the right defect
# class and naming the wrong defect.
#
# So during fixture construction every ledger call is required to succeed. This
# does not make the fixtures correct; it makes a fixture that failed to build
# say so instead of being quietly asserted over.
_FIXTURE_STRICT = False
_FIXTURE_ERRORS: list[str] = []


def ledger(root: Path, *args: str) -> subprocess.CompletedProcess:
    r = sh(sys.executable, str(root / "scripts" / "ledger.py"), *args, cwd=root)
    if _FIXTURE_STRICT and r.returncode != 0:
        _FIXTURE_ERRORS.append(
            f"{' '.join(args[:2])} exited {r.returncode}: "
            + (r.stderr + r.stdout).strip().splitlines()[0][:160])
    return r


def loop(root: Path, review: Path) -> subprocess.CompletedProcess:
    return sh(sys.executable, str(root / "scripts" / "loop_state.py"),
              "--review", str(review), cwd=root)


def status_of(out: str) -> str:
    for line in out.splitlines():
        if line.startswith("LOOP_STATUS:"):
            return line.split(":", 1)[1].strip()
    return "(none)"


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def fresh():
        root, commit = make_repo()
        made.append(root)
        return root, commit, root / "runs" / "T-001" / "plan-review"

    def expect_refused(label: str, needle: str, run) -> None:
        r = run()
        if r.returncode == 0:
            failures.append(f"{label}: expected refusal, exit 0\n{r.stdout}")
            return
        text = (r.stderr + r.stdout).lower()
        if needle.lower() not in text:
            failures.append(f"{label}: refused for the wrong reason\n"
                            f"  wanted {needle!r}\n  got {text.strip()[:240]}")
            return
        print(f"  [ok] refused: {label}")

    # ---- issue 5, requirements 3 and 4, enforced at gate time ----
    # findings.json is an ordinary file after record, so the invariants have to
    # hold whenever the controller runs, not only when the runner writes.
    print("review-result integrity at gate time")

    def integrity_fixture():
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        make_cycle(root, rev, 1, commit)
        c = rev / "cycle-01"
        write_lf(c / "codex-output-raw.md",
                 "Finding ID: C01-F01\nClass: UNTESTED RULE\n\n"
                 "Finding ID: C01-F02\nClass: WRONG OWNERSHIP\n")
        write_lf(c / "findings.json", json.dumps({
            "schema": "cycle-findings/1", "cycle": 1, "count": 2,
            "zero_findings_asserted": False,
            "findings": [{"id": "C01-F01", "class": "UNTESTED RULE"},
                         {"id": "C01-F02", "class": "WRONG OWNERSHIP"}],
        }, indent=2))
        digest = hashlib.sha256((c / "target.json").read_bytes()).hexdigest()
        write_lf(c / "target.sha256", digest + "\n")
        write_lf(c / "codex-input.md", f"target {digest}\n")
        for fid, kl in (("C01-F01", "UNTESTED RULE"), ("C01-F02", "WRONG OWNERSHIP")):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                   "--id", fid, "--class", kl, "--source", "CODEX_REVIEW")
        return root, rev, c

    root, rev, c = integrity_fixture()
    if loop(root, rev).returncode != 0:
        failures.append("the integrity fixture does not compute a loop state, "
                        "so the two controls below prove nothing")
    else:
        print("  [ok] a consistent raw/structured/ledger chain computes")

    root, rev, c = integrity_fixture()
    d = json.loads((c / "findings.json").read_text(encoding="utf-8"))
    d["findings"] = d["findings"][:1]; d["count"] = 1
    write_lf(c / "findings.json", json.dumps(d, indent=2))
    r = loop(root, rev)
    if r.returncode == 0:
        failures.append("a finding present in the raw review but dropped from "
                        "findings.json still computed a loop state")
    else:
        print("  [ok] refused: raw finding omitted from findings.json")

    root, rev, c = integrity_fixture()
    d = json.loads((c / "findings.json").read_text(encoding="utf-8"))
    d["findings"][0]["id"] = "C01-F99"
    write_lf(c / "findings.json", json.dumps(d, indent=2))
    r = loop(root, rev)
    if r.returncode == 0:
        failures.append("a finding renamed between the raw review and the "
                        "structured record still computed a loop state")
    else:
        print("  [ok] refused: finding id changed between raw review and record")

    # ---- issue 7: recurrence of a previously RESOLVED finding ----
    # Alex Zamurko, 9 September: same persistent ID, RESOLVED -> OPEN, a reopen
    # event with cycle and evidence, no fourth authoritative state, and the
    # controller treats it as an ordinary member of OPEN_n. Before this the
    # ledger refused outright, so a recurrence either got a new identifier —
    # breaking V40 and §6's re-raise detection — or went unrecorded.
    print()
    print("recurrence of a resolved finding")

    def resolved_fixture():
        root, commit, rev = fresh()
        rev.mkdir(parents=True)
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "will fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "2",
               "--id", "C01-F01", "--evidence", "repaired in 02-PLAN.md")
        return root, rev

    root, rev = resolved_fixture()
    r = ledger(root, "reopen", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F01", "--evidence", "recurred in 03-PLAN.md §4")
    data = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
    f = data["findings"].get("C01-F01", {})
    if r.returncode != 0:
        failures.append(f"reopening a recurred finding was refused:\n{r.stderr}{r.stdout}")
    elif f.get("state") != "OPEN":
        failures.append(f"reopen did not move the state to OPEN: {f.get('state')}")
    elif not any(e["event"] == "REOPENED" and e.get("prior_state") == "RESOLVED"
                 for e in f["history"]):
        failures.append("reopen did not record a reopen event carrying the "
                        "prior state")
    elif set(e["state"] for e in f["history"]) - {"OPEN", "RESOLVED", "DISPUTED"}:
        failures.append("reopen introduced a state outside the protocol's three")
    else:
        print("  [ok] recurrence keeps the identifier and moves RESOLVED -> OPEN")

    rootE, revE = resolved_fixture()
    expect_refused("reopen with no evidence", "--evidence is required",
                   lambda: ledger(rootE, "reopen", "--review", str(revE),
                                  "--cycle", "3", "--id", "C01-F01"))

    # Non-recurrence: nothing that was never resolved can be reopened.
    root2, commit2, rev2 = fresh()
    rev2.mkdir(parents=True)
    ledger(root2, "raise", "--review", str(rev2), "--cycle", "1",
           "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    expect_refused("reopen a finding that is still OPEN", "not RESOLVED",
                   lambda: ledger(root2, "reopen", "--review", str(rev2),
                                  "--cycle", "2", "--id", "C01-F01",
                                  "--evidence", "x"))

    root3, rev3 = resolved_fixture()
    expect_refused("recurrence dated before the resolution it undoes",
                   "cannot recur",
                   lambda: ledger(root3, "reopen", "--review", str(rev3),
                                  "--cycle", "2", "--id", "C01-F01",
                                  "--evidence", "x"))

    # ---- B02-F03: one grammar, consumed rather than copied ----
    # Codex: "The schema permits zero to two capital prefix letters. The parser
    # accepted `AB02-F01` with class UNTESTED RULE without problems. The ledger
    # rejected the same identifier because its independently hard-coded
    # expression permits at most one capital letter." A finding valid at capture
    # could not be entered unchanged, which is the divergence the single-grammar
    # ruling exists to close — inside the module built to close it.
    print()
    print("one Finding ID grammar, parser and ledger (B02-F03)")

    import importlib.util as _iu2
    _sp2 = _iu2.spec_from_file_location("_ff2", SRC / "findings_format.py")
    _ff2 = _iu2.module_from_spec(_sp2); _sp2.loader.exec_module(_ff2)
    _grammar = _ff2.canonical_id_grammar()

    rootG, commitG, revG = fresh()
    revG.mkdir(parents=True)

    # Every prefix length the schema allows, end to end: parsed, then recorded.
    for fid, label in (("02-F01", "no prefix"),
                       ("B02-F01", "one letter"),
                       ("AB02-F01", "two letters")):
        parsed, probs = _ff2.extract(
            f"Finding ID: {fid}\nClass: UNTESTED RULE\nEvidence: x\n")
        if probs or [p["id"] for p in parsed] != [fid]:
            failures.append(f"the parser rejected {fid} ({label}): {probs}")
            continue
        r = ledger(rootG, "raise", "--review", str(revG), "--cycle", "2",
                   "--id", fid, "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        if r.returncode != 0:
            failures.append(
                f"the parser accepted {fid} ({label}) and the ledger refused "
                f"it; a finding valid at capture cannot be recorded\n{r.stderr}")
        else:
            print(f"  [ok] {fid} ({label}) parses and records unchanged")

    # An identifier outside the grammar is still refused, and for that reason.
    expect_refused("an identifier outside the canonical grammar",
                   "canonical grammar",
                   lambda: ledger(rootG, "raise", "--review", str(revG),
                                  "--cycle", "2", "--id", "ABC02-F01",
                                  "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW"))

    # The cycle rule still holds, and holds independently of prefix length —
    # which is the part that made the ledger keep its own pattern.
    expect_refused("a two-letter identifier whose cycle digits disagree",
                   "declares cycle",
                   lambda: ledger(rootG, "raise", "--review", str(revG),
                                  "--cycle", "3", "--id", "AB02-F09",
                                  "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW"))

    # And the ledger reads the grammar rather than carrying a copy: with the
    # declaration gone it refuses outright instead of falling back.
    rootH, commitH, revH = fresh()
    revH.mkdir(parents=True)
    schemaH = rootH / "specs" / "evidence-schema-v1.0.md"
    write_lf(schemaH, schemaH.read_text(encoding="utf-8")
             .replace("FINDING_ID_GRAMMAR", "REMOVED_GRAMMAR"))
    expect_refused("the ledger with no canonical grammar to read",
                   "cannot be read",
                   lambda: ledger(rootH, "raise", "--review", str(revH),
                                  "--cycle", "1", "--id", "C01-F01",
                                  "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW"))

    # ---- B01-F12: no event may predate the finding it acts on ----
    # "Require every ACCEPT, RESOLVE, or DISPUTE event to occur in the raising
    # cycle or a later valid cycle. Reject any earlier-dated event." Nothing
    # checked this, so a finding raised in cycle 3 could be accepted in cycle 1
    # and resolved in cycle 2, and §6 would measure those sets at boundaries
    # where the finding did not yet exist.
    print()
    print("events cannot predate the finding they act on (B01-F12)")

    rootF, commitF, revF = fresh()
    revF.mkdir(parents=True)
    ledger(rootF, "raise", "--review", str(revF), "--cycle", "3",
           "--id", "C03-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")

    expect_refused("ACCEPT dated before the raising cycle", "could not have happened",
                   lambda: ledger(rootF, "respond", "--review", str(revF),
                                  "--cycle", "1", "--id", "C03-F01",
                                  "--disposition", "ACCEPT", "--note", "early"))
    expect_refused("REJECT_WITH_REASON dated before the raising cycle",
                   "could not have happened",
                   lambda: ledger(rootF, "respond", "--review", str(revF),
                                  "--cycle", "2", "--id", "C03-F01",
                                  "--disposition", "REJECT_WITH_REASON",
                                  "--note", "disagree",
                                  "--spec-evidence", "§4 does not apply"))
    expect_refused("RESOLVE dated before the raising cycle",
                   "could not have happened",
                   lambda: ledger(rootF, "resolve", "--review", str(revF),
                                  "--cycle", "1", "--id", "C03-F01",
                                  "--evidence", "early"))

    # The same cycle as the raise is permitted: §5 places the disposition in the
    # cycle the finding was raised in. Only earlier is impossible.
    r = ledger(rootF, "respond", "--review", str(revF), "--cycle", "3",
               "--id", "C03-F01", "--disposition", "ACCEPT", "--note", "fix")
    if r.returncode != 0:
        failures.append(f"an ACCEPT in the raising cycle was refused:\n"
                        f"{r.stderr}{r.stdout}")
    else:
        print("  [ok] a disposition in the raising cycle itself is permitted")

    # The duplicate-id refusal must now point at reopen rather than instruct a
    # rename, which is what B01-F13 was about.
    root4, rev4 = resolved_fixture()
    r = ledger(root4, "raise", "--review", str(rev4), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    if r.returncode == 0:
        failures.append("a duplicate identifier was accepted")
    elif "reopen" not in (r.stdout + r.stderr):
        failures.append("the duplicate-id refusal does not point at reopen; it "
                        "still implies a recurrence needs a new identifier")
    else:
        print("  [ok] the duplicate-id refusal points at reopen, not a rename")

    print()
    print("ledger")

    # ---- happy path ----
    root, commit, rev = fresh()
    rev.mkdir(parents=True)
    r = ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE", "--requirement", "R-B7",
               "--source", "CODEX_REVIEW")
    if r.returncode != 0:
        failures.append(f"raise failed:\n{r.stderr}{r.stdout}")
    else:
        print("  [ok] raise records a finding as OPEN")

    r = ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "will fix")
    data = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
    if data["findings"]["C01-F01"]["state"] != "OPEN":
        failures.append("ACCEPT changed the state; §5 resolves only once the repair "
                        "is demonstrated in the next review target")
    else:
        print("  [ok] ACCEPT records a disposition and leaves the state OPEN")

    r = ledger(root, "resolve", "--review", str(rev), "--cycle", "2",
               "--id", "C01-F01", "--evidence", "repaired in 02-PLAN.md")
    data = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
    if r.returncode != 0 or data["findings"]["C01-F01"]["state"] != "RESOLVED":
        failures.append(f"resolve from a later cycle should work:\n{r.stderr}{r.stdout}")
    else:
        print("  [ok] resolve from a later cycle moves OPEN -> RESOLVED")

    # ---- refusals ----
    expect_refused("duplicate finding id", "already exists", lambda: ledger(
        root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
        "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW"))

    expect_refused("id declares a different cycle", "persistent", lambda: ledger(
        root, "raise", "--review", str(rev), "--cycle", "2", "--id", "C09-F01",
        "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW"))

    expect_refused("respond to a finding never raised", "no such finding", lambda: ledger(
        root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F99",
        "--disposition", "ACCEPT"))

    # ---- provenance, B02-F11 ----
    # Alex Zamurko's ruling of 16 September. The register is complete only if
    # implementer-found defects can enter it, and honest only if they cannot
    # enter it wearing a reviewer's identifier.
    expect_refused("a source outside the three", "must be one of the three",
                   lambda: ledger(
                       root, "raise", "--review", str(rev), "--cycle", "1",
                       "--id", "C01-F07", "--class", "UNTESTED RULE",
                       "--source", "CODEX"))

    # Omission is refused by argparse rather than by cmd_raise, so it exits 2
    # and not 1. Checked separately for that reason: a control asserting exit 1
    # here would pass on the day someone gives --source a default, which is the
    # change this control exists to prevent.
    r_nosrc = ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                     "--id", "C01-F08", "--class", "UNTESTED RULE")
    if r_nosrc.returncode == 0:
        failures.append(
            "raise succeeded with no --source. A finding whose provenance was "
            "never stated is indistinguishable from a reviewer finding, which "
            "is what the ruling refuses.")
    else:
        print("  [ok] refused: a finding raised without saying who found it")

    r_self = ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                    "--id", "C01-F09", "--class", "UNTESTED RULE",
                    "--source", "IMPLEMENTER_SELF_FOUND")
    d_self = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
    rec = d_self["findings"].get("C01-F09", {})
    if r_self.returncode != 0:
        failures.append(f"a self-found defect was refused entry:\n{r_self.stderr}")
    elif rec.get("source") != "IMPLEMENTER_SELF_FOUND":
        failures.append("a self-found defect was recorded without its source, "
                        f"got {rec.get('source')!r}")
    elif rec.get("state") != "OPEN":
        failures.append("a self-found defect did not get ordinary lifecycle "
                        f"state, got {rec.get('state')!r}")
    else:
        print("  [ok] a self-found defect enters the ledger, labelled, with "
              "ordinary state")

    r_show = ledger(root, "show", "--review", str(rev))
    if "IMPLEMENTER_SELF_FOUND" not in (r_show.stdout + r_show.stderr):
        failures.append(
            "show does not surface IMPLEMENTER_SELF_FOUND. A provenance "
            "recorded in the file and absent from the report leaves the "
            "distinction where nobody reads it, which is the condition "
            "B02-F11 named.")
    else:
        print("  [ok] show names the provenance of a self-found defect")

    # ---- repair status is descriptive, and the loop cannot see it ----
    # Alex Zamurko, 17 September: "External demonstration may update descriptive
    # repair/closure metadata, but must never masquerade as a §5 RESOLVED
    # transition in the original ledger." And: neither field "may affect OPEN_n,
    # convergence, stall, or cycle counting."
    #
    # A comment asserting non-interference is the kind of control this review
    # keeps rejecting. This one measures it: the authoritative outputs are
    # captured, every non-authoritative field is then written onto every
    # finding, and the outputs are required to be identical afterwards.
    rootN, commitN, revN = fresh()
    revN.mkdir(parents=True)
    for n in (1, 2):
        make_cycle(rootN, revN, n, commitN)
    ledger(rootN, "raise", "--review", str(revN), "--cycle", "1",
           "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(rootN, "raise", "--review", str(revN), "--cycle", "1",
           "--id", "C01-F02", "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW")
    ledger(rootN, "respond", "--review", str(revN), "--cycle", "1",
           "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "will fix")
    ledger(rootN, "resolve", "--review", str(revN), "--cycle", "2",
           "--id", "C01-F01", "--evidence", "demonstrated")

    before_loop = loop(rootN, revN)
    before_snap = ledger(rootN, "show", "--review", str(revN), "--cycle", "2")

    r_rs = ledger(rootN, "repair-status", "--review", str(revN), "--id", "C01-F02",
                  "--status", "EXTERNALLY_DEMONSTRATED",
                  "--verification-run", "BOOTSTRAP-002",
                  "--closure-record", "bootstrap-review/decision.json")
    dN = json.loads((revN / "ledger.json").read_text(encoding="utf-8"))
    if r_rs.returncode != 0:
        failures.append(f"repair-status was refused:\n{r_rs.stderr}{r_rs.stdout}")
    elif dN["findings"]["C01-F02"]["state"] != "OPEN":
        failures.append(
            "repair-status moved the finding out of OPEN. It is descriptive "
            "metadata and must never be a second route to RESOLVED.")
    else:
        print("  [ok] repair-status records EXTERNALLY_DEMONSTRATED and leaves "
              "the state OPEN")

    after_loop = loop(rootN, revN)
    after_snap = ledger(rootN, "show", "--review", str(revN), "--cycle", "2")
    if (before_loop.stdout, before_loop.returncode) != \
            (after_loop.stdout, after_loop.returncode):
        failures.append(
            "the loop controller's output changed once repair status was "
            "recorded. OPEN_n, convergence, stall and cycle counting must not "
            "see this field.\n      before: "
            f"{before_loop.stdout.strip()[:200]}\n      after:  "
            f"{after_loop.stdout.strip()[:200]}")
    elif before_snap.stdout != after_snap.stdout:
        failures.append(
            "the per-cycle state snapshot changed once repair status was "
            "recorded; the field is reaching the state machine.")
    else:
        print("  [ok] recording repair status changes no authoritative output")

    expect_refused("EXTERNALLY_DEMONSTRATED with no verification run",
                   "requires --verification-run", lambda: ledger(
                       rootN, "repair-status", "--review", str(revN),
                       "--id", "C01-F02", "--status", "EXTERNALLY_DEMONSTRATED"))

    expect_refused("a repair status outside the three", "one of the three",
                   lambda: ledger(
                       rootN, "repair-status", "--review", str(revN),
                       "--id", "C01-F02", "--status", "RESOLVED"))

    expect_refused("respond to a RESOLVED finding", "resolved", lambda: ledger(
        root, "respond", "--review", str(rev), "--cycle", "3", "--id", "C01-F01",
        "--disposition", "ACCEPT"))

    root2, commit2, rev2 = fresh()
    rev2.mkdir(parents=True)
    ledger(root2, "raise", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")

    expect_refused("REJECT_WITH_REASON with no reason", "requires --note", lambda: ledger(
        root2, "respond", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
        "--disposition", "REJECT_WITH_REASON"))

    # §5 names Reason and Spec evidence as two fields. A rejection carrying only
    # a reason rests on the implementing agent's reading of the spec rather than
    # on the spec, and the human adjudicating the dispute gets half of what the
    # protocol says they should have.
    expect_refused("REJECT_WITH_REASON with a reason but no spec evidence",
                   "requires --spec-evidence", lambda: ledger(
        root2, "respond", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
        "--disposition", "REJECT_WITH_REASON", "--note", "I disagree"))

    # Whitespace is not evidence.
    expect_refused("spec evidence that is only whitespace",
                   "requires --spec-evidence", lambda: ledger(
        root2, "respond", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
        "--disposition", "REJECT_WITH_REASON", "--note", "I disagree",
        "--spec-evidence", "   "))

    expect_refused("resolve with no prior ACCEPT", "no accept", lambda: ledger(
        root2, "resolve", "--review", str(rev2), "--cycle", "2", "--id", "C01-F01",
        "--evidence", "x"))

    ledger(root2, "respond", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "will fix")

    expect_refused("resolve in the same cycle as the ACCEPT", "next review target",
                   lambda: ledger(root2, "resolve", "--review", str(rev2), "--cycle", "1",
                                  "--id", "C01-F01", "--evidence", "x"))

    expect_refused("resolve with no evidence", "--evidence is required", lambda: ledger(
        root2, "resolve", "--review", str(rev2), "--cycle", "2", "--id", "C01-F01"))

    expect_refused("two dispositions in one cycle", "exactly one", lambda: ledger(
        root2, "respond", "--review", str(rev2), "--cycle", "1", "--id", "C01-F01",
        "--disposition", "REJECT_WITH_REASON", "--note", "actually no"))

    root3, commit3, rev3 = fresh()
    rev3.mkdir(parents=True)
    ledger(root3, "raise", "--review", str(rev3), "--cycle", "1", "--id", "C01-F01",
           "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW")
    ledger(root3, "respond", "--review", str(rev3), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "REJECT_WITH_REASON", "--note", "spec says otherwise",
           "--spec-evidence", "§5: ACCEPT does not resolve")
    data = json.loads((rev3 / "ledger.json").read_text(encoding="utf-8"))
    if data["findings"]["C01-F01"]["state"] != "DISPUTED":
        failures.append("REJECT_WITH_REASON did not produce DISPUTED")
    else:
        print("  [ok] REJECT_WITH_REASON moves OPEN -> DISPUTED")

    expect_refused("respond to a DISPUTED finding", "human adjudication", lambda: ledger(
        root3, "respond", "--review", str(rev3), "--cycle", "2", "--id", "C01-F01",
        "--disposition", "ACCEPT"))

    # ---- OUT OF VOCABULARY is a diagnostic, not a finding ----
    # Ruled 8 September 2026: kept in the review prompts, but with no Finding ID,
    # never in findings.json, never in a state, no effect on loop state. The
    # prompts say so; these show the ledger enforces it, which is the difference
    # between a rule and a request.
    root4, commit4, rev4 = fresh()
    rev4.mkdir(parents=True)

    expect_refused("raise OUT OF VOCABULARY as a finding", "not a finding",
                   lambda: ledger(root4, "raise", "--review", str(rev4),
                                  "--cycle", "1", "--id", "C01-F01",
                                  "--class", "OUT OF VOCABULARY",
                                  "--source", "CODEX_REVIEW"))

    # Case and spacing must not be a way around it. A refusal that a different
    # capitalisation defeats is a refusal in appearance only.
    expect_refused("raise it in lower case", "not a finding",
                   lambda: ledger(root4, "raise", "--review", str(rev4),
                                  "--cycle", "1", "--id", "C01-F02",
                                  "--class", "out of vocabulary",
                                  "--source", "CODEX_REVIEW"))

    expect_refused("raise it with surrounding whitespace", "not a finding",
                   lambda: ledger(root4, "raise", "--review", str(rev4),
                                  "--cycle", "1", "--id", "C01-F03",
                                  "--class", "  OUT OF VOCABULARY  ",
                                  "--source", "CODEX_REVIEW"))

    # And nothing was written on the way to being refused.
    if (rev4 / "findings.json").is_file():
        data = json.loads((rev4 / "ledger.json").read_text(encoding="utf-8"))
        if data.get("findings"):
            failures.append("a refused OUT OF VOCABULARY class still left findings "
                            f"in the ledger: {sorted(data['findings'])}")
        else:
            print("  [ok] three refusals left findings.json empty")
    else:
        print("  [ok] three refusals wrote no findings.json at all")

    # The six must still be accepted, or the check above is just a broken raise.
    for i, klass in enumerate(("MISSING REQUIREMENT", "WRONG OWNERSHIP",
                               "NONDETERMINISTIC WHERE D POSSIBLE",
                               "SEMANTIC STEP TOO BROAD", "UNTESTED RULE",
                               "CONTRADICTORY IMPLEMENTATION MAPPING"), start=10):
        r = ledger(root4, "raise", "--review", str(rev4), "--cycle", "1",
                   "--id", f"C01-F{i}", "--class", klass,
                   "--source", "CODEX_REVIEW")
        if r.returncode != 0:
            failures.append(f"the ledger refused a legitimate class {klass!r}:\n"
                            f"{r.stderr}{r.stdout}")
            break
    else:
        print("  [ok] all six legitimate classes still accepted")

    # An unknown class still refuses, with the general message rather than the
    # OUT OF VOCABULARY one. Removing argparse's `choices` moved this check into
    # the code, so it needs its own control.
    expect_refused("an invented seventh class", "one of the six",
                   lambda: ledger(root4, "raise", "--review", str(rev4),
                                  "--cycle", "1", "--id", "C01-F20",
                                  "--class", "STYLE NIT",
                                  "--source", "CODEX_REVIEW"))

    expect_refused("resolve a DISPUTED finding", "human adjudication", lambda: ledger(
        root3, "resolve", "--review", str(rev3), "--cycle", "2", "--id", "C01-F01",
        "--evidence", "x"))

    # ---- B01-F11: one projection for authority and for loop arithmetic ----
    # "The ledger authorizes transitions from its unfiltered stored state and
    # history, while the controller filters events by valid cycles." Decision G
    # was implemented in the controller alone, which was exploitable in both
    # directions. Both are proved here, and both are proved on the ledger side:
    # the controller was already correct, so a control that only asked the
    # controller would pass with the repair removed.
    print()
    print("invalid cycles neither authorize nor block (B01-F11)")

    def review_with(cycles: dict[int, bool]):
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        for n in sorted(cycles):
            make_cycle(root, rev, n, commit, valid=cycles[n])
        return root, rev

    # Direction one: an ACCEPT recorded in a cycle that fails MC-2 must not
    # satisfy the precondition for closing the finding. Before the projection it
    # did, so an invalid acceptance could support a resolution the controller
    # then counted as real.
    root, rev = review_with({1: True, 2: False, 3: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "accepted in a cycle that failed")
    expect_refused(
        "an ACCEPT in an invalid cycle does not authorize a resolution",
        "has no ACCEPT",
        lambda: ledger(root, "resolve", "--review", str(rev), "--cycle", "3",
                       "--id", "C01-F01", "--evidence", "done"))

    # The refusal has to be legible: the operator can see an ACCEPT sitting in
    # the history, so the message must say which events were disregarded.
    r = ledger(root, "resolve", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F01", "--evidence", "done")
    if "cycle 02 ACCEPT" in (r.stderr + r.stdout):
        print("  [ok] the refusal names the disregarded event")
    else:
        failures.append("the refusal does not name the disregarded ACCEPT\n"
                        + r.stderr + r.stdout)

    # And it must still be in the ledger as evidence, marked rather than erased.
    r = ledger(root, "show", "--review", str(rev))
    if "ACCEPT" in r.stdout and "[no authority]" in r.stdout:
        print("  [ok] the disregarded event is preserved and marked in show")
    else:
        failures.append("the invalid-cycle event was not preserved and marked\n"
                        + r.stdout)

    # ---- B01-F11 as cycle 02 found it still broken ----
    # The first repair filtered which events were MEMBERS of the projection and
    # then copied the state the surviving event recorded. Codex's reproduction:
    # RAISED in valid 01, ACCEPT in then-valid 02, DEMONSTRATED in valid 03.
    # Invalidate 02 afterwards and `show` marked the ACCEPT as having no
    # authority while the finding stayed RESOLVED and the controller returned
    # CONVERGED. A resolution survived on an acceptance that had been withdrawn.
    root, rev = review_with({1: True, 2: True, 3: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "accepted while cycle 2 passed")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "3", "--id", "C01-F01",
           "--evidence", "demonstrated in cycle 3")
    # Everything so far is legitimate. Now the acceptance's cycle fails the gate.
    write_lf(rev / "cycle-02" / "codex-output-raw.md", "")

    r = ledger(root, "show", "--review", str(rev))
    if "[RESOLVED]" in r.stdout:
        failures.append(
            "the finding is still RESOLVED after the ACCEPT its resolution "
            "depended on was invalidated; state is being copied from the last "
            f"retained event rather than replayed\n{r.stdout}")
    elif "[OPEN]" not in r.stdout:
        failures.append(f"unexpected state after invalidating the prerequisite\n"
                        f"{r.stdout}")
    else:
        print("  [ok] invalidating an ACCEPT withdraws the resolution that "
              "rested on it")

    r = loop(root, rev)
    if status_of(r.stdout) == "CONVERGED":
        failures.append("the controller still reports CONVERGED on a resolution "
                        "whose acceptance was invalidated")
    else:
        print(f"  [ok] the controller does not converge on it "
              f"({status_of(r.stdout)})")

    # And the refusal has to explain itself: the operator can see a
    # DEMONSTRATED in the history and needs to know why it did not take.
    r = ledger(root, "reopen", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F01", "--evidence", "x")
    if "never took effect" not in (r.stderr + r.stdout):
        failures.append(f"the refusal does not say which event failed to take "
                        f"effect\n{r.stderr}{r.stdout}")
    else:
        print("  [ok] the refusal names the transition that never took effect")

    # An event naming a cycle that does not exist cannot authorize anything.
    #
    # This control used to accept in cycle 99 and resolve in cycle 99. Codex
    # took it apart in cycle 03: it replaced the membership rule with
    # unconditional True and the control still passed, because resolution was
    # refused for accept-and-resolve-being-the-same-cycle, which has nothing to
    # do with the cycle existing. Both branches printed [ok] besides, so it
    # reported success whatever happened. It was decorative.
    #
    # Rebuilt as the case Codex actually reproduced: cycles 01 and 03 exist and
    # pass, cycle 02 never did. RAISED in 01, ACCEPT in the gap, resolution from
    # a LATER cycle. The ordering is legal, the evidence is present, and the
    # only thing wrong is that the acceptance sits in a cycle that never
    # happened. Nothing but the membership rule can refuse this.
    root, rev = review_with({1: True, 3: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    _acc = ledger(root, "respond", "--review", str(rev), "--cycle", "2",
                  "--id", "C01-F01", "--disposition", "ACCEPT",
                  "--note", "recorded against a cycle that never existed")
    if _acc.returncode != 0:
        # Storing it is allowed; only its authority is in question. If the write
        # is refused this control cannot reach what it exists to test.
        failures.append(f"fixture: the ACCEPT could not be recorded at all, so "
                        f"the resolution below proves nothing\n{_acc.stderr}")
    else:
        _res = ledger(root, "resolve", "--review", str(rev), "--cycle", "3",
                      "--id", "C01-F01", "--evidence", "repaired")
        _blob = (_res.stderr + _res.stdout).lower()
        if _res.returncode == 0:
            failures.append(
                "a finding was resolved on an acceptance recorded against cycle "
                "02, which never existed. The ledger would report RESOLVED while "
                "the controller, which counts only cycles that exist, keeps it "
                "OPEN. That disagreement is B01-F11.")
        elif "no accept" not in _blob:
            failures.append(f"the resolution was refused, but not for want of an "
                            f"authoritative acceptance\n      {_blob[:200]}")
        else:
            print("  [ok] an acceptance in a gap between real cycles authorizes "
                  "nothing")

        # The other half of the finding: the two components must now agree. A
        # ledger that refuses while the controller counts the finding closed
        # would be the same disagreement pointing the other way.
        _st = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
        _state = _st["findings"]["C01-F01"]["state"]
        _loop = loop(root, rev)
        if _state != "OPEN":
            failures.append(f"the ledger records {_state} for a finding whose "
                            f"only acceptance has no authority")
        elif status_of(_loop.stdout) == "CONVERGED":
            failures.append("the controller converged on a finding the ledger "
                            "still holds OPEN")
        else:
            print("  [ok] ledger and controller agree the finding is still open")

    # A reopened finding needs a NEW acceptance before it can close again.
    #
    # B01-F11's third part, which cycle 03 found still open. `replay` disarms
    # acceptance on REOPENED, but `last_authorized` kept its earlier answer and
    # handed the spent ACCEPT back as a prerequisite. Codex's sequence exactly:
    # RAISED(1), ACCEPT(1), DEMONSTRATED(2), REOPENED(3). The finding is OPEN
    # again and the acceptance that closed it the first time has been withdrawn
    # by the same history, so resolving on it would be closing a finding on an
    # agreement nobody made about the second repair.
    root, rev = review_with({1: True, 2: True, 3: True, 4: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "will fix")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--evidence", "repaired")
    _re = ledger(root, "reopen", "--review", str(rev), "--cycle", "3",
                 "--id", "C01-F01", "--evidence", "it came back")
    if _re.returncode != 0:
        failures.append(f"fixture: could not reopen a resolved finding, so the "
                        f"control below proves nothing\n{_re.stderr}")
    else:
        _again = ledger(root, "resolve", "--review", str(rev), "--cycle", "4",
                        "--id", "C01-F01", "--evidence", "repaired again")
        _blob = (_again.stderr + _again.stdout).lower()
        if _again.returncode == 0:
            failures.append(
                "a reopened finding was closed again on the acceptance from "
                "before it recurred. That acceptance was withdrawn by the "
                "reopen; nobody has agreed to the second repair.")
        elif "no accept" not in _blob:
            failures.append(f"the second resolution was refused, but not for "
                            f"want of a fresh acceptance\n      {_blob[:200]}")
        else:
            print("  [ok] a reopened finding needs a new acceptance, not the "
                  "spent one")
        # And the ordinary path still works: accept again, close again.
        ledger(root, "respond", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F01", "--disposition", "ACCEPT",
               "--note", "accepted the second time too")
        _ok = ledger(root, "resolve", "--review", str(rev), "--cycle", "4",
                     "--id", "C01-F01", "--evidence", "repaired again")
        if _ok.returncode != 0:
            failures.append(f"a reopened finding could not be closed even with a "
                            f"fresh acceptance, so the rule above is not a rule "
                            f"but a dead end\n{_ok.stderr}")
        else:
            print("  [ok] with a fresh acceptance it closes normally")

    # B01-F11, the part cycle 04 found still open. The control above proves a
    # reopened finding needs a NEW acceptance. It says nothing about whether
    # that acceptance has to come after the reopening, and it did not: Codex
    # appended one dated cycle 2 to a finding reopened in cycle 3 and resolved
    # on it in cycle 4, every command exiting 0.
    #
    # Codex: "The named reopening control demonstrates refusal when no
    # additional ACCEPT exists. It does not test whether a subsequently appended
    # ACCEPT is causally eligible." A fresh row is not a fresh agreement.
    root, rev = review_with({1: True, 2: True, 3: True, 4: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "will fix")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--evidence", "repaired")
    ledger(root, "reopen", "--review", str(rev), "--cycle", "3", "--id", "C01-F01",
           "--evidence", "it came back")
    _back = ledger(root, "respond", "--review", str(rev), "--cycle", "2",
                   "--id", "C01-F01", "--disposition", "ACCEPT",
                   "--note", "dated before the reopening it claims to answer")
    _bblob = (_back.stderr + _back.stdout).lower()
    if _back.returncode == 0:
        failures.append(
            "an acceptance dated before the reopening was recorded. It answers "
            "the repair the reopening undid, and it re-arms the finding for a "
            "second repair nobody agreed to.")
    # C02-F02 moved this rule into the evaluator, so the refusal now carries the
    # evaluator's sentence rather than the command's. The needle follows the
    # wording, not the other way round: it is tightened rather than loosened,
    # because the surrounding framing text also says "reopening" and a needle
    # that broad would match a refusal for any reason at all.
    elif "dated before the cycle 03 reopening" not in _bblob:
        failures.append(f"the backdated acceptance was refused, but not for "
                        f"predating the reopening\n      {_bblob[:200]}")
    else:
        print("  [ok] refused: an acceptance dated before the reopening it "
              "answers")

    # ---- C02-F02: replay must refuse what the commands refuse to write ----
    # The three ordering rules lived in the write commands and not in the
    # evaluator, so a history containing one of these orderings was refused at
    # admission and honoured at replay. Any route other than the commands put
    # one there: a hand edit, a merge, an older tool, a restored backup.
    #
    # Which is why these fixtures are forged rather than built. Building them
    # through the commands is the thing that is now impossible, and a control
    # that can only construct legal histories cannot show this at all.
    #
    # Each is observed through what the NEXT command permits, because that path
    # recomputes the state from the history. Asserting on the stored state field
    # would be asserting on a value the forgery never touched, which is a
    # control that cannot come back false.
    def _forge(*events, raised_at: int = 1, cycles: int = 3):
        """A run whose finding carries a hand-written history.

        `raised_at` exists for C02-F02's second pass. Cycle 03 found that the
        evaluator did not keep the raising cycle, so a disposition dated before
        the finding existed replayed as valid, and demonstrating the rule needs
        a raise that is not in cycle 1.
        """
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        for i in range(1, cycles + 1):
            make_cycle(root, rev, i, commit)
        # The identifier carries its own cycle, so a finding raised in cycle 3
        # is C03-Fnn. Naming it C01-F01 made the raise refuse, and the fixture
        # then read a ledger that had never been written: the control reported a
        # missing file rather than the rule it was about.
        fid = f"C{raised_at:02d}-F01"
        ledger(root, "raise", "--review", str(rev), "--cycle", str(raised_at),
               "--id", fid, "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        lp = rev / "ledger.json"
        data = json.loads(lp.read_text(encoding="utf-8"))
        for ev, c in events:
            data["findings"][fid]["history"].append(
                {"cycle": c, "event": ev, "state": "OPEN",
                 "at": "2026-09-30T00:00:00Z", "note": "forged"})
        write_lf(lp, json.dumps(data, indent=2) + "\n")
        return root, rev, fid

    def _permits(root, rev, *args, fid: str = "C01-F01"):
        return ledger(root, *args, "--review", str(rev), "--id", fid)

    # 1. A demonstration in the acceptance's own cycle. cmd_resolve refuses it;
    #    replay used to resolve on it. If it had applied the finding would be
    #    RESOLVED and a reopen would be available.
    _r, _v, _f = _forge(("ACCEPT", 2), ("DEMONSTRATED", 2))
    _out = _permits(_r, _v, "reopen", "--cycle", "3", "--evidence", "x")
    if _out.returncode == 0:
        failures.append(
            "a same-cycle demonstration resolved the finding on replay. §5 "
            "demonstrates the repair in the NEXT review target, and the write "
            "command refuses exactly this, so replay honoured a resolution the "
            "protocol would never have allowed to be recorded.")
    elif "not RESOLVED" not in (_out.stderr + _out.stdout):
        failures.append(f"refused, but not for the finding not being "
                        f"RESOLVED\n{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] replay refuses a demonstration in the acceptance's own "
              "cycle")

    # The pair. One cycle later is legal, so the refusal above is about the
    # ordering rather than about forged histories being rejected wholesale.
    _r, _v, _f = _forge(("ACCEPT", 1), ("DEMONSTRATED", 2))
    _out = _permits(_r, _v, "reopen", "--cycle", "3", "--evidence", "x")
    if _out.returncode != 0:
        failures.append(
            f"a demonstration one cycle after its acceptance did not resolve "
            f"the finding, so the control above proves nothing\n"
            f"{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] and honours one a cycle later, so that is the rule")

    # 2. A reopening not later than the resolution it undoes. If it had applied
    #    the finding would be OPEN and a disposition would be available.
    _r, _v, _f = _forge(("ACCEPT", 1), ("DEMONSTRATED", 2), ("REOPENED", 2))
    _out = _permits(_r, _v, "respond", "--cycle", "3",
                    "--disposition", "ACCEPT", "--note", "x")
    if _out.returncode == 0:
        failures.append(
            "a reopening dated to the same cycle as the resolution it undoes "
            "took effect on replay. A recurrence is observed later than the "
            "resolution, and cmd_reopen refuses this.")
    else:
        print("  [ok] replay refuses a reopening not later than its resolution")

    # 3. A rejection dated before the reopening it would have to answer. ACCEPT
    #    had this guard and REJECT_WITH_REASON did not, though §5 gives a
    #    finding both dispositions. If it had applied the finding would be
    #    DISPUTED and no disposition would be available.
    _r, _v, _f = _forge(("ACCEPT", 1), ("DEMONSTRATED", 2), ("REOPENED", 3),
                    ("REJECT_WITH_REASON", 2))
    _out = _permits(_r, _v, "respond", "--cycle", "3",
                    "--disposition", "ACCEPT", "--note", "x")
    if _out.returncode != 0:
        failures.append(
            f"a rejection dated before the reopening took effect on replay, "
            f"leaving the finding DISPUTED. ACCEPT carried this guard and "
            f"REJECT_WITH_REASON did not.\n{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] replay refuses a rejection dated before its reopening")

    # ---- C02-F02, raised again by cycle 03 ----
    # Three ordering rules moved into the evaluator and a fourth stayed behind.
    # Codex: "a chronological guard still exists only in commands... With cycles
    # 1 to 4 valid, the stored history RAISED(3), ACCEPT(1), DEMONSTRATED(4)
    # reconstructs RESOLVED: acceptance sees OPEN with no reopening restriction,
    # and demonstration sees an acceptance from an earlier cycle."
    #
    # The command path refused that acceptance from the start, because it
    # answers a finding that did not yet exist. Replay did not, which is the
    # same divergence in a rule nobody had moved.

    # 4. An acceptance dated before the raise. If it applied, the finding has an
    #    acceptance in force and a demonstration would be available.
    _r, _v, _f = _forge(("ACCEPT", 1), raised_at=3, cycles=4)
    _out = _permits(_r, _v, "resolve", "--cycle", "4", "--evidence", "x",
                    fid=_f)
    if _out.returncode == 0:
        failures.append(
            "an acceptance dated before the finding was raised took effect on "
            "replay. It answers a finding that did not exist in that cycle, and "
            "cmd_respond refuses exactly this.")
    elif "has no ACCEPT" not in (_out.stderr + _out.stdout):
        failures.append(f"refused, but not for the absent acceptance\n"
                        f"{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] replay refuses an acceptance dated before the raise")

    # The pair. An acceptance in the raising cycle is legal, so the refusal
    # above is about the ordering and not about raises after cycle 1.
    _r, _v, _f = _forge(("ACCEPT", 3), raised_at=3, cycles=4)
    _out = _permits(_r, _v, "resolve", "--cycle", "4", "--evidence", "x",
                    fid=_f)
    if _out.returncode != 0:
        failures.append(
            f"an acceptance in the raising cycle did not take effect, so the "
            f"control above proves nothing\n{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] and honours one in the raising cycle, so that is the rule")

    # 5. A rejection dated before the raise. ACCEPT and REJECT_WITH_REASON are
    #    the two dispositions §5 gives a finding, and a guard on one of them is
    #    a guard on half the rule, which is how this finding arrived twice.
    _r, _v, _f = _forge(("REJECT_WITH_REASON", 1), raised_at=3, cycles=4)
    _out = _permits(_r, _v, "respond", "--cycle", "3",
                    "--disposition", "ACCEPT", "--note", "x", fid=_f)
    if _out.returncode != 0:
        failures.append(
            f"a rejection dated before the raise took effect on replay, leaving "
            f"the finding DISPUTED\n{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] replay refuses a rejection dated before the raise")

    # 6. Codex's own reproduction, end to end: the demonstration rests on the
    #    backdated acceptance. If the chain held, the finding is RESOLVED and a
    #    reopening is available.
    _r, _v, _f = _forge(("ACCEPT", 1), ("DEMONSTRATED", 4), raised_at=3,
                        cycles=4)
    _out = _permits(_r, _v, "reopen", "--cycle", "4", "--evidence", "x",
                    fid=_f)
    if _out.returncode == 0:
        failures.append(
            "RAISED(3), ACCEPT(1), DEMONSTRATED(4) reconstructed RESOLVED on "
            "replay. That is the exact history cycle 03 described, and no "
            "command would have written any of it.")
    elif "not RESOLVED" not in (_out.stderr + _out.stdout):
        failures.append(f"refused, but not for the finding not being "
                        f"RESOLVED\n{(_out.stderr + _out.stdout)[:300]}")
    else:
        print("  [ok] replay refuses a demonstration resting on an acceptance "
              "that predates the raise")

    # ---- C03-F01: a completed cycle keeps the grammar it was parsed with ----
    # Codex: "a completed review's interpretation depends on today's schema. A
    # later grammar amendment excluding a previously valid identifier makes an
    # unchanged historical raw review fail reconciliation, even though its
    # frozen artifacts and recorded grammar remain intact."
    #
    # The amendment here is deliberately one that would be reasonable to make:
    # three-digit finding numbers. It excludes every two-digit identifier ever
    # issued, which is every identifier in both bootstrap runs.
    print()
    print("C03-F01  a finished review is read with its own grammar")

    _gr, _gc = make_repo()
    made.append(_gr)
    _grev = _gr / "runs" / "T-001" / "plan-review"
    for _i in (1, 2):
        make_cycle(_gr, _grev, _i, _gc)
    ledger(_gr, "raise", "--review", str(_grev), "--cycle", "1",
           "--id", "C01-F01", "--class", "UNTESTED RULE",
           "--source", "CODEX_REVIEW")
    ledger(_gr, "respond", "--review", str(_grev), "--cycle", "1",
           "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "will fix")

    _schema = _gr / "specs" / "evidence-schema-v1.0.md"
    _m = re.search(r"^FINDING_ID_GRAMMAR\s*=\s*(\S+)\s*$",
                   _schema.read_text(encoding="utf-8"), re.M)
    if not _m:
        failures.append("the fixture schema declares no FINDING_ID_GRAMMAR, so "
                        "this control cannot say what it is about")
    else:
        _was = _m.group(1)
        _c1 = _grev / "cycle-01"
        write_lf(_c1 / "codex-output-raw.md",
                 "Finding ID: C01-F01\nClass: UNTESTED RULE\nEvidence: x\n")
        write_lf(_c1 / "findings.json", json.dumps({
            "schema": "cycle-findings/1", "cycle": 1, "count": 1,
            "finding_id_grammar": _was,
            "zero_findings_asserted": False,
            "findings": [{"id": "C01-F01", "class": "UNTESTED RULE",
                          "kind": "finding"}],
        }, indent=2))

        # The cycle computes before the amendment, or nothing below is
        # attributable to the amendment.
        _before = loop(_gr, _grev)
        if _before.returncode != 0:
            failures.append(
                f"the C03-F01 fixture does not compute before the grammar is "
                f"amended\n{(_before.stdout + _before.stderr)[-400:]}")
        else:
            write_lf(_schema, _schema.read_text(encoding="utf-8").replace(
                f"FINDING_ID_GRAMMAR = {_was}",
                r"FINDING_ID_GRAMMAR = \b[A-Z]{1,2}\d{2}-F\d{3}\b"))
            _after = loop(_gr, _grev)
            _blob = _after.stdout + _after.stderr
            if _after.returncode != 0:
                failures.append(
                    f"amending the grammar broke a completed cycle. Its raw "
                    f"review, its frozen artifacts and its recorded grammar are "
                    f"all unchanged; only today's schema moved, and a finished "
                    f"review is not a claim about today.\n{_blob[-500:]}")
            else:
                print("  [ok] a completed cycle still reconciles after the "
                      "grammar is amended under it")

            # The other half. The amendment has to mean something for evidence
            # that has not been parsed yet, or the repair is just "ignore the
            # schema", which is a different defect with the same symptom.
            _c2 = _grev / "cycle-02"
            write_lf(_c2 / "codex-output-raw.md",
                     "Finding ID: C01-F02\nClass: UNTESTED RULE\nEvidence: y\n")
            write_lf(_c2 / "findings.json", json.dumps({
                "schema": "cycle-findings/1", "cycle": 2, "count": 1,
                "zero_findings_asserted": False,
                "findings": [{"id": "C01-F02", "class": "UNTESTED RULE",
                              "kind": "finding"}],
            }, indent=2))
            _new = loop(_gr, _grev)
            if _new.returncode == 0:
                failures.append(
                    "a cycle recording no grammar was read with the old one. "
                    "Evidence that never declared which grammar it was parsed "
                    "with has only today's to be read by, and this identifier "
                    "is not valid under it.")
            else:
                print("  [ok] and evidence with no recorded grammar is held to "
                      "the amended one")

    # The other half, and the one that tests replay rather than the command.
    # Refusing to WRITE a backdated acceptance does nothing about a history that
    # already holds one, and Codex asked for both: "Make replay validate cycle
    # ordering and prerequisites consistently, including existing out-of-order
    # histories." ledger.json is an ordinary file under CONVENTION_ONLY, so this
    # writes the row directly and then asks whether it can still close anything.
    root, rev = review_with({1: True, 2: True, 3: True, 4: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "will fix")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--evidence", "repaired")
    ledger(root, "reopen", "--review", str(rev), "--cycle", "3", "--id", "C01-F01",
           "--evidence", "it came back")
    _lp = rev / "ledger.json"
    _doc = json.loads(_lp.read_text(encoding="utf-8"))
    _doc["findings"]["C01-F01"]["history"].append({
        "cycle": 2, "event": "ACCEPT", "state": "OPEN",
        "at": "2026-09-16T00:00:00Z",
        "note": "written straight into the file, dated before the reopening"})
    write_lf(_lp, json.dumps(_doc, indent=2) + "\n")
    _r = ledger(root, "resolve", "--review", str(rev), "--cycle", "4",
                "--id", "C01-F01", "--evidence", "repaired again")
    _rblob = (_r.stderr + _r.stdout).lower()
    if _r.returncode == 0:
        failures.append(
            "replay honoured an acceptance already in the history whose cycle "
            "predates the reopening, and closed the finding on it. Refusing to "
            "write one is not the same as refusing to use one.")
    elif "no accept" not in _rblob:
        failures.append(f"the resolution was refused, but not for want of an "
                        f"eligible acceptance\n      {_rblob[:200]}")
    else:
        print("  [ok] replay does not honour a backdated acceptance already in "
              "the history")

    # C01-F01, and the half the control above does not reach. Codex:
    #
    #   "The supplied ledger control inserts the backdated acceptance and then
    #   attempts a new resolve command. That exercises the repaired
    #   prerequisite lookup. It does not exercise state reconstruction from an
    #   existing history that already contains the subsequent demonstration."
    #
    # Which was right, and the gap was real. `last_authorized` had the
    # reopening guard; `replay` and `skipped_events` did not. So one record
    # gave three answers: RESOLVED from the state rebuild, None from the
    # prerequisite lookup, and nothing at all from the diagnostic that exists
    # to explain the difference.
    #
    # Here no command is asked to refuse anything. The whole sequence goes into
    # the file, demonstration included, and the only question is what the
    # record MEANS:
    #
    #   RAISED(1) ACCEPT(1) DEMONSTRATED(2) REOPENED(3) ACCEPT(2) DEMONSTRATED(4)
    root, rev = review_with({1: True, 2: True, 3: True, 4: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "will fix")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--evidence", "repaired")
    ledger(root, "reopen", "--review", str(rev), "--cycle", "3", "--id", "C01-F01",
           "--evidence", "it came back")
    _lp = rev / "ledger.json"
    _doc = json.loads(_lp.read_text(encoding="utf-8"))
    _hist = _doc["findings"]["C01-F01"]["history"]
    _hist.append({"cycle": 2, "event": "ACCEPT", "state": "OPEN",
                  "at": "2026-09-16T00:00:00Z",
                  "note": "dated before the reopening, written into the file"})
    _hist.append({"cycle": 4, "event": "DEMONSTRATED", "state": "RESOLVED",
                  "at": "2026-09-16T00:00:01Z",
                  "evidence": "the closure that acceptance would authorize"})
    # The cached state too. Leaving it OPEN would let this control pass on the
    # stored field while the rebuild was still wrong, which is the shape of
    # defect this whole file is about: a check that holds for a reason other
    # than the one it is named for.
    _doc["findings"]["C01-F01"]["state"] = "RESOLVED"
    write_lf(_lp, json.dumps(_doc, indent=2) + "\n")

    _show = ledger(root, "show", "--review", str(rev))
    if "[RESOLVED]" in _show.stdout:
        failures.append(
            "an existing history closed the finding on an acceptance dated "
            "before the reopening it answers. The command path refuses to "
            "write one and the state rebuild still honours one already "
            "recorded, which is C01-F01.\n" + _show.stdout)
    elif "[OPEN]" not in _show.stdout:
        failures.append(f"unexpected state rebuilding the backdated history\n"
                        f"{_show.stdout}")
    else:
        print("  [ok] the rebuild refuses a backdated acceptance the record "
              "already contains")

    # The controller half, which is NOT the same defect and is not repaired
    # here. Recorded as a tripwire rather than a green tick, because the
    # behaviour has not been ruled on.
    #
    # The ledger now rebuilds this history as OPEN. The controller reports
    # CONVERGED, and it is not wrong about the boundary it chose: at n=2 the
    # finding really was resolved. It walks boundaries from n=1 and stops at
    # the first uncleared terminal exit, so cycles 03 and 04 are never reached
    # and the reopening never enters the answer.
    #
    # That leaves the ledger saying OPEN and the controller saying CONVERGED
    # about one record, which is B01-F11's original shape one level up. But
    # the repair is a protocol question rather than a coding one: whether a
    # terminal exit at n with valid cycles beyond it should still govern, and
    # what a controller should report when evidence exists past an exit nobody
    # cleared. C01-F02 asks for the four-cycle ceiling to be enforced at every
    # boundary, which is adjacent and not this.
    #
    # So this fires on any change in either direction rather than blessing
    # today's answer. See specs/review/TERMINAL-EXIT-WITH-CYCLES-BEYOND-IT.md.
    _loop = loop(root, rev)
    _st = status_of(_loop.stdout)

    # Settled, and asserted as such: whatever the status says, the cycles run
    # after the exit have to be named. Without this the tripwire below would
    # be the only thing here, and a tripwire on its own tests nothing.
    if "UNAUTHORIZED CONTINUATION" not in _loop.stdout:
        failures.append(
            "the controller took its answer from boundary n=2 and said "
            "nothing about cycles 03 and 04, which were run after that exit "
            "and which contain the reopening\n" + _loop.stdout)
    elif "cycle-03" not in _loop.stdout or "cycle-04" not in _loop.stdout:
        failures.append(f"the continuation is flagged but the cycles are not "
                        f"named\n{_loop.stdout}")
    else:
        print("  [ok] the cycles run after the exit are named")

    # Not settled, so a tripwire rather than a tick. LOOP_STATUS reads
    # CONVERGED while the ledger holds the finding OPEN. Both are right about
    # their own question and the status is the line a caller acts on. Whether
    # that should change is a ruling, and three positions are written up in
    # specs/review/TERMINAL-EXIT-WITH-CYCLES-BEYOND-IT.md.
    if _st == "CONVERGED":
        print("  [ok] recorded gap: LOOP_STATUS is CONVERGED while the "
              "ledger holds the finding OPEN")
    else:
        failures.append(
            f"LOOP_STATUS is now {_st} where it was CONVERGED. That may be "
            f"the repair, and it is not one made here, so read "
            f"specs/review/TERMINAL-EXIT-WITH-CYCLES-BEYOND-IT.md before "
            f"changing this control to expect it.")

    # And the diagnostic has to say so. Reporting nothing skipped, while the
    # state quietly differs from what the history appears to show, is worse
    # than the wrong state: it removes the one thing that would explain it.
    _diag = ledger(root, "resolve", "--review", str(rev), "--cycle", "4",
                   "--id", "C01-F01", "--evidence", "x")
    _dblob = _diag.stderr + _diag.stdout
    if "cycle 02 ACCEPT" not in _dblob:
        failures.append(f"the diagnostics do not name the acceptance that "
                        f"never took effect\n{_dblob[:400]}")
    elif "reopening" not in _dblob:
        failures.append(f"the acceptance is named as skipped but not for "
                        f"predating the reopening\n{_dblob[:400]}")
    else:
        print("  [ok] the diagnostic names it, and says why it did not take")

    # Direction two: a DEMONSTRATED recorded in an invalid cycle must not leave
    # the finding permanently RESOLVED. Before the projection the ledger refused
    # every later resolution while the controller still counted the finding
    # OPEN, so it could never be closed by anyone.
    #
    # The cycle is broken AFTER the resolution is recorded, which is both the
    # realistic order and the only order that tests anything. Written the other
    # way round the ledger's own restate() has already stored OPEN, so reading
    # the stored state gives the right answer by accident and the control
    # survives the repair being removed. It did, on the first attempt.
    root, rev = review_with({1: True, 2: True, 3: True})
    ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
           "--disposition", "ACCEPT", "--note", "fix")
    ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
           "--evidence", "demonstrated while cycle 2 still passed")
    stored = json.loads((rev / "ledger.json").read_text(encoding="utf-8"))
    if stored["findings"]["C01-F01"]["state"] != "RESOLVED":
        failures.append("fixture precondition: the stored state should be "
                        "RESOLVED before cycle 2 is broken")
    write_lf(rev / "cycle-02" / "codex-output-raw.md", "")   # cycle 2 now fails
    r = ledger(root, "resolve", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F01", "--evidence", "demonstrated again, in a valid cycle")
    if r.returncode == 0:
        print("  [ok] a resolution in an invalid cycle does not block a valid one")
    else:
        failures.append("the valid resolution was refused because of an "
                        f"invalid-cycle one\n{r.stderr}{r.stdout}")

    # The two components must now agree about the finding's state. The whole
    # finding is that they did not.
    r_show = ledger(root, "show", "--review", str(rev))
    r_loop = loop(root, rev)
    if "RESOLVED" in r_show.stdout and status_of(r_loop.stdout) == "CONVERGED":
        print("  [ok] ledger and controller agree once the valid cycle resolves it")
    else:
        failures.append("ledger and controller still disagree\n"
                        + r_show.stdout + "\n" + r_loop.stdout)

    # ---------------------------------------------------------------- loop
    print()
    print("loop controller")

    def build(label: str, script, root: Path, rev: Path) -> bool:
        """Run a scenario's fixture script and require it to have worked.

        Returns False if it did not, having already recorded why. The caller
        must not then assert anything: an assertion over a fixture that failed
        to build tests the failure, not the property.
        """
        global _FIXTURE_STRICT
        _FIXTURE_ERRORS.clear()
        _FIXTURE_STRICT = True
        try:
            script(root, rev)
        finally:
            _FIXTURE_STRICT = False
        if _FIXTURE_ERRORS:
            failures.append(
                f"{label}: the fixture did not build, so whatever this control "
                "reports is about the fixture:\n      "
                + "\n      ".join(_FIXTURE_ERRORS))
            return False
        return True

    def scenario(label: str, n_cycles: int, script, expect: str,
                 invalid: set[int] | None = None) -> None:
        root, commit, rev = fresh()
        rev.mkdir(parents=True)
        for i in range(1, n_cycles + 1):
            make_cycle(root, rev, i, commit, valid=(i not in (invalid or set())))
        if not build(label, script, root, rev):
            return
        r = loop(root, rev)
        got = status_of(r.stdout)
        if got != expect:
            failures.append(f"{label}: expected {expect}, got {got}\n{r.stdout}")
            return
        print(f"  [ok] {expect:<14} {label}")

    def scenario_out(label: str, n_cycles: int, script, *needles: str,
                     invalid: set[int] | None = None) -> None:
        """Assert on what the controller reports, not only on the exit name.

        The exit is the same either way when the loop is flagged; the point of
        B01-F02's second half is that the cycles run after a terminal outcome
        are named rather than absorbed.
        """
        root, commit, rev = fresh()
        rev.mkdir(parents=True)
        for i in range(1, n_cycles + 1):
            make_cycle(root, rev, i, commit, valid=(i not in (invalid or set())))
        if not build(label, script, root, rev):
            return
        r = loop(root, rev)
        missing = [n for n in needles if n not in r.stdout]
        if missing:
            failures.append(f"{label}: output does not mention "
                            f"{missing}\n{r.stdout}")
            return
        print(f"  [ok] reported      {label}")

    def scenario_absent(label: str, n_cycles: int, script, *needles: str,
                        invalid: set[int] | None = None) -> None:
        """Assert the controller did NOT do something.

        Needed because several of these scenarios stall again at the next
        boundary, so the final exit name is the same whether or not the earlier
        one was wrongly cleared. Asserting only on the status let the repair be
        removed with every control still green.
        """
        root, commit, rev = fresh()
        rev.mkdir(parents=True)
        for i in range(1, n_cycles + 1):
            make_cycle(root, rev, i, commit, valid=(i not in (invalid or set())))
        # This one most of all. It asserts an absence, and an empty fixture
        # satisfies an absence perfectly: nothing was built, so nothing is
        # mentioned, so the control passes. A check that cannot come back false
        # is the defect class this whole review keeps finding.
        if not build(label, script, root, rev):
            return
        r = loop(root, rev)
        present = [n for n in needles if n in r.stdout]
        if present:
            failures.append(f"{label}: output should not mention "
                            f"{present}\n{r.stdout}")
            return
        print(f"  [ok] did not      {label}")

    def scenario_refuses(label: str, n_cycles: int, script, needle: str,
                         invalid: set[int] | None = None) -> None:
        root, commit, rev = fresh()
        rev.mkdir(parents=True)
        for i in range(1, n_cycles + 1):
            make_cycle(root, rev, i, commit, valid=(i not in (invalid or set())))
        if not build(label, script, root, rev):
            return
        r = loop(root, rev)
        if r.returncode != 2 or needle not in (r.stderr + r.stdout):
            failures.append(f"{label}: expected exit 2 mentioning {needle!r}, "
                            f"got exit {r.returncode}\n{r.stdout}\n{r.stderr}")
            return
        if "LOOP_STATUS:" in r.stdout:
            failures.append(f"{label}: emitted a LOOP_STATUS while refusing")
            return
        print(f"  [ok] refused       {label}")

    def nothing(root, rev):
        pass

    def one_open(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")

    # ---- the fixture guard itself ----
    # Two-sided, because a guard that never fires and a guard that always fires
    # are equally useless and only one of them is obvious. `nothing` is a
    # legitimate fixture that issues no ledger calls at all, so the quiet side
    # is checked against a scenario that is genuinely supposed to be empty.
    global _FIXTURE_STRICT
    _probe_root, _probe_commit, _probe_rev = fresh()
    _probe_rev.mkdir(parents=True)

    _FIXTURE_ERRORS.clear()
    _FIXTURE_STRICT = True
    try:
        ledger(_probe_root, "raise", "--review", str(_probe_rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        _quiet = list(_FIXTURE_ERRORS)
        ledger(_probe_root, "raise", "--review", str(_probe_rev), "--cycle", "1",
               "--id", "C01-F02", "--class", "NOT ONE OF THE SIX",
               "--source", "CODEX_REVIEW")
        _noisy = list(_FIXTURE_ERRORS)
    finally:
        _FIXTURE_STRICT = False
        _FIXTURE_ERRORS.clear()

    if _quiet:
        failures.append(
            f"the fixture guard fired on a ledger call that succeeded: {_quiet}. "
            "A guard that reports every fixture as broken stops anyone reading "
            "it.")
    elif not _noisy:
        failures.append(
            "the fixture guard did not fire on a ledger call that failed. Every "
            "scenario below trusts it to notice, and a fixture that fails to "
            "build would once again be asserted over rather than reported.")
    else:
        print("  [ok] the fixture guard is quiet on success and fires on "
              "failure")

    scenario("no findings at all", 1, nothing, "CONVERGED")

    scenario("one finding still open after cycle 1", 1, one_open, "CONTINUE")

    def resolved_by_2(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
               "--evidence", "done")
    scenario("everything resolved by cycle 2", 2, resolved_by_2, "CONVERGED")

    def stalled(root, rev):
        # Raised in 1, accepted in 1, nothing demonstrated in 2, nothing new.
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "ACCEPT", "--note", "fix")
    scenario("no reduction, nothing resolved, nothing disputed", 2, stalled, "STALLED")

    def new_dispute(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F02",
               "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW")
        # A NEW dispute in cycle 2 is progress under §6, so this must NOT stall.
        ledger(root, "respond", "--review", str(rev), "--cycle", "2", "--id", "C01-F02",
               "--disposition", "REJECT_WITH_REASON", "--note", "spec disagrees",
               "--spec-evidence", "§4 closed vocabulary")
    scenario("a new dispute counts as progress, so not stalled", 2, new_dispute,
             "CONTINUE")

    # Four cycles that each show progress, so STALLED never fires and the
    # budget is genuinely exhausted. My first attempt at this fixture added one
    # new finding per cycle, which is a stall by §6 and rightly came back
    # STALLED. The fixture was wrong, not the controller.
    def four_with_progress(root, rev, cycles=(1, 2, 3, 4)):
        c1 = cycles[0]
        for i in range(1, 5):
            ledger(root, "raise", "--review", str(rev), "--cycle", str(c1),
                   "--id", f"C{c1:02d}-F{i:02d}", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        # Accept one per cycle and demonstrate it in the next valid cycle.
        for k, cyc in enumerate(cycles[:-1], start=1):
            ledger(root, "respond", "--review", str(rev), "--cycle", str(cyc),
                   "--id", f"C{c1:02d}-F{k:02d}", "--disposition", "ACCEPT",
                   "--note", "fix")
            ledger(root, "resolve", "--review", str(rev), "--cycle", str(cycles[k]),
                   "--id", f"C{c1:02d}-F{k:02d}", "--evidence", "done")

    scenario("budget exhausted, progress every cycle", 4, four_with_progress,
             "MAX_4_REACHED")

    # Exit ordering: STALLED is exit B and MAX 4 is exit C, so a loop that
    # stalls on its fourth valid cycle reports STALLED, not MAX_4_REACHED.
    def four_no_progress(root, rev):
        for c in range(1, 5):
            ledger(root, "raise", "--review", str(rev), "--cycle", str(c),
                   "--id", f"C{c:02d}-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    scenario("STALLED is tested before MAX_4", 4, four_no_progress, "STALLED")

    # ---- the ceiling must not swallow the exits above it ----
    # Alex Zamurko, 28 September, asking for boundary tests at cycle 4 in
    # particular. The point is sharp: every other exit is tested where the
    # ceiling is not in play, so nothing established that a fourth cycle which
    # genuinely converges reports CONVERGED rather than MAX_4_REACHED. Exit D is
    # last in §6's order, so the protocol says it cannot fire here, and the two
    # controls below are what makes that a fact about the code rather than a
    # fact about the order the branches happen to be written in.
    #
    # Both fixtures must show progress at every boundary or STALLED fires first
    # and the control passes for the wrong reason, which is how the earlier
    # four-cycle fixture had to be rewritten.
    def four_then_converged(root, rev):
        four_with_progress(root, rev)
        # The fourth finding, accepted in 3 and demonstrated in 4. Nothing is
        # left open or disputed at the ceiling.
        ledger(root, "respond", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F04", "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "4",
               "--id", "C01-F04", "--evidence", "done")
    scenario("a fourth cycle that converges is CONVERGED, not MAX_4", 4,
             four_then_converged, "CONVERGED")

    def four_then_only_disputed(root, rev):
        for i in range(1, 5):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                   "--id", f"C01-F{i:02d}", "--class", "UNTESTED RULE",
                   "--source", "CODEX_REVIEW")
        for k, cyc in ((1, 1), (2, 2), (3, 3)):
            ledger(root, "respond", "--review", str(rev), "--cycle", str(cyc),
                   "--id", f"C01-F{k:02d}", "--disposition", "ACCEPT",
                   "--note", "fix")
            ledger(root, "resolve", "--review", str(rev), "--cycle", str(cyc + 1),
                   "--id", f"C01-F{k:02d}", "--evidence", "done")
        # The last one becomes a dispute in the fourth cycle, so OPEN empties
        # and DISPUTED does not.
        ledger(root, "respond", "--review", str(rev), "--cycle", "4",
               "--id", "C01-F04", "--disposition", "REJECT_WITH_REASON",
               "--note", "spec disagrees", "--spec-evidence", "§4 closed vocabulary")
    scenario("a fourth cycle with only a dispute left needs a human, not MAX_4",
             4, four_then_only_disputed, "HUMAN_ADJUDICATION_REQUIRED")

    # The pair: one ledger, and the only thing that differs is how many valid
    # cycles it has had. The four-cycle half is `budget exhausted, progress every
    # cycle` above; this is the three-cycle half, and together they show the
    # ceiling is what changed the answer rather than anything in the findings.
    #
    # Worth recording what this control is NOT, because the version originally
    # asked for cannot exist. An identical ledger at cycle 4 has reduced nothing,
    # resolved nothing and disputed nothing since cycle 3, which is the STALLED
    # condition, and §6 tests STALLED before the ceiling. So a genuinely
    # unchanged ledger reports STALLED at 4, never MAX_4_REACHED. The honest pair
    # is a ledger still making progress, which is this one.
    scenario("the same progressing ledger continues at 3", 3,
             lambda root, rev: four_with_progress(root, rev, cycles=(1, 2, 3)),
             "CONTINUE")

    # Alex Zamurko, 28 September, ruling on the one case the exit order leaves
    # ambiguous to a reader: "For Cycle 4 with both OPEN and DISPUTED findings,
    # report MAX_4_REACHED, because the cycle ceiling caused termination and
    # HUMAN_ADJUDICATION_REQUIRED applies only when no OPEN findings remain."
    #
    # That is what the code already does, because exit B tests OPEN_n = 0 first.
    # Until now it did so by accident of the branch order rather than because
    # anything asked. The outstanding dispute stays visible in the recorded
    # ledger state, which is a separate requirement and a separate control.
    def four_open_and_disputed(root, rev):
        for i in range(1, 5):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                   "--id", f"C01-F{i:02d}", "--class", "UNTESTED RULE",
                   "--source", "CODEX_REVIEW")
        for k, cyc in ((1, 1), (2, 2)):
            ledger(root, "respond", "--review", str(rev), "--cycle", str(cyc),
                   "--id", f"C01-F{k:02d}", "--disposition", "ACCEPT",
                   "--note", "fix")
            ledger(root, "resolve", "--review", str(rev), "--cycle", str(cyc + 1),
                   "--id", f"C01-F{k:02d}", "--evidence", "done")
        # A new dispute in cycle 4 is progress under §6, so STALLED cannot fire,
        # and C01-F03 is still open when the ceiling arrives.
        ledger(root, "respond", "--review", str(rev), "--cycle", "4",
               "--id", "C01-F04", "--disposition", "REJECT_WITH_REASON",
               "--note", "spec disagrees", "--spec-evidence", "§4 closed vocabulary")
    scenario("open and disputed together at the ceiling is MAX_4, per the ruling",
             4, four_open_and_disputed, "MAX_4_REACHED")

    # The second half of that ruling: "Record the outstanding dispute separately
    # so the need for adjudication remains visible." The status alone cannot
    # carry it, because MAX_4_REACHED says budget exhausted and says nothing
    # about a human being owed a decision. Asserting the exit name would leave
    # that requirement untested while looking covered.
    scenario_out("and the dispute it swallowed stays visible in the stop state",
                 4, four_open_and_disputed,
                 "C01-F04", "Disputes for adjudication",
                 "ledger at the stop boundary")

    # And the literal form of the third boundary test, recorded as a control
    # rather than argued in a message. The ledger below is unchanged between
    # cycle 3 and cycle 4: nothing reduced, nothing resolved, nothing disputed.
    # That is the STALLED condition, and §6 tests STALLED before the ceiling, so
    # this reports STALLED and never MAX_4_REACHED. It pairs with the
    # progressing version above, where the cycle count really is the only thing
    # that differs.
    scenario("an unchanged ledger at the ceiling stalls, it does not reach MAX_4",
             4, lambda root, rev: four_with_progress(root, rev, cycles=(1, 2, 3)),
             "STALLED")

    # ---- C02-F04: a recurrence must move the finding out of RESOLVED ----
    # Alex Zamurko, 9 September 2026, issue 7: a previously RESOLVED finding
    # raised again as the same underlying finding "transitions RESOLVED -> OPEN.
    # The recurrence is recorded as a reopen event with cycle and evidence."
    #
    # The controller checked that a reported identifier was in the ledger and
    # that it reached some state. Neither asks whether the state agrees with
    # what the review said, so a missed reopen leaves the finding RESOLVED and
    # the boundary sees nothing open.
    #
    # Two findings rather than one, deliberately. With a single finding the loop
    # converges at cycle 2 and that boundary governs, so cycle 3's recurrence
    # could never change the reported status whatever the ledger said. The
    # second finding keeps the loop alive to cycle 3, which is where the
    # question actually lives.
    def _two_then_recurrence(root, rev, reopen: bool):
        for fid in ("C01-F01", "C01-F02"):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1",
                   "--id", fid, "--class", "UNTESTED RULE",
                   "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "2",
               "--id", "C01-F01", "--evidence", "done")
        ledger(root, "respond", "--review", str(rev), "--cycle", "2",
               "--id", "C01-F02", "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "3",
               "--id", "C01-F02", "--evidence", "done")
        # Cycle 3's reviewer says the first repair is still not demonstrated.
        report_recurrence(rev, 3, "C01-F01")
        if reopen:
            ledger(root, "reopen", "--review", str(rev), "--cycle", "3",
                   "--id", "C01-F01", "--evidence", "cycle 3 reports it again")

    # Without the reopen the ledger says RESOLVED, the boundary sees nothing
    # open and nothing disputed, and the loop would converge over a defect its
    # own reviewer reported. Refused and named rather than computed.
    scenario_refuses("a recurrence reported against a RESOLVED ledger entry", 3,
                     lambda root, rev: _two_then_recurrence(root, rev, False),
                     "not demonstrated")

    # And with it recorded, the same evidence computes: the finding is OPEN at
    # cycle 3, so the loop does not converge. This is the half that shows the
    # refusal above is about the missing reopen rather than about recurrences in
    # general, without which the repair could be "refuse every recurrence".
    scenario("a recorded reopen keeps the loop off CONVERGED", 3,
             lambda root, rev: _two_then_recurrence(root, rev, True),
             "CONTINUE")

    # ---- C02-F04, raised again by cycle 03 ----
    # The guard above reads the structured entry's classification, and nothing
    # required that to agree with the review it was transcribed from. Codex:
    # "removing kind, or changing it to finding, in the structured entry leaves
    # the raw recurrence and identifiers unchanged. Reconciliation passes, but
    # the reopening guard skips the entry."
    #
    # So the same scenario, with one word changed in one file and the raw review
    # left exactly as the reviewer wrote it.
    def _recurrence_restated_as_finding(root, rev):
        _two_then_recurrence(root, rev, False)
        restate_kind(rev, 3, "C01-F01", "finding")

    scenario_refuses("a recurrence recorded in findings.json as a new finding",
                     3, _recurrence_restated_as_finding,
                     "classifies findings differently")

    # And the older-record case the correction also asks for: an entry with no
    # classification at all. It is filled from the reparse rather than guessed
    # at, so the reopening guard still sees a recurrence and still refuses.
    def _recurrence_with_no_kind(root, rev):
        _two_then_recurrence(root, rev, False)
        restate_kind(rev, 3, "C01-F01", None)

    scenario_refuses("a recurrence whose structured entry carries no "
                     "classification at all", 3, _recurrence_with_no_kind,
                     "not demonstrated")

    # The positive that keeps both honest: with the reopen recorded, the same
    # restated entry computes rather than refusing, so neither control above is
    # simply "refuse anything whose kind was touched".
    def _restated_but_reopened(root, rev):
        _two_then_recurrence(root, rev, True)
        restate_kind(rev, 3, "C01-F01", None)

    scenario("a reopened recurrence computes even with no structured kind", 3,
             _restated_but_reopened, "CONTINUE")

    # B01-F02. This scenario used to assert CONVERGED, and Codex named the
    # control itself as reinforcing the defect: "Later cycles can override an
    # earlier mandatory termination. The supplied four_then_resolved control
    # reinforces this incorrect behavior."
    #
    # Raised and accepted in cycle 1, untouched in cycle 2, resolved in cycle 4.
    # At n=2 nothing had reduced, resolved or disputed, so §6 required STALLED
    # and the loop should never have reached cycles 3 or 4. Reading only the
    # latest boundary let the cycle-4 resolution erase the cycle-2 exit.
    def four_then_resolved(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "4", "--id", "C01-F01",
               "--evidence", "done")
    scenario("a later cycle cannot erase an earlier mandatory exit", 4,
             four_then_resolved, "STALLED")

    def four_then_resolved_flagged(root, rev):
        four_then_resolved(root, rev)
    scenario_out("the cycles run after the exit are named", 4,
                 four_then_resolved_flagged,
                 "UNAUTHORIZED CONTINUATION", "cycle-03", "cycle-04")

    # And the escape hatch the correction requires, which must be a recorded
    # human transition rather than a flag the loop can set for itself.
    def auth_record(rev, *boundaries):
        write_lf(rev / "loop-authorizations.json", json.dumps({
            "schema": "loop-authorization/1",
            "authorizations": [{
                "after_valid_cycle": n, "outcome": "STALLED",
                "authorized_by": "Alex Zamurko",
                "reason": "test fixture: another loop approved at the gate",
                "at": "2026-09-09T00:00:00Z",
                # Alex Zamurko, 9 October 2026: an authorisation must say
                # where it was given, so that someone else can check it
                # rather than take a typed name on trust.
                "source": {
                    "medium": "Slack",
                    "reference": "test fixture, no real message",
                    "quote": "one more loop at that boundary, please"},
                } for n in boundaries]}, indent=2))

    def authorized_continuation(root, rev):
        four_then_resolved(root, rev)
        auth_record(rev, 2, 3)
    scenario("recorded human authorizations let the loop continue past them", 4,
             authorized_continuation, "CONVERGED")

    # One authorization is not a blanket one. The loop stalls again at n=3 and
    # that exit needs its own recorded transition, or "keep going" would restore
    # the finding under a different spelling.
    def authorized_only_once(root, rev):
        four_then_resolved(root, rev)
        auth_record(rev, 2)
    scenario("clearing one boundary does not clear the next", 4,
             authorized_only_once, "STALLED")

    # ---- B01-F02, the half cycle 02 found still broken ----
    # Codex: "The supplied authorization control pre-creates four cycles and
    # authorizes historical boundaries; it never tests resuming immediately
    # after authorizing the latest exit." Which is exactly where the runner
    # needs it: you stop at a terminal exit, record an authorization, and open
    # the next cycle. The fallback re-imposed the cleared exit, so the loop
    # reported STALLED after announcing it had been cleared.
    #
    # Two valid cycles, an authorization naming the exit at n=2 — the latest —
    # and nothing beyond it.
    def cleared_at_the_latest(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
        auth_record(rev, 2)
    scenario("an authorization at the latest boundary permits continuation", 2,
             cleared_at_the_latest, "CONTINUE")

    scenario_out("the continuation names the authority it rests on", 2,
                 cleared_at_the_latest,
                 "cleared by a recorded human authorization", "Alex Zamurko")

    # And without it, the same fixture stops. Otherwise the control above would
    # pass equally well if the exit had simply stopped being detected.
    def not_cleared_at_the_latest(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
    scenario("the same loop stops when nothing authorizes the latest exit", 2,
             not_cleared_at_the_latest, "STALLED")

    def authorization_for_another_exit(root, rev):
        four_then_resolved(root, rev)
        write_lf(rev / "loop-authorizations.json", json.dumps({
            "schema": "loop-authorization/1",
            "authorizations": [{
                "after_valid_cycle": 2, "outcome": "CONVERGED",
                "authorized_by": "Alex Zamurko",
                "reason": "names an outcome that did not occur at this boundary",
                "at": "2026-09-09T00:00:00Z"}]}, indent=2))
    scenario("an authorization naming a different outcome clears nothing", 4,
             authorization_for_another_exit, "STALLED")

    # C01-F02. The ceiling was enforced only in the fallback that runs for the
    # LATEST boundary. With a fifth cycle already on disk, a cleared exit at
    # n=4 was not the latest boundary, so it fell through and the walk simply
    # continued to n=5.
    #
    # Codex built it: five MC-2-valid cycles, RAISED(1) ACCEPT(1)
    # DEMONSTRATED(5), STALLED cleared by recorded authorization at boundaries
    # 2, 3 and 4. The controller exited 0 with VALID_CYCLE_COUNT 5 and
    # LOOP_STATUS CONVERGED, having taken convergence from a demonstration in
    # a cycle outside the budget.
    #
    # "The supplied control demonstrates the repaired case where boundary 4 is
    # the latest boundary. It does not test boundary 4 after a later evidence
    # directory exists." Which was the gap exactly: the existing controls put
    # the cleared exit at the end, where the fallback's ceiling check could
    # see it.
    def fifth_after_cleared_fourth(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "5",
               "--id", "C01-F01", "--evidence", "done")
        auth_record(rev, 2, 3, 4)
    scenario("a cleared fourth boundary does not buy a fifth cycle", 5,
             fifth_after_cleared_fourth, "MAX_4_REACHED")

    # The status alone is not enough here. MAX_4_REACHED would also be the
    # answer if the ceiling fired for some unrelated reason, so the output has
    # to show that the fourth boundary governs and that the fifth cycle was
    # seen and not evaluated. Without this, the control above would pass on a
    # right answer reached for a wrong reason.
    scenario_out("the fifth cycle is named rather than evaluated", 5,
                 fifth_after_cleared_fourth,
                 "ceiling still binds", "n=4", "cycle-05")

    # C01-F06. A ledger key is not a state.
    #
    # The controller checks that every finding a valid review reported exists
    # in ledger["findings"], then rebuilds states from events in valid cycles.
    # A finding whose replay returns None enters none of the three sets, and
    # nothing reconciled that with what the valid review said.
    #
    # Codex's two cycles, exactly: C01-F01 raised in cycle 1 and recorded
    # RAISED(1); cycle 2 reports it as REPAIR NOT DEMONSTRATED. With both
    # valid the controller says STALLED. Invalidate only cycle 1 and cycle 2
    # still carries the recurrence in both its raw and structured review, but
    # the finding has nothing to recur from, so it vanishes from every set and
    # the controller reported CONVERGED while saying every finding was
    # accounted for.
    print()
    print("a valid review's finding with no authoritative state (C01-F06)")

    def _reports_it(cdir, n, recurrence=False):
        """This cycle's review names C01-F01.

        A block is either a new finding with its own Class, or a recurrence
        of an existing identifier with a Status. Carrying both makes the raw
        review refuse to parse deterministically, which is what the first
        version of this fixture did and what the baseline caught.
        """
        body = ("Finding ID: C01-F01\nStatus: REPAIR NOT DEMONSTRATED\n"
                if recurrence else
                "Finding ID: C01-F01\nClass: UNTESTED RULE\n")
        entry = ({"id": "C01-F01"} if recurrence
                 else {"id": "C01-F01", "class": "UNTESTED RULE"})
        write_lf(cdir / "codex-output-raw.md", body)
        write_lf(cdir / "findings.json", json.dumps({
            "schema": "cycle-findings/1", "cycle": n, "count": 1,
            "findings": [entry],
        }, indent=2))

    def _recurrence(origin_valid: bool):
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        make_cycle(root, rev, 1, commit)
        make_cycle(root, rev, 2, commit)
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        # Cycle 1's review reports the finding it raised. Leaving it asserting
        # zero findings, which is what make_cycle writes, made the first
        # version of this fixture refuse for that reason instead: a cycle
        # whose review says nothing while the ledger raised something in it.
        # The baseline caught it, which is what the baseline is for.
        _reports_it(rev / "cycle-01", 1)
        # Cycle 2 reports it again, unrepaired.
        _reports_it(rev / "cycle-02", 2, recurrence=True)
        if not origin_valid:
            # Break cycle 1 only, and after its records are written. Codex
            # invalidated its target hash; an empty required file is the same
            # thing through check 5, and the recurrence in cycle 2 survives
            # intact either way.
            write_lf(rev / "cycle-01" / "codex-output-raw.md", "")
        return loop(root, rev)

    # The baseline: with the origin valid this is an ordinary unrepaired
    # finding and the controller must still produce an outcome. Without it the
    # refusal below could be refusing the fixture rather than the defect.
    _both = _recurrence(origin_valid=True)
    if _both.returncode != 0:
        failures.append(f"a recurrence with a valid origin was refused, so "
                        f"the refusal below establishes nothing\n"
                        f"{_both.stderr}{_both.stdout}")
    elif status_of(_both.stdout) == "CONVERGED":
        failures.append("an unrepaired finding reported by a valid review "
                        "produced CONVERGED")
    else:
        print(f"  [ok] with a valid origin it is an ordinary open finding "
              f"({status_of(_both.stdout)})")

    _orphan = _recurrence(origin_valid=False)
    _oblob = _orphan.stdout + _orphan.stderr
    if _orphan.returncode == 0:
        failures.append(
            f"invalidating the origin turned a valid review's unresolved "
            f"finding into {status_of(_orphan.stdout)}. The recurrence is "
            f"still reported by a cycle that counts.\n{_oblob[:400]}")
    elif "C01-F01" not in _oblob:
        failures.append(f"the refusal does not name the finding that has no "
                        f"state\n{_oblob[:400]}")
    else:
        print("  [ok] refused: a valid review's finding with no "
              "authoritative state, named")

    # D01-F01, BOOTSTRAP-003 cycle 01. A later cycle's RAISED event satisfying
    # an earlier cycle's review.
    #
    # The stateless check replayed each finding's history over every valid
    # cycle, while each boundary is computed over the cycles up to it. So a
    # finding reported by cycle 1 whose RAISED event sits in cycle 2 had a
    # state here and none at its own boundary: it left OPEN_1 without being
    # resolved by anything and the controller reported CONVERGED at a boundary
    # whose own reviewer had reported it.
    #
    # The reviewer's fixture, rebuilt: cycle 1 reports one finding, cycle 2
    # asserts zero, and only the raising event moves. `cycle_raised` and the
    # reviewer evidence are untouched, which is what makes it a test of the
    # controller rather than of a mangled file.
    print()
    print("a later cycle's raising event satisfying an earlier review (D01-F01)")

    def _raised_in(cycle_of_event: int, keep_declared: bool = True):
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        make_cycle(root, rev, 1, commit)
        make_cycle(root, rev, 2, commit)
        # Always raised through the tool, in cycle 1. The identifier encodes
        # its own cycle, so `raise --cycle 2 --id C01-F01` is refused outright
        # and the fixture cannot be built that way; the first version of this
        # control tried and died on the missing key. The reviewer's case is
        # made by moving the recorded event afterwards, which is what he
        # described: "changing only that history event".
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        # Cycle 1 reports it. Cycle 2 keeps make_cycle's zero-findings
        # assertion, so the second cycle genuinely reports nothing and the only
        # thing in question is where the raising event sits.
        _reports_it(rev / "cycle-01", 1)
        if cycle_of_event != 1:
            # `cycle_raised` stays 1, as the reviewer had it: the file reads as
            # coherent and only the event is out of place.
            p = rev / "ledger.json"
            led = json.loads(p.read_text(encoding="utf-8"))
            for h in led["findings"]["C01-F01"]["history"]:
                if h.get("event") == "RAISED":
                    h["cycle"] = cycle_of_event
            # `keep_declared` is the difference between the reviewer's fixture
            # and the one that isolates the boundary rule.
            #
            # His kept `cycle_raised: 1` against an event in cycle 2, which is
            # also a contradiction, and the contradiction check refuses it
            # before the boundary rule is consulted. The mutation probe caught
            # that immediately: removing the boundary rule left the suite green
            # because the other check was answering for it.
            #
            # With both moved to 2 the entry is internally consistent and the
            # only thing wrong is that cycle 1's reviewer reported a finding
            # whose origin its own boundary cannot see.
            led["findings"]["C01-F01"]["cycle_raised"] = (
                1 if keep_declared else cycle_of_event)
            write_lf(p, json.dumps(led, indent=2))
        return loop(root, rev)

    # The baseline first. With the event where it belongs this is an ordinary
    # open finding, so the refusal below cannot be refusing the fixture.
    _ok = _raised_in(1)
    if _ok.returncode != 0:
        failures.append(f"a finding raised in the cycle that reported it was "
                        f"refused, so the control below establishes nothing\n"
                        f"{_ok.stderr}{_ok.stdout}")
    elif status_of(_ok.stdout) == "CONVERGED":
        failures.append("a finding reported by cycle 1 and never resolved "
                        "produced CONVERGED")
    else:
        print(f"  [ok] raised where it was reported, it is an ordinary open "
              f"finding ({status_of(_ok.stdout)})")

    _moved = _raised_in(2)
    _mblob = _moved.stdout + _moved.stderr
    if _moved.returncode == 0:
        failures.append(
            f"moving only the raising event to a later cycle produced "
            f"{status_of(_moved.stdout)}. Cycle 1's reviewer reported this "
            f"finding and cycle 1's boundary cannot see the event that raised "
            f"it.\n{_mblob[:400]}")
    # `LOOP_STATUS:` with its colon, because the refusal's own epilogue says
    # "No LOOP_STATUS is emitted" and the bare word matches that sentence. The
    # first version of this control failed on exactly that, which is the same
    # mistake as a control passing on the wrong message, caught in the other
    # direction.
    elif any(ln.strip().startswith("LOOP_STATUS:")
             for ln in _mblob.splitlines()):
        failures.append(f"the controller refused and declared a status "
                        f"anyway\n{_mblob[:400]}")
    elif "C01-F01" not in _mblob:
        failures.append(f"the refusal does not name the finding\n{_mblob[:400]}")
    else:
        print("  [ok] refused, with no LOOP_STATUS: a later cycle's event "
              "cannot satisfy an earlier review")

    # The same defect with nothing else wrong in the file, so that the
    # boundary rule is the only thing that can refuse it. Without this the
    # control above passes on the contradiction check and the boundary rule
    # could be deleted unnoticed, which is what the probe reported.
    _late = _raised_in(2, keep_declared=False)
    _lblob = _late.stdout + _late.stderr
    if _late.returncode == 0:
        failures.append(
            f"a finding reported by cycle 1, raised consistently in cycle 2, "
            f"produced {status_of(_late.stdout)}. Cycle 1's boundary cannot "
            f"see the event that raised it, so at that boundary the reviewer's "
            f"finding has no state at all.\n{_lblob[:400]}")
    elif "no authoritative state" not in _lblob:
        failures.append(f"refused, but not for the finding without a state at "
                        f"its own boundary\n{_lblob[:400]}")
    else:
        print("  [ok] refused: a consistent origin in a later cycle still "
              "cannot answer for an earlier boundary")

    # The second half of D01-F01's correction: "Refuse contradictory
    # originating-cycle metadata and history." That rule needs a control the
    # boundary rule above cannot satisfy, or removing it would change nothing
    # observable and it would sit there unwatched.
    #
    # So: no cycle reports the finding at all. The boundary check never looks
    # at it, and the only thing that can notice `cycle_raised: 1` against a
    # RAISED event in cycle 2 is the comparison between the two.
    def _contradiction_only():
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        make_cycle(root, rev, 1, commit)
        make_cycle(root, rev, 2, commit)
        ledger(root, "raise", "--review", str(rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
        p = rev / "ledger.json"
        led = json.loads(p.read_text(encoding="utf-8"))
        for h in led["findings"]["C01-F01"]["history"]:
            if h.get("event") == "RAISED":
                h["cycle"] = 2
        write_lf(p, json.dumps(led, indent=2))
        return loop(root, rev)

    _contra = _contradiction_only()
    _cblob = _contra.stdout + _contra.stderr
    if _contra.returncode == 0:
        failures.append(
            f"a ledger entry whose cycle_raised disagrees with its own RAISED "
            f"event was accepted, because no cycle happened to report it. One "
            f"of the two fields is wrong either way.\n{_cblob[:400]}")
    elif "disagrees with its own history" not in _cblob:
        failures.append(f"refused, but not for the contradictory origin\n"
                        f"{_cblob[:400]}")
    else:
        print("  [ok] refused: a recorded origin that disagrees with its own "
              "history, even where nothing reported it")

    # C01-F05. Classification was `"DEVELOPMENT" if label.startswith("EXEMPT")
    # else "PROTOCOL"`, so a missing, empty or unrecognised label all meant
    # PROTOCOL. Absence bought the stronger claim.
    #
    # Codex removed only `bootstrap_review` from a development run, left the
    # file and its valid enforcement status in place, and the ordinary
    # invocation exited 0 with an unqualified "LOOP_STATUS: CONVERGED".
    # Deleting the whole file was already refused; deleting the one field that
    # says what the file is describing promoted the run.
    print()
    print("the run's classification, and what absence buys (C01-F05)")

    def _classified(value):
        """A one-cycle run whose bootstrap_review is set, blanked or removed."""
        root, commit = make_repo()
        made.append(root)
        rev = root / "runs" / "T-001" / "plan-review"
        make_cycle(root, rev, 1, commit)
        rp = root / "runs" / "T-001" / "run.json"
        doc = json.loads(rp.read_text(encoding="utf-8"))
        if value is None:
            doc.pop("bootstrap_review", None)
        else:
            doc["bootstrap_review"] = value
        write_lf(rp, json.dumps(doc, indent=2) + "\n")
        return loop(root, rev)

    # The three shapes the finding names. All other prerequisites stay valid,
    # so the only thing wrong is that the run does not say what it is.
    for _label, _val in (("removed", None), ("left empty", "   "),
                         ("an unrecognised value", "PENDING")):
        _r = _classified(_val)
        _blob = _r.stdout + _r.stderr
        if _r.returncode == 0:
            failures.append(
                f"a run whose bootstrap_review is {_label} produced an "
                f"outcome. A run that does not say what it is cannot be "
                f"assumed to be the stronger kind.\n{_blob[:400]}")
        elif "bootstrap_review" not in _blob:
            failures.append(f"the refusal for {_label} does not name the field "
                            f"that is missing\n{_blob[:400]}")
        else:
            print(f"  [ok] refused: bootstrap_review {_label}")

    # Both baselines, or the three refusals above could be refusing for some
    # unrelated reason and would look green while proving nothing.
    _ok = _classified("APPROVED")
    if _ok.returncode != 0:
        failures.append(f"an APPROVED run was refused, so the refusals above "
                        f"establish nothing\n{_ok.stderr}{_ok.stdout}")
    else:
        print("  [ok] an APPROVED run still produces an outcome")

    # An exempt run is also refused by the ordinary invocation, and that is a
    # different refusal: it has said what it is, and what it is cannot carry a
    # protocol outcome without --development. Asserted separately so the two
    # cannot be confused for one another.
    _ex = _classified("EXEMPT - NOT_A_PROTOCOL_CYCLE")
    _exblob = _ex.stdout + _ex.stderr
    if _ex.returncode == 0:
        failures.append("a development run produced an unqualified outcome "
                        f"from the ordinary invocation\n{_exblob[:400]}")
    elif "bootstrap_review" in _exblob:
        failures.append(
            "a development run was refused for want of a classification. It "
            f"has one; the refusal should be about what it says.\n"
            f"{_exblob[:400]}")
    else:
        print("  [ok] a development run is refused for being development "
              "evidence, not for want of a label")

    # C02-F11. Two places emit a status and only one carried the label. The
    # other is the early return taken when a run has cycle directories but none
    # passes MC-2, and under --quiet it printed a bare LOOP_STATUS: CONTINUE.
    # A caller parsing the machine interface would get an unqualified outcome
    # off development evidence, which is the single thing the label exists for.
    #
    # Quiet specifically. The full report carries a preamble saying what the run
    # is, so the defect is invisible there, and the control above passes on a
    # run that has one valid cycle and never reaches this branch.
    _r11, _c11 = make_repo()
    made.append(_r11)
    _v11 = _r11 / "runs" / "T-001" / "plan-review"
    make_cycle(_r11, _v11, 1, _c11, valid=False)
    _rp11 = _r11 / "runs" / "T-001" / "run.json"
    _d11 = json.loads(_rp11.read_text(encoding="utf-8"))
    _d11["bootstrap_review"] = "EXEMPT - NOT_A_PROTOCOL_CYCLE"
    write_lf(_rp11, json.dumps(_d11, indent=2) + "\n")
    _out11 = sh(sys.executable, str(_r11 / "scripts" / "loop_state.py"),
                "--review", str(_v11), "--development", "--quiet", cwd=_r11)
    if _out11.returncode != 0:
        failures.append(
            "the zero-valid-cycle development run was refused rather than "
            f"computed, so the label cannot be checked\n"
            f"{_out11.stderr}{_out11.stdout}")
    elif "LOOP_STATUS" not in _out11.stdout:
        failures.append(f"no status emitted at all\n{_out11.stdout!r}")
    elif "DEVELOPMENT EVIDENCE" not in _out11.stdout:
        failures.append(
            "a development run with no valid cycle emitted an unlabelled "
            "status through --quiet. A caller parsing that gets a bare outcome "
            f"off development evidence.\n{_out11.stdout!r}")
    else:
        print("  [ok] the label survives the zero-valid-cycle early return too")
    # The status alone cannot show this: the loop stalls again at n=3, so it
    # reports STALLED either way. What distinguishes the two is whether the n=2
    # exit was cleared at all.
    scenario_absent("clear an exit the authorization does not name", 4,
                    authorization_for_another_exit,
                    "cleared by recorded authorization")

    def authorization_without_attribution(root, rev):
        four_then_resolved(root, rev)
        write_lf(rev / "loop-authorizations.json", json.dumps({
            "schema": "loop-authorization/1",
            "authorizations": [{
                "after_valid_cycle": 2, "outcome": "STALLED",
                "authorized_by": "", "reason": "", "at": ""}]}, indent=2))
    scenario_refuses("an authorization with no attribution or reason is refused",
                     4, authorization_without_attribution, "authorized_by")

    # The one that would have bitten: cycle-02 fails the gate, so the four valid
    # cycles are 1, 3, 4, 5 and the budget is reached at directory cycle 5.
    scenario("an invalid cycle does not consume the budget", 5,
             lambda root, rev: four_with_progress(root, rev, cycles=(1, 3, 4, 5)),
             "MAX_4_REACHED", invalid={2})

    # ---- HUMAN_ADJUDICATION_REQUIRED, added in protocol v1.1 ----
    # v1.0 had no exit here: the cycle the dispute landed in returned CONTINUE,
    # telling Claude to repair a plan with nothing open, and the next returned
    # STALLED, which mislabels a loop that finished everything automation could.
    def only_a_dispute(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "REJECT_WITH_REASON", "--note", "spec disagrees",
               "--spec-evidence", "§4 closed vocabulary")
    scenario("nothing open, one dispute outstanding", 1, only_a_dispute,
             "HUMAN_ADJUDICATION_REQUIRED")

    # The exit order is load-bearing: this same fixture returned STALLED under
    # v1.0 because STALLED was tested first.
    scenario("precedes STALLED, which would otherwise swallow it", 2,
             only_a_dispute, "HUMAN_ADJUDICATION_REQUIRED")

    def resolved_and_disputed(root, rev):
        for fid, cls in (("C01-F01", "UNTESTED RULE"), ("C01-F02", "WRONG OWNERSHIP")):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", fid,
                   "--class", cls, "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "ACCEPT", "--note", "fix")
        ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
               "--evidence", "done")
        ledger(root, "respond", "--review", str(rev), "--cycle", "2", "--id", "C01-F02",
               "--disposition", "REJECT_WITH_REASON", "--note", "spec disagrees",
               "--spec-evidence", "§4 closed vocabulary")
    scenario("everything resolved or disputed", 2, resolved_and_disputed,
             "HUMAN_ADJUDICATION_REQUIRED")

    # It must NOT fire while anything is still open. A dispute alongside an open
    # finding leaves automated repair available, so the loop continues.
    def dispute_plus_open(root, rev):
        for fid, cls in (("C01-F01", "UNTESTED RULE"), ("C01-F02", "WRONG OWNERSHIP")):
            ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", fid,
                   "--class", cls, "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F02",
               "--disposition", "REJECT_WITH_REASON", "--note", "spec disagrees",
               "--spec-evidence", "§4 closed vocabulary")
    scenario("a dispute alongside an open finding does not trigger it", 1,
             dispute_plus_open, "CONTINUE")

    def resolved_in_invalid_cycle(root, rev):
        ledger(root, "raise", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
        ledger(root, "respond", "--review", str(rev), "--cycle", "1", "--id", "C01-F01",
               "--disposition", "ACCEPT", "--note", "fix")
        # Demonstrated in cycle 2, which fails the gate. It must not count.
        ledger(root, "resolve", "--review", str(rev), "--cycle", "2", "--id", "C01-F01",
               "--evidence", "done")
    scenario("a resolution recorded in an invalid cycle is ignored", 2,
             resolved_in_invalid_cycle, "CONTINUE", invalid={2})

    # ---- B01-F14, the condition Alex Zamurko attached to it ----
    #
    # He classified B01-F14 NOT BLOCKING with a proviso, 13 October 2026:
    # "This classification assumes missing metadata cannot still produce an
    # authoritative result." That is a claim about behaviour, so it needs a
    # control rather than agreement, and it had none.
    #
    # The freeze path is already covered three times over in
    # test_run_review.py. This is the other door, and the one an authoritative
    # result actually comes out of: the controller. Cycle 03's reviewer
    # removed mc1_enforcement from an approved run with a completed valid
    # cycle and got an unqualified LOOP_STATUS: CONVERGED.
    #
    # Shown both ways round. A controller that refused everything would
    # satisfy the second half on its own and establish nothing.
    root, commit, review = fresh()
    make_cycle(root, review, 1, commit)
    _with = loop(root, review)
    _status = status_of(_with.stdout)
    if _status == "(none)":
        failures.append(
            "B01-F14: the fixture produced no loop state at all, so removing "
            "the enforcement\n  status below would prove nothing about the "
            f"guard:\n  {_with.stdout.strip()[:200]}")
    else:
        print(f"  [ok] a protocol run recording its enforcement status "
              f"produces an outcome ({_status})")

    _rj = root / "runs" / "T-001" / "run.json"
    _d = json.loads(_rj.read_text(encoding="utf-8"))
    _d.pop("mc1_enforcement", None)
    write_lf(_rj, json.dumps(_d, indent=2) + "\n")
    _without = loop(root, review)
    _said = _without.stdout + _without.stderr
    if _without.returncode == 0:
        failures.append(
            "missing enforcement metadata cannot produce an authoritative "
            "result: it did.\n  The controller exited 0 with "
            f"{status_of(_without.stdout)}. This is precisely the condition "
            "Alex Zamurko's\n  B01-F14 classification rests on, and it does "
            "not hold.")
    elif status_of(_without.stdout) != "(none)":
        failures.append(
            "missing enforcement metadata cannot produce an authoritative "
            "result: it did.\n  The controller printed LOOP_STATUS: "
            f"{status_of(_without.stdout)} alongside its refusal, and a "
            "reader\n  takes the status.")
    elif "cannot support an authoritative outcome" not in _said:
        failures.append(
            "missing enforcement metadata cannot produce an authoritative "
            "result: it was\n  refused, and not for that reason, so the "
            f"condition is met by accident:\n  {_said.strip()[:300]}")
    else:
        print("  [ok] missing enforcement metadata cannot produce an "
              "authoritative result")

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("all controls fired; every refusal is reachable and every exit is "
          "shown firing and not firing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
