#!/usr/bin/env python3
"""Interface tests for the execution layer.

The other suites test each component alone. This one tests the seams, which is
where the components can each be correct and the system still wrong.

    python scripts/test_interfaces.py

Exit 0 = every seam held.

Seams covered, per Alex Zamurko's list of 8 September:

    1  schema      <-> checker      the doc's mandatory fields are the ones
                                    the checker actually enforces
    2  runner      <-> checker      a cycle the runner produced passes the
                                    gate with no hand-editing, both types
    3  runner      <-> evidence     freeze writes the layout the schema
                                    documents, by filename
    4  ledger      <-> controller   findings.json written by one is read by
                                    the other with no schema drift
    5  controller  <-> live MC-2    the verdict follows the evidence on disk
                                    now, not a value cached earlier
    6  states      <-> exits        each finding state maps to the exit the
                                    protocol assigns it

Seam 1 is the one worth having. A unit test cannot catch a schema that says a
field is mandatory while the checker never looks for it: each side passes its own
tests and the pair is wrong. It reads the field names out of the frozen schema
document and requires the checker to refuse when each is missing, so the document
and the code cannot drift apart silently.
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

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "scripts"
SCHEMA = REPO / "specs" / "evidence-schema-v1.0.md"


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def lay_run(run_dir: Path, run_id: str) -> None:
    """The run record a hand-built fixture needs to be a run at all.

    B01-F14, the half cycle 04 found still open. The controller used to classify
    a missing run.json as UNKNOWN and carry on, so seams that build a review
    directory by hand never needed one. It now refuses, because a loop state is
    an outcome about a run and there is nothing to say what kind of run this is.

    These fixtures were exercising the seam through a gap in it. Giving them a
    run makes them exercise the PROTOCOL path, which is the path the seam is
    about.
    """
    write_lf(run_dir / "run.json", json.dumps({
        "run_id": run_id,
        "bootstrap_review": "APPROVED",
        "mc1_enforcement": "CONVENTION_ONLY",
    }, indent=2) + "\n")


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def build_repo() -> tuple[Path, str]:
    """A throwaway repo carrying the real scripts and a real commit."""
    tmp = Path(tempfile.mkdtemp(prefix="iface-")).resolve()
    (tmp / "scripts").mkdir()
    for n in ("validate_cycle.py", "run_review.py", "ledger.py", "loop_state.py",
              "bootstrap_gate.py", "findings_format.py",
              "cycle_projection.py", "authority.py", "run_pins.py"):
        shutil.copy2(SRC / n, tmp / "scripts" / n)
    (tmp / "specs").mkdir()
    # The parser reads the canonical Finding ID grammar out of the schema, so a
    # fixture without it cannot record a cycle. Copied rather than stubbed.
    shutil.copy2(REPO / "specs" / "evidence-schema-v1.0.md",
                 tmp / "specs" / "evidence-schema-v1.0.md")
    write_lf(tmp / "specs" / "protocol.md", "# protocol\n\nbody\n")
    write_lf(tmp / "specs" / "spec.md", "# spec\n\nrules\n")
    write_lf(tmp / "specs" / "prompt.md", "Review the plan. Report findings.\n")
    write_lf(tmp / "plan" / "01-PLAN.md", "# plan v1\n\nstep one\n")
    write_lf(tmp / "candidate.diff", "--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n")
    write_lf(tmp / "tests.txt", "ok 1 - all\n")
    sh("git", "init", "-q", cwd=tmp)
    sh("git", "config", "user.email", "t@t", cwd=tmp)
    sh("git", "config", "user.name", "t", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "fixture", cwd=tmp)
    return tmp, sh("git", "rev-parse", "HEAD", cwd=tmp).stdout.strip()


def run(root: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    return sh(sys.executable, str(root / "scripts" / script), *args, cwd=root)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def ok(msg: str) -> None:
        print(f"  [ok] {msg}")

    def bad(msg: str) -> None:
        failures.append(msg)

    def failed_checks_of(r) -> set[int]:
        """Which numbered MC-2 checks reported FAIL.

        Asserting the specific check matters: a probe that accepts any failure
        proves nothing about the rule it claims to test, which is B01-F18.
        """
        return {int(m.group(1)) for m in
                re.finditer(r"^\s*(\d+)\.\s*\[FAIL\]", r.stdout, re.M)}

    # ---------------------------------------------------------- seam 1
    print("seam 1  schema <-> checker")

    # The schema documents these as mandatory for implementation review. Read
    # them out of the document rather than restating them here, so the test
    # fails if the document changes and the checker does not.
    block = re.search(r'"candidate_commit".*?\n```', SCHEMA.read_text(encoding="utf-8"),
                      re.S)
    if not block:
        bad("could not find the implementation field block in the schema; "
            "seam 1 cannot be checked and that is itself the finding")
        documented = []
    else:
        documented = re.findall(r'"([a-z_]+)":', block.group(0))
        print(f"        schema declares {len(documented)}: {', '.join(documented)}")

    root, commit = build_repo()
    made.append(root)

    def impl_target(**overrides) -> dict:
        tree = sh("git", "rev-parse", f"{commit}^{{tree}}", cwd=root).stdout.strip()
        t = {
            "review_type": "implementation", "run_id": "I-001", "cycle": 1,
            "protocol_commit": commit, "protocol_sha256": "2" * 64,
            "spec_sha256": "0" * 64, "frozen_at": "2026-09-08T00:00:00Z",
            "candidate_commit": commit,
            "candidate_tree_hash": tree,
            "approved_plan_hash": sha256_file(root / "plan" / "01-PLAN.md"),
            "diff_path": "candidate.diff",
            "diff_hash": sha256_file(root / "candidate.diff"),
            "test_result_path": "tests.txt",
            "test_result_hash": sha256_file(root / "tests.txt"),
        }
        t.update(overrides)
        return t

    def lay_cycle(cdir: Path, target: dict) -> None:
        for e in target.get("plan_files", []):
            snap = cdir / "artifacts" / e["path"]
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_bytes((root / e["path"]).read_bytes())
        write_lf(cdir / "findings.json", json.dumps({
            "schema": "cycle-findings/1", "cycle": target.get("cycle"),
            "count": 0, "zero_findings_asserted": True, "findings": [],
        }, indent=2))
        write_lf(cdir / "target.json", json.dumps(target, indent=2))
        d = sha256_file(cdir / "target.json")
        write_lf(cdir / "target.sha256", d + "\n")
        write_lf(cdir / "codex-input.md", f"target {d}\n")
        write_lf(cdir / "codex-output-raw.md", "findings\n")

    # approval record so check 13 has something authoritative
    write_lf(root / "runs" / "I-001" / "plan-approval" / "approval.json",
             json.dumps({"decision": "APPROVE",
                         # B01-F06: the record has to name the artifact its
                         # hash is of, or check 13 can only compare a hash
                         # against another copy of itself.
                         "approved_plan_path": "plan/01-PLAN.md",
                         "approved_plan_hash": sha256_file(root / "plan" / "01-PLAN.md")},
                        indent=2))

    base = root / "runs" / "I-001" / "implementation-review" / "cycle-01"
    lay_cycle(base, impl_target())
    r = run(root, "validate_cycle.py", str(base))
    if r.returncode != 0:
        bad(f"a conformant implementation cycle failed the gate:\n{r.stdout}")
    else:
        ok("a conformant implementation cycle passes all fifteen")

    # ---- B01-F06: check 13 must reach the plan, not two copies of a hash ----
    # Codex: "Check 13 compares two recorded strings. It neither hashes the
    # approved plan nor checks the approval decision. An isolated implementation
    # fixture continued to pass all fifteen checks after the approved plan's
    # contents changed."
    def f06_fixture(name: str, approval: dict, mutate_plan: bool = False) -> Path:
        rd = root / "runs" / name
        write_lf(rd / "plan-approval" / "approval.json",
                 json.dumps(approval, indent=2))
        cdir = rd / "implementation-review" / "cycle-01"
        cdir.mkdir(parents=True)
        write_lf(cdir / "findings.json", json.dumps({
            "schema": "cycle-findings/1", "cycle": 1, "count": 0,
            "zero_findings_asserted": True, "findings": []}, indent=2))
        write_lf(cdir / "target.json", json.dumps(impl_target(), indent=2))
        d = sha256_file(cdir / "target.json")
        write_lf(cdir / "target.sha256", d + "\n")
        write_lf(cdir / "codex-input.md", f"target {d}\n")
        write_lf(cdir / "codex-output-raw.md", "findings\n")
        if mutate_plan:
            write_lf(root / "plan" / "01-PLAN.md", "# plan v1\n\nstep one CHANGED\n")
        return cdir

    good_approval = {"decision": "APPROVE",
                     "approved_plan_path": "plan/01-PLAN.md",
                     "approved_plan_hash": sha256_file(root / "plan" / "01-PLAN.md")}

    c13 = f06_fixture("F06-BASE", good_approval)
    if failed_checks_of(run(root, "validate_cycle.py", str(c13))):
        bad("the F06 baseline fixture fails, so the controls below prove nothing")
    else:
        ok("an implementation cycle with a matching approved plan passes check 13")

    c13 = f06_fixture("F06-DECISION",
                      {**good_approval, "decision": "RETURN_FOR_REWORK"})
    if 13 not in failed_checks_of(run(root, "validate_cycle.py", str(c13))):
        bad("a hash carried by a RETURN_FOR_REWORK record was accepted as an "
            "approved plan; §7.3 freezes it on approval and nowhere else")
    else:
        ok("check 13 refuses an approval record that is not an APPROVE")

    c13 = f06_fixture("F06-NOPATH",
                      {k: v for k, v in good_approval.items()
                       if k != "approved_plan_path"})
    if 13 not in failed_checks_of(run(root, "validate_cycle.py", str(c13))):
        bad("check 13 passed with no artifact named, so it compared a hash "
            "against another copy of itself")
    else:
        ok("check 13 refuses when no artifact is named for the hash")

    c13 = f06_fixture("F06-DRIFT", good_approval, mutate_plan=True)
    if 13 not in failed_checks_of(run(root, "validate_cycle.py", str(c13))):
        bad("the approved plan changed and check 13 still passed; this is "
            "B01-F06, code approved against a plan nobody approved")
    else:
        ok("check 13 fails once the approved plan's contents change")
    write_lf(root / "plan" / "01-PLAN.md", "# plan v1\n\nstep one\n")

    # ---- the probes, rebuilt after B01-F18 ----
    #
    # The first version put each probe at runs/I-001/probe-<field>. Check 13
    # resolves the approval record as cycle_dir.parent.parent / "plan-approval",
    # which from there is runs/plan-approval — a path that does not exist. So
    # every probe failed on check 13 before the field under test was reached,
    # and the probe only asked for a nonzero exit.
    #
    # That made this control unfalsifiable. Deleting check 12's enforcement of
    # candidate_tree_hash outright still produced "7/7 enforced" and exit 0.
    #
    # Three things fix it, and all three are needed:
    #   1. each probe sits in a complete run laid out like a real one, so the
    #      approval record resolves;
    #   2. an unmodified fixture at that same layout must PASS first, or the
    #      probes could again be failing for a reason unrelated to the field;
    #   3. the probe asserts the specific check responsible for the field,
    #      rather than accepting any failure.

    def probe_run(name: str, target: dict) -> Path:
        """A complete, isolated run directory in the real layout."""
        rd = root / "runs" / name
        write_lf(rd / "plan-approval" / "approval.json",
                 json.dumps({"decision": "APPROVE",
                             "approved_plan_path": "plan/01-PLAN.md",
                             "approved_plan_hash":
                                 sha256_file(root / "plan" / "01-PLAN.md")},
                            indent=2))
        cdir = rd / "implementation-review" / "cycle-01"
        cdir.mkdir(parents=True)
        write_lf(cdir / "target.json", json.dumps(target, indent=2))
        d = sha256_file(cdir / "target.json")
        write_lf(cdir / "target.sha256", d + "\n")
        write_lf(cdir / "codex-input.md", f"target {d}\n")
        write_lf(cdir / "codex-output-raw.md", "findings\n")
        return cdir

    def failed_checks(cdir: Path) -> set[int]:
        """Which numbered checks reported FAIL."""
        out = run(root, "validate_cycle.py", str(cdir)).stdout
        return {int(m.group(1)) for m in
                re.finditer(r"^\s*(\d+)\.\s*\[FAIL\]", out, re.M)}

    # Step 2: the layout itself must be sound.
    control = probe_run("P-CONTROL", impl_target())
    control_fails = failed_checks(control)
    if control_fails:
        bad("an unmodified implementation fixture fails at the probe layout: "
            f"checks {sorted(control_fails)}. Every probe below would then fail "
            "for that reason rather than the field under test, which is exactly "
            "how B01-F18 happened.")
        documented = []
    elif documented:
        ok("an unmodified fixture passes at the probe layout, so probe failures "
           "below are attributable to the removed field")

    # Step 3: the check each field is actually enforced by. A field absent from
    # this map is one nothing specific guards, and that is itself a finding.
    RESPONSIBLE = {
        "candidate_commit":    11,
        "candidate_tree_hash": 12,
        "approved_plan_hash":  13,
        "diff_path":           14,
        "diff_hash":           14,
        "test_result_path":    15,
        "test_result_hash":    15,
    }

    unenforced, wrong_check, unmapped = [], [], []
    for field in documented:
        if field not in RESPONSIBLE:
            unmapped.append(field)
            continue
        t = {k: v for k, v in impl_target().items() if k != field}
        fails = failed_checks(probe_run(f"P-{field}", t))
        if not fails:
            unenforced.append(field)
        elif RESPONSIBLE[field] not in fails:
            wrong_check.append(f"{field}: expected check "
                               f"{RESPONSIBLE[field]} to fail, got {sorted(fails)}")

    if unmapped:
        bad("no specific check is identified for: " + ", ".join(unmapped) +
            ". A mandatory field with no responsible check cannot be shown to be "
            "enforced by anything in particular.")
    if unenforced:
        bad("the schema declares these mandatory but the checker accepts a "
            f"cycle without them: {', '.join(unenforced)}")
    if wrong_check:
        bad("a probe failed, but not on the check responsible for the removed "
            "field, so the failure does not demonstrate enforcement:\n      "
            + "\n      ".join(wrong_check))
    if documented and not (unmapped or unenforced or wrong_check):
        ok(f"every field the schema calls mandatory fails its own check when "
           f"removed ({len(documented)}/{len(documented)})")

    # ---------------------------------------------------------- seam 2 and 3
    print()
    print("seam 2  runner <-> checker      seam 3  runner <-> evidence store")

    root2, commit2 = build_repo()
    made.append(root2)
    # --bootstrap-exempt: this seam tests that a runner-produced cycle passes the
    # checker with no hand-editing, which is development evidence about the
    # machinery rather than a protocol cycle. The gate's own behaviour is
    # controlled in test_run_review.py and test_bootstrap_gate.py.
    r = run(root2, "run_review.py", "init", "--run", "A1E-001", "--bootstrap-exempt",
            "--protocol", "specs/protocol.md", "--spec", "specs/spec.md")
    if r.returncode != 0:
        bad(f"init failed:\n{r.stderr}{r.stdout}")

    r = run(root2, "run_review.py", "freeze", "--run", "A1E-001", "--type", "plan",
            "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    if r.returncode != 0:
        bad(f"freeze failed:\n{r.stderr}{r.stdout}")

    cyc = root2 / "runs" / "A1E-001" / "plan-review" / "cycle-01"

    # seam 3: the filenames the schema documents are the ones freeze wrote.
    schema_text = SCHEMA.read_text(encoding="utf-8")
    layout = re.search(r"```text\nruns/\n(.*?)```", schema_text, re.S)
    documented_files = set(re.findall(r"^\s+(target\.json|target\.sha256|"
                                      r"codex-input\.md|codex-output-raw\.md)\s*$",
                                      layout.group(1), re.M)) if layout else set()
    frozen = {p.name for p in cyc.iterdir()}
    missing = documented_files - frozen - {"codex-output-raw.md"}
    if missing:
        bad(f"freeze did not write files the schema layout documents: {missing}")
    else:
        ok(f"freeze wrote the documented layout ({len(documented_files)} names "
           "checked against the schema)")

    # Capture validity requires the reviewer to quote the target hash, so the
    # fixture has to as well.
    _th = (cyc / "target.sha256").read_text(encoding="utf-8").strip()
    write_lf(root2 / "reply.md",
             f"TARGET_SHA256 {_th}\n\n"
             "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
             "Requirement ID: R-B7\nEvidence: ...\n")
    r = run(root2, "run_review.py", "record", "--cycle", str(cyc),
            "--output", "reply.md", "--invocation", "manual")
    if r.returncode != 0 or "MC2_CONFORMANCE: PASS" not in r.stdout:
        bad(f"a runner-produced cycle did not pass the gate:\n{r.stdout}")
    else:
        ok("a runner-produced cycle passes the gate with no hand-editing")

    # ---------------------------------------------------------- seam 4
    print()
    print("seam 4  ledger <-> controller")

    rev = root2 / "runs" / "A1E-001" / "plan-review"
    run(root2, "ledger.py", "raise", "--review", str(rev), "--cycle", "1",
        "--id", "C01-F01", "--class", "UNTESTED RULE", "--requirement", "R-B7",
        "--source", "CODEX_REVIEW")
    # --development throughout these seams: root2 was initialised with
    # --bootstrap-exempt, so its cycles are development evidence and B01-F08
    # makes the controller refuse to read them as anything else. The flag is
    # the seam being exercised, not a workaround for it — a fixture that had to
    # drop it would mean the distinction had stopped travelling.
    r = run(root2, "loop_state.py", "--review", str(rev), "--development")
    if "C01-F01" not in r.stdout:
        bad("the controller did not see a finding the ledger wrote; the two "
            f"disagree about findings.json\n{r.stdout}")
    elif "OPEN_1           1" not in r.stdout.replace("  ", "  "):
        # tolerate spacing, just require it counted one open finding
        if "OPEN_1" not in r.stdout:
            bad(f"controller produced no OPEN_1 line\n{r.stdout}")
        else:
            ok("the controller reads the ledger's findings.json without drift")
    else:
        ok("the controller reads the ledger's findings.json without drift")

    # ---------------------------------------------------------- seam 5
    print()
    print("seam 5  controller <-> live MC-2 result")

    before = run(root2, "loop_state.py", "--review", str(rev),
                 "--development").stdout
    if "cycle-01  VALID" not in before:
        bad(f"expected cycle-01 valid before tampering\n{before}")
    # Break the evidence AFTER the controller has already run once.
    (cyc / "codex-output-raw.md").write_text("", encoding="utf-8")
    after = run(root2, "loop_state.py", "--review", str(rev),
                "--development").stdout
    if "cycle-01  INVALID" not in after:
        bad("the controller still reported the cycle valid after its evidence "
            f"was broken; it is not re-running the gate\n{after}")
    else:
        ok("breaking the evidence flips the verdict, so the gate is re-run "
           "rather than cached")
    if "VALID_CYCLE_COUNT: 0" not in after:
        bad(f"an invalid cycle still counted toward the budget\n{after}")
    else:
        ok("an invalid cycle contributes nothing to the budget")

    # ---------------------------------------------------------- seam 7
    print()
    print("seam 7  runner <-> loop exit  (B01-F02)")

    # "The runner checks previous output existence, not the previous loop exit."
    # Existence is the wrong question: a cycle can be properly closed and still
    # be the one at which §6 required the loop to stop. This seam is the one the
    # finding is about, so it is built end to end rather than simulated.
    root3, commit3 = build_repo()
    made.append(root3)
    rev3 = root3 / "runs" / "A1E-001" / "plan-review"
    run(root3, "run_review.py", "init", "--run", "A1E-001", "--bootstrap-exempt",
        "--protocol", "specs/protocol.md", "--spec", "specs/spec.md")
    run(root3, "run_review.py", "freeze", "--run", "A1E-001", "--type", "plan",
        "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    c1 = rev3 / "cycle-01"
    th3 = (c1 / "target.sha256").read_text(encoding="utf-8").strip()
    # A clean review: nothing found, so the loop converges at cycle 01.
    write_lf(root3 / "reply.md",
             f"TARGET_SHA256 {th3}\n\nNo findings in any category.\n")
    r = run(root3, "run_review.py", "record", "--cycle", str(c1),
            "--output", "reply.md", "--invocation", "manual", "--zero-findings")
    if r.returncode != 0:
        bad(f"seam 7 fixture: record failed\n{r.stderr}{r.stdout}")
    r = run(root3, "loop_state.py", "--review", str(rev3), "--quiet",
            "--development")
    if "CONVERGED" not in r.stdout:
        bad(f"seam 7 fixture: expected a converged loop, got\n{r.stdout}")

    # The previous cycle is closed and has recorded output, so the old check is
    # satisfied. Only consulting the exit refuses this.
    r = run(root3, "run_review.py", "freeze", "--run", "A1E-001", "--type", "plan",
            "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    if r.returncode == 0:
        bad("the runner opened cycle 02 on a loop that had already CONVERGED; "
            "it is checking output existence, not the loop exit")
    elif "already exited" not in (r.stderr + r.stdout):
        bad(f"the runner refused, but not for the loop exit\n{r.stderr}{r.stdout}")
    elif (rev3 / "cycle-02").exists():
        bad("the runner refused but left a cycle-02 directory behind")
    else:
        ok("the runner refuses to open a cycle after the loop has exited, with "
           "the previous cycle properly closed")

    # An undeterminable loop state is a refusal too: if nobody can say whether
    # the loop exited, nobody can say another cycle is permitted.
    (c1 / "findings.json").unlink()
    r = run(root3, "run_review.py", "freeze", "--run", "A1E-001", "--type", "plan",
            "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    if r.returncode == 0:
        bad("the runner opened a cycle while the loop state was undeterminable")
    elif "cannot be determined" not in (r.stderr + r.stdout):
        bad(f"refused, but not for the undeterminable state\n{r.stderr}{r.stdout}")
    else:
        ok("an undeterminable loop state refuses the next cycle rather than "
           "assuming CONTINUE")

    # ---------------------------------------------------------- seam 9
    print()
    print("seam 9  run classification <-> loop outcome  (B01-F08)")

    # Codex, cycle 02: "An isolated run initialized with --bootstrap-exempt,
    # frozen and recorded through the runner with explicit zero findings
    # returned LOOP_STATUS: CONVERGED through the ordinary controller
    # interface." The runner labelled the run; nothing stopped the controller
    # handing out an outcome indistinguishable from a protocol result.
    #
    # Its own fixture rather than root3's. Seam 7 deliberately unlinks that
    # run's findings.json to test the undeterminable path, and a later seam
    # reusing it inherits the damage — the controls below failed first time for
    # exactly that reason and said nothing about B01-F08.
    root8, commit8 = build_repo()
    made.append(root8)
    rev8 = root8 / "runs" / "D-001" / "plan-review"
    run(root8, "run_review.py", "init", "--run", "D-001", "--bootstrap-exempt",
        "--protocol", "specs/protocol.md", "--spec", "specs/spec.md")
    run(root8, "run_review.py", "freeze", "--run", "D-001", "--type", "plan",
        "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    c8 = rev8 / "cycle-01"
    th8 = (c8 / "target.sha256").read_text(encoding="utf-8").strip()
    write_lf(root8 / "reply.md",
             f"TARGET_SHA256 {th8}\n\nNo findings in any category.\n")
    r = run(root8, "run_review.py", "record", "--cycle", str(c8),
            "--output", "reply.md", "--invocation", "manual", "--zero-findings")
    if r.returncode != 0:
        bad(f"seam 9 fixture: record failed\n{r.stderr}{r.stdout}")

    r = run(root8, "loop_state.py", "--review", str(rev8), "--quiet")
    if r.returncode == 0:
        bad("the controller computed a loop state for a NOT_A_PROTOCOL_CYCLE "
            f"run without being told it was development evidence\n{r.stdout}")
    elif "development evidence" not in (r.stdout + r.stderr).lower():
        bad(f"refused, but not for the run's classification\n{r.stderr}")
    else:
        ok("the controller refuses an exempt run by default")

    r = run(root8, "loop_state.py", "--review", str(rev8), "--quiet",
            "--development")
    if r.returncode != 0:
        bad(f"--development did not let the exempt run be analysed\n{r.stderr}")
    elif "DEVELOPMENT EVIDENCE" not in r.stdout:
        bad("the status line carries no label, so a caller parsing it gets a "
            f"bare outcome off development evidence\n{r.stdout}")
    else:
        ok("--development computes it and labels the status line itself")

    # The label has to survive --quiet, which prints that line and nothing else.
    # A preamble-only label would vanish at exactly the interface where it
    # matters most.
    if r.stdout.strip().count("\n") == 0 and "DEVELOPMENT EVIDENCE" in r.stdout:
        ok("the label survives --quiet, where the status line travels alone")
    else:
        bad(f"--quiet output is not a single labelled line\n{r.stdout!r}")

    # And the reverse: a protocol run must not be dressed as development
    # evidence. Understating an outcome is as much a misreport as overstating.
    # The label is flipped after the cycle is built, not before. Freezing a run
    # marked APPROVED makes the gate demand a real bootstrap approval, which
    # this fixture has no reason to have — the first attempt failed there and
    # the control reported a missing directory instead of the thing it tests.
    rj = root8 / "runs" / "D-001" / "run.json"
    _r = json.loads(rj.read_text(encoding="utf-8"))
    _r["bootstrap_review"] = "APPROVED"
    write_lf(rj, json.dumps(_r, indent=2) + "\n")
    r = run(root8, "loop_state.py", "--review", str(rev8), "--quiet",
            "--development")
    if r.returncode == 0:
        bad("a protocol run was labelled development evidence on request")
    elif "does not apply" not in (r.stdout + r.stderr):
        bad(f"refused, but not for the misapplied flag\n{r.stderr}")
    else:
        ok("a protocol run cannot be relabelled as development evidence")

    # ---------------------------------------------------------- seam 6
    print()
    print("seam 6  finding states <-> protocol exits")

    # The cycle count is part of each case. One finding open across two cycles
    # with nothing changing is a stall by §6, not a CONTINUE, so the CONTINUE
    # case needs a single cycle where STALLED is not yet testable.
    cases = [
        ("no findings",  1, [], "CONVERGED"),
        ("one OPEN",     1, [("raise", "C01-F01")], "CONTINUE"),
        ("one OPEN, unchanged across two cycles", 2,
                            [("raise", "C01-F01")], "STALLED"),
        ("one RESOLVED", 2, [("raise", "C01-F01"), ("accept", "C01-F01"),
                             ("resolve", "C01-F01")], "CONVERGED"),
    ]
    for label, ncycles, ops, expect in cases:
        root3, commit3 = build_repo()
        made.append(root3)
        rv = root3 / "runs" / "T" / "plan-review"
        lay_run(rv.parent, "T")
        for n in range(1, ncycles + 1):
            d = rv / f"cycle-{n:02d}"
            d.mkdir(parents=True)
            t = {"review_type": "plan", "run_id": "T", "cycle": n,
                 "protocol_commit": commit3, "protocol_sha256": "2" * 64,
                 "spec_sha256": "0" * 64, "frozen_at": "2026-09-08T00:00:00Z",
                 "plan_files": [{"path": "plan/01-PLAN.md",
                                 "sha256": sha256_file(root3 / "plan" / "01-PLAN.md")}]}
            lay_cycle(d, t)
        for op, fid in ops:
            if op == "raise":
                run(root3, "ledger.py", "raise", "--review", str(rv), "--cycle", "1",
                    "--id", fid, "--class", "UNTESTED RULE",
                    "--source", "CODEX_REVIEW")
            elif op == "accept":
                run(root3, "ledger.py", "respond", "--review", str(rv), "--cycle", "1",
                    "--id", fid, "--disposition", "ACCEPT", "--note", "fix")
            elif op == "resolve":
                run(root3, "ledger.py", "resolve", "--review", str(rv), "--cycle", "2",
                    "--id", fid, "--evidence", "done")
        out = run(root3, "loop_state.py", "--review", str(rv)).stdout
        got = next((l.split(":", 1)[1].strip() for l in out.splitlines()
                    if l.startswith("LOOP_STATUS:")), "(none)")
        if got != expect:
            bad(f"seam 6, {label}: expected {expect}, got {got}\n{out}")
        else:
            ok(f"{label} -> {expect}")

    # The dispute-only state is deliberately absent. See below.
    root3, commit3 = build_repo()
    made.append(root3)
    rv = root3 / "runs" / "T" / "plan-review"
    lay_run(rv.parent, "T")
    d = rv / "cycle-01"
    d.mkdir(parents=True)
    lay_cycle(d, {"review_type": "plan", "run_id": "T", "cycle": 1,
                  "protocol_commit": commit3, "protocol_sha256": "2" * 64,
                  "spec_sha256": "0" * 64, "frozen_at": "2026-09-08T00:00:00Z",
                  "plan_files": [{"path": "plan/01-PLAN.md",
                                  "sha256": sha256_file(root3 / "plan" / "01-PLAN.md")}]})
    run(root3, "ledger.py", "raise", "--review", str(rv), "--cycle", "1",
        "--id", "C01-F01", "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW")
    run(root3, "ledger.py", "respond", "--review", str(rv), "--cycle", "1",
        "--id", "C01-F01", "--disposition", "REJECT_WITH_REASON", "--note", "disagree",
        "--spec-evidence", "§4: the class does not apply to this requirement")
    out = run(root3, "loop_state.py", "--review", str(rv)).stdout
    got = next((l.split(":", 1)[1].strip() for l in out.splitlines()
                if l.startswith("LOOP_STATUS:")), "(none)")
    if got != "HUMAN_ADJUDICATION_REQUIRED":
        bad(f"dispute-only state: expected HUMAN_ADJUDICATION_REQUIRED, got {got}")
    else:
        ok("nothing open, one dispute -> HUMAN_ADJUDICATION_REQUIRED (protocol v1.1)")

    # ---------------------------------------------------------- seam 11
    print()
    print("seam 11  implementation evidence <-> later work  (B02-F07)")

    # Codex: "An implementation fixture passed initially with preserved copies
    # present. Changing only its live diff and test-result files made checks 14
    # and 15 fail while the preserved copies were unchanged."
    #
    # Built through the runner, because the whole claim is about what freeze
    # preserves. A hand-laid cycle would prove nothing about the runner.
    root11, commit11 = build_repo()
    made.append(root11)
    run(root11, "run_review.py", "init", "--run", "I-001",
        "--bootstrap-exempt", "--protocol", "specs/protocol.md",
        "--spec", "specs/spec.md")
    # C02-F08. The reviewed diff is derived from a base and a candidate now, so
    # this fixture makes a real change and reviews it, rather than naming a real
    # commit beside two invented lines.
    write_lf(root11 / "src.py", "def f():\n    return 1\n")
    sh("git", "add", "-A", cwd=root11)
    sh("git", "commit", "-qm", "candidate work", cwd=root11)
    base11 = sh("git", "rev-parse", "HEAD~1", cwd=root11).stdout.strip()
    write_lf(root11 / "results.txt", "3 passed, 0 failed\n")
    head11 = sh("git", "rev-parse", "HEAD", cwd=root11).stdout.strip()
    plan_hash11 = sha256_file(root11 / "plan" / "01-PLAN.md")
    # §7.3's approval record. Check 13 refuses without it rather than passing
    # vacuously, which is decision F — the first run of this control failed on
    # exactly that and was right to.
    write_lf(root11 / "runs" / "I-001" / "plan-approval" / "approval.json",
             json.dumps({"decision": "APPROVE",
                         "approved_plan_hash": plan_hash11,
                         "approved_plan_path": "plan/01-PLAN.md",
                         "decided_by": "Alex Zamurko",
                         "decided_at": "2026-09-12T00:00:00Z"}, indent=2) + "\n")
    r = run(root11, "run_review.py", "freeze", "--run", "I-001",
            "--type", "implementation", "--prompt", "specs/prompt.md",
            "--candidate-commit", head11,
            "--approved-plan-hash", plan_hash11,
            "--base", base11, "--test-results", "results.txt")
    c11 = root11 / "runs" / "I-001" / "implementation-review" / "cycle-01"
    if r.returncode != 0:
        bad(f"seam 11 fixture: implementation freeze failed\n{r.stderr}{r.stdout}")
    else:
        # Recorded, not just frozen. A frozen-only cycle has no
        # codex-output-raw.md, so check 4 fails and checks 5 to 15 cascade from
        # it — the first run of this control reported all twelve as failures and
        # said nothing about the snapshot.
        _th11 = (c11 / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(root11 / "reply11.md",
                 f"TARGET_SHA256 {_th11}\n\nNo findings in any category.\n")
        _rec11 = run(root11, "run_review.py", "record", "--cycle", str(c11),
                     "--output", "reply11.md", "--invocation", "manual",
                     "--zero-findings")
        if _rec11.returncode != 0:
            bad(f"seam 11 fixture: record failed\n{_rec11.stderr}{_rec11.stdout}")

        # The preserved copies must exist, or nothing below tests anything.
        # C02-F08 renamed the first of these. The reviewed diff is no longer a
        # file the operator supplies; it is derived from the base and the
        # candidate and preserved as candidate.diff, so that is the name the
        # snapshot carries.
        for f in ("candidate.diff", "results.txt"):
            if not (c11 / "artifacts" / f).is_file():
                bad(f"freeze did not preserve {f} for an implementation review")

        # Ordinary later work: the tests are rerun, the diff regenerated, the
        # plan revised and re-approved. Every live artifact the checks look at
        # moves. A completed cycle must survive all of it — that is the whole
        # claim of snapshot-at-freeze, and B02-F07 is the places it was not
        # applied.
        # The work continues: more commits land on top of the candidate. Under
        # C02-F08 this is the live movement that matters for the diff, because
        # the diff is no longer a file anyone can edit. Check 14 re-derives from
        # two commits the target names, and commits do not move, so a cycle must
        # survive a repository that has gone on without it.
        write_lf(root11 / "src.py", "def f():\n    return 99\n")
        sh("git", "add", "-A", cwd=root11)
        sh("git", "commit", "-qm", "work after the freeze", cwd=root11)
        write_lf(root11 / "results.txt", "4 passed, 0 failed\n")
        _p11 = root11 / "plan" / "01-PLAN.md"
        _p11.write_text(_p11.read_text(encoding="utf-8") + "\n## revised\n",
                        encoding="utf-8")
        write_lf(root11 / "runs" / "I-001" / "plan-approval" / "approval.json",
                 json.dumps({"decision": "APPROVE",
                             "approved_plan_hash": sha256_file(_p11),
                             "approved_plan_path": "plan/01-PLAN.md",
                             "decided_by": "Alex Zamurko",
                             "decided_at": "2026-09-13T00:00:00Z"}, indent=2) + "\n")
        rv = run(root11, "validate_cycle.py", str(c11))
        failed = failed_checks_of(rv)
        if {14, 15} & failed:
            bad("checks 14 and 15 failed after later commits landed and the "
                "test results were rerun, so a completed implementation cycle "
                f"is invalidated by ordinary later work: {sorted(failed)}\n"
                f"{rv.stdout}")
        elif failed:
            bad(f"unexpected checks failed: {sorted(failed)}\n{rv.stdout}")
        else:
            ok("an implementation cycle survives later commits and rerun tests")

        # And tampering with the snapshot itself must still fail, or the check
        # has simply stopped looking at anything.
        write_lf(c11 / "artifacts" / "results.txt", "99 passed, 0 failed\n")
        rv = run(root11, "validate_cycle.py", str(c11))
        if 15 not in failed_checks_of(rv):
            bad("altering the preserved test results did not fail check 15; the "
                f"check is reading neither copy\n{rv.stdout}")
        elif "altered since the freeze" not in rv.stdout:
            bad(f"check 15 failed without naming the altered snapshot\n{rv.stdout}")
        else:
            ok("altering a preserved copy still fails its check")

    # ---------------------------------------------------------- seam 10
    print()
    print("seam 10  authorized continuation <-> the runner  (B01-F02)")

    # Codex: "the explicitly authorized continuation required by the original
    # correction and decision I does not work at the point the runner needs it
    # ... Add a runner/controller test that stops, records the matching
    # authorization, and then successfully freezes the next permitted cycle;
    # mismatched or absent authorization must still refuse."
    #
    # The controller reporting CONTINUE is not the same claim. This drives the
    # actual sequence: freeze, record, hit a terminal exit, be refused, record
    # the authorization, freeze successfully.
    root10, commit10 = build_repo()
    made.append(root10)
    rev10 = root10 / "runs" / "A1E-001" / "plan-review"
    run(root10, "run_review.py", "init", "--run", "A1E-001",
        "--bootstrap-exempt", "--protocol", "specs/protocol.md",
        "--spec", "specs/spec.md")

    def cycle10(n: int, findings: str) -> bool:
        if run(root10, "run_review.py", "freeze", "--run", "A1E-001",
               "--type", "plan", "--prompt", "specs/prompt.md",
               "--file", "plan/01-PLAN.md").returncode != 0:
            return False
        c = rev10 / f"cycle-{n:02d}"
        th = (c / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(root10 / f"r{n}.md", f"TARGET_SHA256 {th}\n\n{findings}")
        return run(root10, "run_review.py", "record", "--cycle", str(c),
                   "--output", f"r{n}.md", "--invocation", "manual").returncode == 0

    ok10 = cycle10(1, "Finding ID: C01-F01\nClass: UNTESTED RULE\nEvidence: x\n")
    run(root10, "ledger.py", "raise", "--review", str(rev10), "--cycle", "1",
        "--id", "C01-F01", "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
    run(root10, "ledger.py", "respond", "--review", str(rev10), "--cycle", "1",
        "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "will repair")
    ok10 = ok10 and cycle10(2, "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                               "Evidence: still here\n")
    if not ok10:
        bad("seam 10 fixture: could not build two recorded cycles")
    else:
        # Nothing changed across cycle 02, so §6 requires STALLED.
        r = run(root10, "loop_state.py", "--review", str(rev10), "--quiet",
                "--development")
        if "STALLED" not in r.stdout:
            bad(f"seam 10 fixture: expected STALLED at n=2, got\n{r.stdout}")
        else:
            r = run(root10, "run_review.py", "freeze", "--run", "A1E-001",
                    "--type", "plan", "--prompt", "specs/prompt.md",
                    "--file", "plan/01-PLAN.md")
            if r.returncode == 0:
                bad("the runner opened a cycle on a stalled loop")
            elif "already exited" not in (r.stdout + r.stderr):
                bad(f"refused, but not for the loop exit\n{r.stderr}")
            else:
                ok("the runner refuses the next cycle at a terminal exit")

            # An authorization for the wrong outcome must not unlock it.
            write_lf(rev10 / "loop-authorizations.json", json.dumps({
                "schema": "loop-authorization/1",
                "authorizations": [{
                    "after_valid_cycle": 2, "outcome": "CONVERGED",
                    "authorized_by": "Alex Zamurko",
                    "reason": "names an outcome that did not occur here",
                    "at": "2026-09-12T00:00:00Z"}]}, indent=2) + "\n")
            r = run(root10, "run_review.py", "freeze", "--run", "A1E-001",
                    "--type", "plan", "--prompt", "specs/prompt.md",
                    "--file", "plan/01-PLAN.md")
            if r.returncode == 0:
                bad("an authorization naming a different outcome unlocked the "
                    "next cycle")
            else:
                ok("an authorization for the wrong outcome still refuses")

            # The matching one must let it through. This is the case that was
            # broken: the controller announced the exit as cleared and then
            # reported it anyway, so the runner refused.
            write_lf(rev10 / "loop-authorizations.json", json.dumps({
                "schema": "loop-authorization/1",
                "authorizations": [{
                    "after_valid_cycle": 2, "outcome": "STALLED",
                    "authorized_by": "Alex Zamurko",
                    "reason": "another loop approved at the human gate",
                    "at": "2026-09-12T00:00:00Z"}]}, indent=2) + "\n")
            r = run(root10, "run_review.py", "freeze", "--run", "A1E-001",
                    "--type", "plan", "--prompt", "specs/prompt.md",
                    "--file", "plan/01-PLAN.md")
            if r.returncode != 0:
                bad("a matching authorization did not permit the next cycle, "
                    f"which is B01-F02 unrepaired\n{r.stderr}{r.stdout}")
            elif not (rev10 / "cycle-03").is_dir():
                bad("freeze reported success but opened no cycle 03")
            else:
                ok("a matching authorization lets the runner open the next "
                   "cycle")

    # ---------------------------------------------------------- seam 8
    print()
    print("seam 8  recorded hashes <-> what git hands back")

    # Every hash in this repository is taken over bytes on disk, and git decides
    # what those bytes are at checkout. Under core.autocrlf=true it rewrites LF
    # to CRLF, and then target.sha256 stops matching target.json, the capture
    # log stops matching codex-output-raw.md, MC-2 check 10 stops binding
    # codex-input.md to the target, and each cycle's artifacts/ snapshot stops
    # matching the values recorded at freeze. All at once, and none of it says
    # "line endings": it reads as fabricated or corrupted evidence.
    #
    # .gitattributes pinned specs/ and scripts/ for exactly this reason and left
    # runs/ unpinned, which is the directory the protocol is actually about. git
    # itself reported it, warning on a write into runs/ that LF would be
    # replaced by CRLF next time it touched the file.
    #
    # git check-attr is asked rather than .gitattributes parsed. The precedence
    # rules are git's, and a check that reimplements them is a check that can
    # disagree with the thing it is checking.
    hashed = [
        "runs/BOOTSTRAP-001/plan-review/cycle-01/target.json",
        "runs/BOOTSTRAP-001/plan-review/cycle-01/codex-input.md",
        "runs/BOOTSTRAP-001/plan-review/cycle-01/codex-output-raw.md",
        "runs/BOOTSTRAP-001/plan-review/cycle-01/capture-log.json",
        "specs/evidence-schema-v1.0.md",
        "specs/implementation-review-protocol-v1.1.md",
        "scripts/validate_cycle.py",
        "scripts/run_review.py",
    ]
    unpinned = []
    for rel_p in hashed:
        if not (REPO / rel_p).exists():
            continue
        t = sh("git", "-C", str(REPO), "check-attr", "text", "eol", "--", rel_p,
               cwd=REPO)
        attrs = t.stdout
        # Either conversion is disabled (-text -> "text: unset") or the ending
        # is pinned to lf. Anything else and checkout may rewrite the bytes.
        safe = ("text: unset" in attrs) or ("eol: lf" in attrs)
        if not safe:
            unpinned.append(f"{rel_p} -> {attrs.strip().splitlines()}")
    if unpinned:
        bad("files whose bytes are hashed are not pinned against line-ending "
            "conversion:\n    " + "\n    ".join(unpinned) +
            "\n    A checkout would rewrite them and every recorded hash over "
            "them would stop\n    matching at once.")
    else:
        ok(f"all {len(hashed)} hashed paths survive checkout unaltered")

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("all seams held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
