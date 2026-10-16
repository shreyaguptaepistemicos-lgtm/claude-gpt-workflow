#!/usr/bin/env python3
"""Negative controls for the bootstrap gate.

    python scripts/test_bootstrap_gate.py

Exit 0 = every refusal fired on a fixture built to produce it.

The gate is one boolean standing between development evidence and a real
protocol cycle, so the only thing that makes it worth having is that it can say
no. Each refusal below is demonstrated, and the approval path is demonstrated
too, because a gate that refuses everything is as useless as one that refuses
nothing.

The control that matters most is `approval does not survive editing a reviewed
component`. Without it the gate would answer "was there a review" rather than
"was this code reviewed", and it would keep saying yes about files nobody has
looked at since. That is the superseded-protocol-pin defect one level up.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "scripts"

EVIDENCE = ("codex-input.md", "codex-output-raw.md", "findings.md",
            "claude-response.md")


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha256_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def force_rmtree(p: Path) -> None:
    """Remove a tree that contains a git object store.

    Git writes everything under .git/objects read-only, and on Windows
    shutil.rmtree refuses a read-only file rather than clearing the bit. The
    suite's final cleanup passes ignore_errors and does not care; this one
    cannot, because a control below depends on the directory actually being
    gone. Ignoring the error there would leave a readable history behind and
    the control would pass while testing nothing.
    """
    import os
    import stat

    def _onerror(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(p, onerror=_onerror)


def build(with_evidence: bool = True) -> Path:
    """A throwaway repo carrying the real gate, components and a review target."""
    tmp = Path(tempfile.mkdtemp(prefix="bgate-")).resolve()
    (tmp / "scripts").mkdir()
    (tmp / "specs").mkdir()
    for n in ("bootstrap_gate.py", "validate_cycle.py", "run_review.py",
              "ledger.py", "loop_state.py", "findings_format.py",
              "cycle_projection.py", "authority.py", "run_pins.py"):
        shutil.copy2(SRC / n, tmp / "scripts" / n)
    shutil.copy2(REPO / "specs" / "evidence-schema-v1.0.md",
                 tmp / "specs" / "evidence-schema-v1.0.md")

    # C03-F02. The scope is a file now, not a constant, so a fixture repository
    # that lacks it has no scope at all and the gate says so. The real manifest
    # is copied rather than invented, because a fixture carrying its own list
    # would be the second source of truth Alex Zamurko's ruling removed, living
    # in the suite instead of in the gate.
    shutil.copy2(REPO / "specs" / "covered-components.json",
                 tmp / "specs" / "covered-components.json")
    shutil.copytree(REPO / "approvals", tmp / "approvals")

    if with_evidence:
        for n in EVIDENCE:
            write_lf(tmp / "bootstrap-review" / n, f"contents of {n}\n")

    # A repository, because the gate requires a scope change to exist as a
    # commit and not only as an edit. A fixture with no history cannot approve
    # anything, which is the rule rather than an obstacle to it.
    sh("git", "init", "-q", cwd=tmp)
    sh("git", "config", "user.email", "t@t", cwd=tmp)
    sh("git", "config", "user.name", "t", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "fixture", cwd=tmp)

    freeze_target(tmp)
    return tmp


def freeze_target(root: Path) -> Path:
    """A target.json covering exactly the files the gate covers.

    B01-F09 requires the decision to be bound to what was reviewed, so a fixture
    that wants to approve needs a target to bind to. Built from the gate's own
    covered set, so the two agree by construction here and any disagreement in a
    control below is one the control deliberately introduced.
    """
    import importlib.util
    spec_ = importlib.util.spec_from_file_location(
        "_bg_fixture", root / "scripts" / "bootstrap_gate.py")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)

    tgt = root / "runs" / "B-001" / "plan-review" / "cycle-01" / "target.json"
    write_lf(tgt, json.dumps({
        "review_type": "plan", "run_id": "B-001", "cycle": 1,
        "plan_files": [{"path": rel, "sha256": digest}
                       for rel, digest in mod.covered(root).items()],
    }, indent=2) + "\n")

    # C02-F07. The target and the input that names it are written together, by
    # one function, so they cannot drift apart. Several fixtures below re-freeze
    # after changing the covered set, which gives the target a new digest; when
    # this lived in the caller the preserved input went on naming the old one,
    # which is exactly the staleness the repair refuses. Writing them in two
    # places is how the two disagree, and that is the shape of most of the
    # findings this suite exists for.
    #
    # Guarded, because a fixture built with no evidence at all must stay that
    # way: creating the input here would satisfy a completeness control that is
    # supposed to fail.
    inp = root / "bootstrap-review" / "codex-input.md"
    if inp.parent.is_dir():
        write_lf(inp, f"contents of codex-input.md\ntarget {sha256_file(tgt)}\n")
    return tgt


TARGET = "runs/B-001/plan-review/cycle-01/target.json"


def gate(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "scripts" / "bootstrap_gate.py"),
                           *args], cwd=str(root), capture_output=True, text=True)


def approve(root: Path, who: str = "Alex Zamurko") -> subprocess.CompletedProcess:
    return gate(root, "record", "--decision", "APPROVE", "--decided-by", who,
                "--note", "#gap, 9 Sep 2026 00:03, Alex Zamurko: reviewed and "
                          "approved for the bootstrap exception",
                "--target", TARGET)


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def ok(msg: str) -> None:
        print(f"  [ok] {msg}")

    def expect_refused(label: str, needle: str, r: subprocess.CompletedProcess) -> None:
        if r.returncode == 0:
            failures.append(f"{label}: expected a refusal, got exit 0\n{r.stdout}")
            return
        blob = (r.stdout + r.stderr).lower()
        if needle.lower() not in blob:
            failures.append(f"{label}: refused for the wrong reason\n"
                            f"  wanted {needle!r}\n  got {blob.strip()[:240]}")
            return
        print(f"  [ok] refused: {label}")

    print("the gate refuses")

    # ---- nothing recorded ----
    root = build(); made.append(root)
    expect_refused("check with no bootstrap review at all",
                   "no bootstrap review on record", gate(root, "check"))

    # ---- evidence incomplete ----
    root = build(with_evidence=False); made.append(root)
    expect_refused("record a decision with no evidence preserved",
                   "incomplete", approve(root))

    root = build(); made.append(root)
    (root / "bootstrap-review" / "codex-output-raw.md").write_text("", encoding="utf-8")
    expect_refused("record a decision with the raw output empty",
                   "codex-output-raw.md (empty)", approve(root))

    # ---- no human named ----
    root = build(); made.append(root)
    expect_refused("record a decision with no human named", "decided-by",
                   gate(root, "record", "--decision", "APPROVE", "--decided-by", "  ",
                        "--note", "#gap, 9 Sep 2026, some attribution text here",
                        "--target", TARGET))

    # A name in --decided-by is typed by whoever ran the command. Without an
    # attribution the record cannot distinguish a relayed approval from an
    # invented one.
    expect_refused("record an approval with no attribution", "--note is required",
                   gate(root, "record", "--decision", "APPROVE",
                        "--decided-by", "Alex Zamurko", "--target", TARGET))

    expect_refused("attribution too thin to identify anything", "--note is required",
                   gate(root, "record", "--decision", "APPROVE",
                        "--decided-by", "Alex Zamurko", "--note", "ok",
                        "--target", TARGET))

    # ---- a decision that is not an approval ----
    root = build(); made.append(root)
    r = gate(root, "record", "--decision", "RETURN_FOR_REWORK",
             "--decided-by", "Alex Zamurko",
             "--note", "#gap, 9 Sep 2026, Alex Zamurko: rework required",
             "--target", TARGET)
    if r.returncode != 0:
        failures.append(f"recording RETURN_FOR_REWORK should succeed:\n{r.stderr}{r.stdout}")
    else:
        expect_refused("check after RETURN_FOR_REWORK", "not approve",
                       gate(root, "check"))

    print()
    print("the gate approves")

    root = build(); made.append(root)
    r = approve(root)
    if r.returncode != 0:
        failures.append(f"a complete bootstrap review should record:\n{r.stderr}{r.stdout}")
    elif gate(root, "check").returncode != 0:
        failures.append("check refused immediately after a valid APPROVE; the "
                        "gate would then block every run forever, which is as "
                        "useless as approving everything")
    else:
        print("  [ok] a complete review records, and check passes")

    # ---- C02-F07: the evidence has to be about the target being decided ----
    # Codex, cycle 02: "Checking that component files match a target and that
    # review files exist is not checking that the review was of that target."
    #
    # Both halves of this pairing are individually valid, which is the whole
    # point. The preserved evidence is a complete review naming target A. The
    # target passed in is B, built from the same covered set so today's
    # components match it exactly and the drift check is satisfied. Every check
    # that existed before passes. Nothing but the binding tells them apart.
    #
    # The matching positive is the control immediately above: a review whose
    # input does name its target still records and still passes check. Without
    # it the repair could be "refuse every decision" and this control would look
    # just as green.
    # Its own repo and its own name. `root` is still carrying the approved
    # fixture the next control needs, and rebinding it here made that control
    # run against a fresh repo with no prior decision, where recording a second
    # one is not a violation at all. It passed green for two runs before the
    # suite caught it.
    root7 = build(); made.append(root7)
    write_lf(root7 / "runs" / "B-002" / "plan-review" / "cycle-01" / "target.json",
             json.dumps({
                 "review_type": "plan", "run_id": "B-002", "cycle": 1,
                 "plan_files": json.loads(
                     (root7 / TARGET).read_text(encoding="utf-8"))["plan_files"],
             }, indent=2) + "\n")
    expect_refused("a decision about a target the preserved review never names",
                   "does not name the target",
                   gate(root7, "record", "--decision", "APPROVE",
                        "--decided-by", "Alex Zamurko",
                        "--note", "#gap, 9 Sep 2026, Alex Zamurko: approved "
                                  "after review",
                        "--target",
                        "runs/B-002/plan-review/cycle-01/target.json"))

    # ---- one-time by design ----
    expect_refused("record a second decision without --supersede",
                   "already exists", approve(root, "Someone Else"))

    r = gate(root, "record", "--decision", "APPROVE", "--decided-by", "Alex Zamurko",
             "--note", "#gap, 9 Sep 2026, Alex Zamurko: re-approved after rework",
             "--target", TARGET, "--supersede")
    if r.returncode != 0:
        failures.append(f"--supersede should be permitted:\n{r.stderr}{r.stdout}")
    else:
        d = json.loads((root / "bootstrap-review" / "decision.json")
                       .read_text(encoding="utf-8"))
        if "supersedes" not in d:
            failures.append("--supersede replaced the decision without preserving "
                            "the prior one; the record must not lose it")
        else:
            print("  [ok] --supersede preserves the decision it replaces")

    print()
    print("approval covers bytes, not filenames")

    # ---- THE control: editing a reviewed component invalidates the review ----
    # All four roots, plus the gate itself. bootstrap_gate.py is the one that was
    # missing: it did not hash itself, so editing `evaluate` to return (True, [])
    # would have defeated every other pin while check still said APPROVED.
    for target in ("validate_cycle.py", "run_review.py", "ledger.py",
                   "loop_state.py", "bootstrap_gate.py"):
        root = build(); made.append(root)
        if approve(root).returncode != 0 or gate(root, "check").returncode != 0:
            failures.append(f"fixture for {target} did not reach an approved state")
            continue
        p = root / "scripts" / target
        p.write_text(p.read_text(encoding="utf-8") + "\n# a later edit\n",
                     encoding="utf-8")
        expect_refused(f"approval surviving an edit to {target}",
                       "has changed since it was reviewed", gate(root, "check"))

    # ---- a reviewed component deleted ----
    # Refuses in covered(), before the per-file comparison, because a root that
    # is gone cannot be hashed at all. Both refusals are correct; this asserts
    # the one that actually fires rather than the one written first.
    root = build(); made.append(root)
    approve(root)
    (root / "scripts" / "validate_cycle.py").unlink()
    expect_refused("approval surviving deletion of a reviewed root",
                   "component under bootstrap review is missing",
                   gate(root, "check"))

    # The other path: a component the decision still pins, which the scope has
    # since dropped and which is then deleted. Without this the "was reviewed
    # but no longer exists" branch is dead code.
    #
    # C03-F02 changed how a file leaves the covered set. It used to be enough to
    # stop mentioning it; now it takes a manifest version, an authorisation
    # bound to that version's bytes, and a commit. So the fixture performs a
    # real scope contraction, which also exercises the only route by which
    # anything may leave the reviewed object.
    root = build(); made.append(root)
    write_lf(root / "scripts" / "zqx_leaving.py", "VALUE = 1\n")
    m = json.loads((root / "specs" / "covered-components.json")
                   .read_text(encoding="utf-8"))
    m["version"] = 2
    m["components"].append("scripts/zqx_leaving.py")
    m["history"].append({
        "version": 2, "at": "2026-10-02T21:00:00Z",
        "authorized_by": "Alex Zamurko",
        "reason": "fixture: a component joins the scope so that the next "
                  "version can demonstrate one leaving it",
        "added": ["scripts/zqx_leaving.py"], "removed": []})
    write_lf(root / "specs" / "covered-components.json",
             json.dumps(m, indent=2) + "\n")
    v2 = root / "approvals" / "covered-scope" / "v2.json"
    write_lf(v2, json.dumps({
        "schema": "covered-scope-change/1",
        "manifest_version": "2",
        "manifest_sha256": sha256_file(root / "specs" /
                                       "covered-components.json"),
        "authorized_by": "Alex Zamurko",
        "at": "2026-10-02T21:00:00Z",
        "reason": "fixture: authorises version 2 of the covered set",
    }, indent=2) + "\n")
    sh("git", "add", "-A", cwd=root)
    sh("git", "commit", "-qm", "scope v2", cwd=root)
    freeze_target(root)
    r = approve(root)
    if r.returncode != 0:
        failures.append(f"an authorised scope change was refused:\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] an authorised scope change is accepted")

        # Now the contraction. The decision above pins zqx_leaving.py; version 3
        # removes it from the scope and the file is deleted. The decision still
        # answers for it, which is the branch under test: a component that was
        # reviewed and is no longer there.
        m["version"] = 3
        m["components"].remove("scripts/zqx_leaving.py")
        m["history"].append({
            "version": 3, "at": "2026-10-02T21:30:00Z",
            "authorized_by": "Alex Zamurko",
            "reason": "fixture: the component leaves the scope, by the only "
                      "route anything may leave it",
            "added": [], "removed": ["scripts/zqx_leaving.py"]})
        write_lf(root / "specs" / "covered-components.json",
                 json.dumps(m, indent=2) + "\n")
        write_lf(root / "approvals" / "covered-scope" / "v3.json", json.dumps({
            "schema": "covered-scope-change/1",
            "manifest_version": "3",
            "manifest_sha256": sha256_file(root / "specs" /
                                           "covered-components.json"),
            "authorized_by": "Alex Zamurko",
            "at": "2026-10-02T21:30:00Z",
            "reason": "fixture: authorises version 3, which removes one "
                      "component from the covered set",
        }, indent=2) + "\n")
        sh("git", "add", "-A", cwd=root)
        sh("git", "commit", "-qm", "scope v3", cwd=root)
        (root / "scripts" / "zqx_leaving.py").unlink()

        r = gate(root, "check")
        blob = (r.stdout + r.stderr)
        if r.returncode == 0:
            failures.append(
                "a decision still pinning a deleted component passed. The "
                "approval answers for bytes that are not there.")
        elif "zqx_leaving.py" not in blob:
            failures.append(f"refused without naming the component the "
                            f"decision can no longer account for\n{blob[:300]}")
        else:
            print("  [ok] refused: the decision pins a component that has "
                  "left the scope and the tree")

    # ---- a decision that covers fewer components than required ----
    # This is also what an old decision looks like after the root list is
    # widened, which happened on 9 September when ledger.py and loop_state.py
    # were added. A decision predating a widening is not a decision about the
    # current system.
    for dropped in ("scripts/run_review.py", "scripts/ledger.py",
                    "scripts/loop_state.py"):
        root = build(); made.append(root)
        approve(root)
        rec = root / "bootstrap-review" / "decision.json"
        d = json.loads(rec.read_text(encoding="utf-8"))
        d["components"].pop(dropped)
        write_lf(rec, json.dumps(d, indent=2) + "\n")
        expect_refused(f"a decision that never covered {Path(dropped).name}",
                       "does not cover every component", gate(root, "check"))

    print()
    print("the covered set is declared, not derived  (C03-F02)")

    # Everything in this section replaces controls that demonstrated the
    # opposite rule. Alex Zamurko, 2 October 2026, having been shown a covered
    # set that had grown from ten files to seventeen by textual reference:
    #
    #     Remove automatic scope expansion from filename references. A filename
    #     appearing in source code, comments, documentation, strings, fixtures,
    #     or other covered files must not automatically add that file to the
    #     covered set.
    #
    # The hazard the derivation addressed is real and did not go away: a
    # component can import a module nobody declared, and editing that module
    # changes the component's behaviour without changing its bytes. So the
    # hazard is refused instead of absorbed, and the first control here is the
    # one the old mechanism would have passed silently.
    HELPER = "zqx_probe_dep"
    root = build(); made.append(root)
    write_lf(root / "scripts" / f"{HELPER}.py", "THRESHOLD = 64\n")
    vc = root / "scripts" / "validate_cycle.py"
    vc.write_text(
        vc.read_text(encoding="utf-8").replace(
            "import hashlib",
            f"import hashlib\nimport {HELPER}\n_T = {HELPER}.THRESHOLD",
            1),
        encoding="utf-8")
    # The target has to be re-frozen, or validate_cycle.py has drifted from it
    # and the drift check refuses first. The probe caught exactly that: with the
    # undeclared-import rule removed this control still went red, which means it
    # was never testing that rule.
    #
    # It cannot re-freeze through freeze_target, because that calls covered(),
    # which is the thing under test. So the target is written straight from the
    # manifest. That is the one place in this suite allowed to read the
    # component list without going through the gate, and it is allowed because
    # the gate's refusal is the subject rather than the instrument.
    _m = json.loads((root / "specs" / "covered-components.json")
                    .read_text(encoding="utf-8"))
    _tgt = root / "runs" / "B-001" / "plan-review" / "cycle-01" / "target.json"
    write_lf(_tgt, json.dumps({
        "review_type": "plan", "run_id": "B-001", "cycle": 1,
        "plan_files": [{"path": rel, "sha256": sha256_file(root / rel)}
                       for rel in sorted(set(_m["components"]) | {
                           "scripts/bootstrap_gate.py"})],
    }, indent=2) + "\n")
    write_lf(root / "bootstrap-review" / "codex-input.md",
             f"contents of codex-input.md\ntarget {sha256_file(_tgt)}\n")

    r = approve(root)
    blob = (r.stdout + r.stderr)
    if r.returncode == 0:
        failures.append(
            "a covered component imported a module the manifest does not "
            "declare, and the gate approved anyway. Editing that module would "
            "change a reviewed component's behaviour without changing its "
            "bytes, which is what the removed derivation was for.")
    elif f"scripts/{HELPER}.py" not in blob:
        failures.append(f"refused, but without naming the undeclared "
                        f"module\n{blob[:300]}")
    elif "validate_cycle.py" not in blob:
        failures.append("refused without naming which component imports it, "
                        "so the reader cannot act on it")
    else:
        print("  [ok] refused: a component imports a module nobody declared")

    # The other half, and the half the ruling is actually about: a filename that
    # appears in text pulls nothing in. Without this the repair above could be
    # "refuse everything that is mentioned", which is the defect it replaced.
    root = build(); made.append(root)
    write_lf(root / "scripts" / "zqx_unreferenced.py", "VALUE = 1\n")
    lg = root / "scripts" / "ledger.py"
    lg.write_text(
        lg.read_text(encoding="utf-8")
        + "\n# see zqx_unreferenced.py for the threshold table\n",
        encoding="utf-8")
    freeze_target(root)
    r = approve(root)
    if r.returncode != 0:
        failures.append(
            f"a filename mentioned in a comment blocked the approval. That is "
            f"the expansion the ruling removed, arriving as a refusal instead "
            f"of as an addition:\n{r.stdout}{r.stderr}")
    else:
        d = json.loads((root / "bootstrap-review" / "decision.json")
                       .read_text(encoding="utf-8"))
        if "scripts/zqx_unreferenced.py" in d.get("components", {}):
            failures.append(
                "a file named only in a comment entered the covered set. "
                "Approving it commits the review to bytes no reviewer saw.")
        elif "scripts/zqx_unreferenced.py" not in d.get("references_observed", {}):
            failures.append(
                "the mention was not recorded either. It binds nothing, but "
                "the decision is supposed to say what the components mention.")
        else:
            print("  [ok] a filename in a comment is recorded and covers "
                  "nothing")

    # ---- the manifest is the only list, and it answers for itself ----
    def _manifest(root: Path) -> dict:
        return json.loads((root / "specs" / "covered-components.json")
                          .read_text(encoding="utf-8"))

    def _write_manifest(root: Path, m: dict, commit: bool = True) -> None:
        write_lf(root / "specs" / "covered-components.json",
                 json.dumps(m, indent=2) + "\n")
        if commit:
            sh("git", "add", "-A", cwd=root)
            sh("git", "commit", "-qm", "scope change", cwd=root)

    # A list that is not what its own history produces. This is an internal
    # consistency check and is named as one: an edit that changed both would
    # pass it, which is why the authorisation evidence lives outside the file.
    root = build(); made.append(root)
    write_lf(root / "scripts" / "zqx_unreferenced.py", "VALUE = 1\n")
    m = _manifest(root)
    m["components"].append("scripts/zqx_unreferenced.py")
    _write_manifest(root, m)
    expect_refused("a manifest whose list is not what its history produces",
                   "not what its own history produces", approve(root))

    # No approval at all. Alex Zamurko: "a repository commit proves a scope
    # change was recorded, not that it was authorised."
    root = build(); made.append(root)
    (root / "approvals" / "covered-scope" / "v1.json").unlink()
    sh("git", "add", "-A", cwd=root)
    sh("git", "commit", "-qm", "remove the approval", cwd=root)
    expect_refused("a scope with no recorded authorisation",
                   "not authorised", approve(root))

    # An approval that exists but was issued for different bytes.
    root = build(); made.append(root)
    ap = root / "approvals" / "covered-scope" / "v1.json"
    rec = json.loads(ap.read_text(encoding="utf-8"))
    rec["manifest_sha256"] = "e" * 64
    write_lf(ap, json.dumps(rec, indent=2) + "\n")
    sh("git", "add", "-A", cwd=root)
    sh("git", "commit", "-qm", "rebind the approval", cwd=root)
    expect_refused("an approval issued for a different manifest",
                   "not authorised", approve(root))

    # A scope change that exists only on disk.
    root = build(); made.append(root)
    m = _manifest(root)
    m["note"] = "edited without committing"
    _write_manifest(root, m, commit=False)
    expect_refused("a scope change that was never committed",
                   "differs from the version in the repository record",
                   approve(root))

    # ---- C03-F02, raised again by cycle 04 ----
    # The approval's committed state was checked with `git status --porcelain`,
    # which says nothing about a file git has never heard of. Cycle 04: "an
    # ignored, untracked approval file can satisfy authority.require_approval
    # while producing empty ordinary porcelain status output."
    #
    # Each control below bumps the scope to version 2 and leaves the approval
    # for it out of the repository record in a different way. The manifest is
    # committed every time, so the manifest's own check cannot be what fires.
    def _scope_v2(root: Path, commit_approval: bool, ignore: bool = False,
                  stage_only: bool = False) -> None:
        m = json.loads((root / "specs" / "covered-components.json")
                       .read_text(encoding="utf-8"))
        m["version"] = 2
        m["history"].append({
            "version": 2, "at": "2026-10-05T12:00:00Z",
            "authorized_by": "Alex Zamurko",
            "reason": "fixture: a second version so the approval for it can be "
                      "left out of the repository record",
            "added": [], "removed": []})
        write_lf(root / "specs" / "covered-components.json",
                 json.dumps(m, indent=2) + "\n")
        if ignore:
            write_lf(root / ".gitignore", "approvals/covered-scope/v2.json\n")
        sh("git", "add", "-A", cwd=root)
        sh("git", "commit", "-qm", "scope v2, approval handled separately",
           cwd=root)
        # Written after the commit, so the manifest is in the record and the
        # approval is not.
        write_lf(root / "approvals" / "covered-scope" / "v2.json", json.dumps({
            "schema": "covered-scope-change/1",
            "manifest_version": "2",
            "manifest_sha256": sha256_file(root / "specs" /
                                           "covered-components.json"),
            "authorized_by": "Alex Zamurko",
            "at": "2026-10-05T12:00:00Z",
            "reason": "fixture: authorises version 2 of the covered set",
        }, indent=2) + "\n")
        if stage_only:
            sh("git", "add", "-f", "approvals/covered-scope/v2.json", cwd=root)
        if commit_approval:
            sh("git", "add", "-f", "approvals/covered-scope/v2.json", cwd=root)
            sh("git", "commit", "-qm", "approve scope v2", cwd=root)

    root = build(); made.append(root)
    _scope_v2(root, commit_approval=False, ignore=True)
    expect_refused("an approval that is untracked and ignored",
                   "not in the repository record", approve(root))

    root = build(); made.append(root)
    _scope_v2(root, commit_approval=False, stage_only=True)
    expect_refused("an approval staged but never committed",
                   "not in the repository record", approve(root))

    # The positive. Without it the three refusals above could be "refuse every
    # version 2", which would satisfy the controls and nothing else.
    root = build(); made.append(root)
    _scope_v2(root, commit_approval=True)
    freeze_target(root)
    r = approve(root)
    if r.returncode != 0:
        failures.append(f"a committed approval for a committed scope change "
                        f"was refused:\n{r.stdout}{r.stderr}")
    else:
        print("  [ok] a committed approval for a committed scope is accepted")

    # A provenance query that cannot be answered must refuse rather than
    # proceed. Cycle 04: "Failure to establish approval provenance is treated as
    # permission." Reached honestly by removing the repository, so the query
    # fails rather than returning an answer nobody checked.
    root = build(); made.append(root)
    force_rmtree(root / ".git")
    expect_refused("a repository whose record cannot be read at all",
                   "not in the repository record", approve(root))

    # A component that starts importing new code after the decision must still
    # block. Under the old rule the closure widened and the hashes stopped
    # matching; under this one the import is undeclared and the gate refuses
    # before it gets that far. Different mechanism, same requirement, and the
    # requirement is the part worth keeping.
    root = build(); made.append(root)
    approve(root)
    if gate(root, "check").returncode != 0:
        failures.append("fixture did not reach an approved state")
    else:
        write_lf(root / "scripts" / "zqx_late_dep.py", "LIMIT = 4\n")
        lp = root / "scripts" / "loop_state.py"
        lp.write_text(lp.read_text(encoding="utf-8") +
                      "\nimport zqx_late_dep\n_L = zqx_late_dep.LIMIT\n",
                      encoding="utf-8")
        r = gate(root, "check")
        blob = (r.stdout + r.stderr).lower()
        if r.returncode == 0:
            failures.append("a component that started reaching new code still "
                            "passed on an old approval")
        elif ("has changed" not in blob and "does not cover" not in blob
                and "not declared" not in blob):
            failures.append(f"blocked for an unexpected reason:\n{blob[:240]}")
        else:
            print("  [ok] refused: a component reaching code the decision "
                  "never saw")

    # ---- a corrupt record is a refusal, not a crash ----
    root = build(); made.append(root)
    approve(root)
    write_lf(root / "bootstrap-review" / "decision.json", "{not json\n")
    expect_refused("a decision record that is not valid JSON",
                   "not valid json", gate(root, "check"))

    # ---- B01-F15: no claim stronger than CONVENTION_ONLY supports ----
    # MC-1: while enforcement is CONVENTION_ONLY, claims that findings are
    # immutable or that review input is technically protected "must not be
    # made". Two such claims had grown back by the time Codex read the code:
    # the schema said freezing "proves the artifact did not change", and the
    # comment here said self-hashing closed the replace-evaluate hole.
    #
    # Prose drifts in the flattering direction on its own. A hash check reads
    # like a guarantee to whoever writes about it next, so this refuses the
    # phrasings rather than trusting everyone to remember the distinction.
    print()
    print("the decision is bound to what was reviewed")

    # ---- B01-F09 ----
    # Approval must be about the artifacts a reviewer saw, not about whatever is
    # on disk when someone gets round to recording the decision. Without this,
    # approve-then-edit-then-record produces an approval covering code nobody
    # reviewed, under evidence describing code that no longer exists — and
    # `check` then verifies the decision against itself and passes forever.
    root = build(); made.append(root)
    expect_refused("record a decision with no --target at all",
                   "--target is required",
                   gate(root, "record", "--decision", "APPROVE",
                        "--decided-by", "Alex Zamurko",
                        "--note", "#gap, 9 Sep 2026, approved after review"))

    root = build(); made.append(root)
    vc = root / "scripts" / "validate_cycle.py"
    vc.write_text(vc.read_text(encoding="utf-8") + "\n# edited after the freeze\n",
                  encoding="utf-8")
    expect_refused("record a decision after a component changed post-freeze",
                   "changed after the freeze", approve(root))

    # ---- B01-F10 ----
    # The target carried six artifacts and the covered set held five, so editing
    # the evidence schema did not invalidate its own approval. Both directions
    # of that mismatch are refusals now.
    root = build(); made.append(root)
    tgt = root / TARGET
    d = json.loads(tgt.read_text(encoding="utf-8"))
    d["plan_files"] = [e for e in d["plan_files"]
                       if e["path"] != "specs/evidence-schema-v1.0.md"]
    write_lf(tgt, json.dumps(d, indent=2) + "\n")
    expect_refused("a covered file the review target never contained",
                   "was not in the review target", approve(root))

    root = build(); made.append(root)
    tgt = root / TARGET
    d = json.loads(tgt.read_text(encoding="utf-8"))
    d["plan_files"].append({"path": "specs/unreviewed-extra.md",
                            "sha256": "f" * 64})
    write_lf(tgt, json.dumps(d, indent=2) + "\n")
    expect_refused("a reviewed artifact the gate does not cover",
                   "not in the covered set", approve(root))

    # And the schema must actually be in the covered set, or F10 is only
    # half-repaired: the mismatch check would pass while nothing pinned it.
    root = build(); made.append(root)
    if approve(root).returncode != 0 or gate(root, "check").returncode != 0:
        failures.append("the six-artifact fixture did not reach an approved state")
    else:
        sch = root / "specs" / "evidence-schema-v1.0.md"
        sch.write_text(sch.read_text(encoding="utf-8") + "\n<!-- later edit -->\n",
                       encoding="utf-8")
        expect_refused("approval surviving an edit to the evidence schema",
                       "has changed since it was reviewed", gate(root, "check"))

    print()
    print("no claim stronger than CONVENTION_ONLY")

    # Word-boundary on both sides: an earlier version used r"prove[sd]?\b" and
    # matched the "prove" inside "approved", flagging every mention of the
    # approved-plan hash. And "prevents" was a trigger until it flagged "the
    # defect this gate exists to prevent", which is a claim about a logic
    # property rather than about enforcement. Both were noise, and a check that
    # cries wolf gets silenced rather than heeded.
    OVERCLAIM = (
        (r"\bprove[sd]?\b|\bproof\b", "proof"),
        (r"\bimmutab", "immutability"),
        (r"technically protected", "technical protection"),
        (r"cannot be (?:changed|edited|modified|overwritten|rewritten)",
         "prevention of modification"),
        (r"\bguarantee[sd]?\b", "guarantee"),
    )
    # Denying the claim is the point, not a violation of it. Checked over a
    # two-line window because these are wrapped paragraphs and the negation
    # frequently lands on the following line.
    DENIAL = re.compile(
        r"\b(?:not|never|no|nothing|cannot|rather than|instead of|without|"
        r"neither|nor|unsupportable|forbid)", re.I)

    # B02-F10. Derived from the gate's actual covered set, not a list typed
    # here. The hard-coded six omitted findings_format.py, cycle_projection.py,
    # authority.py and run_pins.py — every module added since the list was
    # written — and reported success for the six it did read. The over-claim
    # Codex found as B02-F09 was in authority.py, which is to say it was in the
    # one file this check was supposed to cover and did not.
    #
    # Alex Zamurko, 10 September: "derive the prose/over-claim and enforcement
    # test scope from the actual reviewed/dependency set, not a hard-coded
    # list." So when a covered module appears, it is scanned because it is
    # covered, and the scope cannot silently stay fixed while the review scope
    # grows.
    import importlib.util as _ilu
    _s = _ilu.spec_from_file_location("_bg_scope", REPO / "scripts" / "bootstrap_gate.py")
    _bg = _ilu.module_from_spec(_s); _s.loader.exec_module(_bg)
    scanned = [REPO / rel for rel in sorted(_bg.covered(REPO))]
    if len(scanned) < 6:
        failures.append(f"the covered set resolved to {len(scanned)} files, "
                        "which is fewer than the declared roots; the scan scope "
                        "is not being derived from the gate")

    def sentences(text: str):
        """(sentence, first line number). Prose here wraps, so a sentence is the
        unit that carries the claim; a line is not."""
        line_of, pos = [], 0
        for n, ln in enumerate(text.splitlines(keepends=True), 1):
            line_of.append((pos, n))
            pos += len(ln)
        # Strip comment markers before flattening. Left in, a bare "#" between
        # two comment paragraphs stops the sentence splitter, so the claim in
        # the second paragraph merges with a sentence from the first — and if
        # that one contains a negation, the claim is silently excused. That is
        # how "Self-hashing guarantees tamper evidence" went unflagged.
        stripped = []
        for ln in text.splitlines():
            body = re.sub(r"^\s*#\s?", "", ln)
            stripped.append("" if not body.strip() else body)
        flat = re.sub(r"\s*\n\s*", " ", "\n".join(stripped))
        flat = re.sub(r"\n\s*\n", ".\n", flat)
        # Offsets shift once newlines collapse, so locate each sentence by
        # searching the original for its opening words instead.
        for s in re.split(r"(?<=[.:])\s+(?=[A-Z`\"'(])", flat):
            s = s.strip()
            if not s:
                continue
            head = re.escape(s[:40].strip())
            m = re.search(head.replace(r"\ ", r"\s+"), text)
            n = 1
            if m:
                n = next((ln for off, ln in reversed(line_of)
                          if off <= m.start()), 1)
            yield s, n

    offenders = []
    for f in scanned:
        if not f.is_file():
            continue
        for sentence, n in sentences(f.read_text(encoding="utf-8")):
            # The denial has to be in the same sentence as the claim. An earlier
            # version looked at a window of neighbouring lines, which in prose
            # discussing what things do and do not establish suppressed almost
            # every real over-claim — including all three Codex had flagged.
            if DENIAL.search(sentence):
                continue
            for pat, label in OVERCLAIM:
                if re.search(pat, sentence, re.I):
                    offenders.append(
                        f"{f.relative_to(REPO).as_posix()}:{n} claims {label}\n"
                        f"        {sentence[:88]}")
                    break
    if offenders:
        failures.append(
            "language asserting more than CONVENTION_ONLY supports:\n      "
            + "\n      ".join(offenders) +
            "\n      MC-1 forbids these claims while enforcement is by "
            "convention. Restate as\n      detection that holds when the checks "
            "run faithfully, or negate the claim explicitly.")
    else:
        ok(f"{len(scanned)} covered files carry no unqualified proof, "
           "immutability or prevention claim")

    # ---- B01-F09: an approval does not outlive its own evidence ----
    # Codex, cycle 02: "evaluate still checks only the decision and component
    # hashes, ignoring the recorded evidence and reviewed_target hashes. After
    # recording approval in a fixture, deleting all four bootstrap evidence
    # files left evaluate returning (True, [])."
    print()
    print("an approval is bound to the review it rests on (B01-F09)")

    def approved_repo() -> Path:
        root = build(); made.append(root)
        if approve(root).returncode != 0:
            failures.append("fixture: could not record the approval")
        return root

    t = approved_repo()
    if gate(t, "check").returncode != 0:
        failures.append("fixture: a fresh approval does not pass check")
    else:
        ok("a fresh approval passes")

    # Delete the evidence. The components are untouched, so the old check had
    # nothing to say and returned approved.
    t = approved_repo()
    for n in EVIDENCE:
        (t / "bootstrap-review" / n).unlink()
    r = gate(t, "check")
    if r.returncode == 0:
        failures.append("the approval survived deletion of every piece of "
                        "review evidence it rests on")
    elif "nobody can now read" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the missing evidence\n{r.stdout}")
    else:
        ok("refused: the review evidence the approval rests on is gone")

    # Edit one file rather than removing it. An approval covers the review that
    # happened, not a later revision of it.
    t = approved_repo()
    p = t / "bootstrap-review" / "codex-output-raw.md"
    write_lf(p, p.read_text(encoding="utf-8") + "\nan extra finding\n")
    r = gate(t, "check")
    if r.returncode == 0:
        failures.append("the approval survived an edit to the raw review output")
    elif "has changed since the decision" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the altered evidence\n{r.stdout}")
    else:
        ok("refused: the recorded review output was edited after the decision")

    # And the frozen target it was bound to.
    t = approved_repo()
    tp = t / TARGET
    write_lf(tp, tp.read_text(encoding="utf-8").replace('"cycle": 1', '"cycle": 2'))
    r = gate(t, "check")
    if r.returncode == 0:
        failures.append("the approval survived an edit to the reviewed target")
    elif "reviewed target has changed" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the altered target\n{r.stdout}")
    else:
        ok("refused: the reviewed target was edited after the decision")

    # ---- rulings 1 and 2: the exception is bounded, and ends one way ----
    # "Without a precise termination point, 'bootstrap' can become an indefinite
    # exemption." The termination is the first runner approval, so these ask
    # whether the gate actually notices it and whether the notice can be undone.
    print()
    print("the bootstrap exception ends at the first approved runner")

    def git(root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True)

    def git_repo() -> Path:
        root = build(); made.append(root)
        git(root, "init", "-q")
        git(root, "config", "user.email", "t@t")
        git(root, "config", "user.name", "t")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "fixture")
        return root

    def approve_runner(root: Path, *extra: str) -> subprocess.CompletedProcess:
        return gate(root, "approve-runner", "--runner", "scripts/run_review.py",
                    "--decided-by", "Alex Zamurko",
                    "--note", "#gap, 10 Sep 2026 09:00, Alex Zamurko: approved "
                              "as ACTIVE_REVIEW_RUNNER",
                    "--review", TARGET, *extra)

    t = git_repo()
    r = gate(t, "exception")
    if "BOOTSTRAP_EXCEPTION: AVAILABLE" not in r.stdout:
        failures.append(f"the exception should be available before any runner "
                        f"approval\n{r.stdout}{r.stderr}")
    else:
        ok("before any runner approval the exception is available")

    if approve(t).returncode != 0:
        failures.append("fixture: could not record the bootstrap approval")
    r = approve_runner(t)
    if r.returncode != 0:
        failures.append(f"approving a runner was refused:\n{r.stdout}{r.stderr}")
    elif not list((t / "runner-approvals").glob("*.json")):
        failures.append("approve-runner wrote no record")
    else:
        ok("a runner can be approved once the bootstrap review holds")

    r = gate(t, "exception")
    if "BOOTSTRAP_EXCEPTION: ENDED" not in r.stdout:
        failures.append(f"the exception did not end at the first runner "
                        f"approval\n{r.stdout}")
    else:
        ok("the first runner approval ends the exception")

    # B02-F08. runner_approvals_in_history returned [] when git failed, the same
    # value it returns for a clean search that found nothing, so an unreadable
    # history read as "no approval was ever recorded" and the exception came
    # back available. Codex proved it by injecting exit 128; a directory that
    # was never a git repository reaches the same code by an honest route.
    #
    # The control immediately above this section is what makes this one mean
    # something: in a real repository with no approvals the exception IS
    # available, so a refusal here is about the unreadable history and not about
    # fixtures generally being refused.
    tng = build(); made.append(tng)
    # C03-F02 gave every fixture a repository, because a scope change has to
    # exist as a commit. This control needs the opposite and says so rather than
    # relying on the builder's silence: the premise is a history that cannot be
    # read, and a fixture that happens not to be a repository is the honest way
    # to reach it.
    force_rmtree(tng / ".git")
    if (tng / ".git").exists():
        failures.append("the fixture still has a repository, so the control "
                        "below is not about an unreadable history")
    r = gate(tng, "exception")
    blob = r.stdout + r.stderr
    if "BOOTSTRAP_EXCEPTION: AVAILABLE" in r.stdout:
        failures.append(
            "the exception was reported available in a repository whose history "
            "cannot be read. Deletion resistance rests entirely on that query, "
            "so this grants the exception on the strength of not having "
            "checked.")
    elif "cannot be determined" not in blob:
        failures.append(f"the exception was withheld, but not because the "
                        f"history could not be read\n      "
                        f"{blob.strip()[:200]}")
    else:
        ok("the exception is withheld when the history cannot be read")

    # The one that matters. If the gate decided by listing a directory, deleting
    # the directory would reopen the exception and nothing would show it had ever
    # ended. Ruling 2 ends it at the first approval, not at the last surviving
    # copy of the file.
    git(t, "add", "-A")
    git(t, "commit", "-qm", "runner approved")
    shutil.rmtree(t / "runner-approvals")
    r = gate(t, "exception")
    if "BOOTSTRAP_EXCEPTION: ENDED" not in r.stdout:
        failures.append("deleting the approval reopened the exception; the "
                        f"termination is not one-way\n{r.stdout}")
    elif "no longer on disk" not in r.stdout:
        failures.append(f"the deletion was not reported\n{r.stdout}")
    else:
        ok("deleting the approval does not reopen the exception, and the "
           "deletion is named")

    # B02-F08. This control used to assert the opposite: that an uncommitted
    # approval could be deleted and the exception would reopen. It passed, and
    # it was documenting the bypass as correct behaviour while the cycle-02
    # prompt described the arrangement as enforcement. Codex found both.
    #
    # approve-runner now commits the record in the same action that writes it,
    # so there is no uncommitted window to exploit. The control asserts that.
    t2 = git_repo()
    approve(t2)
    r = approve_runner(t2)
    if r.returncode != 0:
        failures.append(f"approve-runner failed: {r.stdout}{r.stderr}")
    elif "committed" not in r.stdout:
        failures.append(f"approve-runner did not commit the record\n{r.stdout}")
    else:
        st = git(t2, "status", "--porcelain", "--", "runner-approvals")
        if st.stdout.strip():
            failures.append("the approval is still uncommitted after "
                            f"approve-runner: {st.stdout.strip()!r}")
        else:
            ok("approve-runner commits the record, leaving no uncommitted "
               "window to delete")

    shutil.rmtree(t2 / "runner-approvals")
    r = gate(t2, "exception")
    if "BOOTSTRAP_EXCEPTION: ENDED" not in r.stdout:
        failures.append("deleting the approval written by approve-runner "
                        f"reopened the exception\n{r.stdout}")
    else:
        ok("an approval written by approve-runner survives deletion")

    # And a run created under the exception cannot keep freezing cycles once it
    # has ended. Returning early for any EXEMPT run was the other half of
    # B02-F08: new exempt runs were blocked, existing ones went on working.
    def runner(root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(root / "scripts" / "run_review.py"), *args],
            cwd=str(root), capture_output=True, text=True)

    t2b = git_repo()
    r = runner(t2b, "init", "--run", "E-001", "--bootstrap-exempt",
               "--protocol", "specs/evidence-schema-v1.0.md",
               "--spec", "specs/evidence-schema-v1.0.md")
    if r.returncode != 0:
        failures.append(f"fixture: exempt init failed\n{r.stderr}{r.stdout}")
    else:
        approve(t2b)
        approve_runner(t2b)
        r = runner(t2b, "freeze", "--run", "E-001", "--type", "plan",
                   "--prompt", "specs/evidence-schema-v1.0.md",
                   "--file", "specs/evidence-schema-v1.0.md")
        if r.returncode == 0:
            failures.append("an existing exempt run froze a cycle after the "
                            "bootstrap exception had ended")
        elif "exception has ended" not in (r.stdout + r.stderr):
            failures.append(f"refused, but not for the ended exception\n"
                            f"{r.stderr}{r.stdout}")
        else:
            ok("an existing exempt run cannot freeze once the exception has "
               "ended")

    # And the flag itself has to stop working, not merely be discouraged.
    t3 = git_repo()
    approve(t3)
    approve_runner(t3)
    r = subprocess.run(
        [sys.executable, str(t3 / "scripts" / "run_review.py"), "init",
         "--run", "X-001", "--bootstrap-exempt",
         "--protocol", "specs/evidence-schema-v1.0.md",
         "--spec", "specs/evidence-schema-v1.0.md"],
        cwd=str(t3), capture_output=True, text=True)
    if r.returncode == 0:
        failures.append("--bootstrap-exempt still created a run after the "
                        "exception ended")
    elif "no longer available" not in (r.stdout + r.stderr):
        failures.append(f"init refused, but not because the exception ended\n"
                        f"{r.stdout}{r.stderr}")
    else:
        ok("--bootstrap-exempt is refused once a runner has been approved")

    print()
    for d in made:
        shutil.rmtree(d, ignore_errors=True)
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("every refusal fired, and approval does not outlive the code it covered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
