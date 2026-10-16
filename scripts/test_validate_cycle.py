#!/usr/bin/env python3
"""Negative controls for the MC-2 conformance gate.

Every one of the fifteen checks is demonstrated failing on a fixture built to
break exactly that check, and clean plan and implementation cycles are
demonstrated passing.

A gate whose checks are never shown to fail is the defect class the v1.0
gate-hardening milestone found thirteen times: a check that cannot come back
false reports success while testing nothing.

Checks 11 to 15 apply to implementation review only. That creates a second way
to build the same defect: report them PASS on a plan cycle they never examined.
So this suite also asserts they come back N/A there, and that N/A is distinct
from PASS in the output.

    python scripts/test_validate_cycle.py

Exit 0 = every expectation held.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent

sys.path.insert(0, str(SRC))
# B01-F07: the control derives the expected spec digest from the same function
# the gate and the runner use. Computing it here by hand would make this suite a
# third implementation of the format, and three copies of a rule disagree even
# more readily than two.
import run_pins  # noqa: E402


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def make_repo() -> tuple[Path, str, str]:
    """A throwaway repo so REPO resolves to the fixture. Returns (root, commit, tree)."""
    tmp = Path(tempfile.mkdtemp(prefix="mc2-")).resolve()
    (tmp / "scripts").mkdir()
    # run_pins comes too: the gate imports it for the shared spec-digest format
    # (B01-F07). Without it validate_cycle dies at import, emits no check marks,
    # and every control in this suite reports the wrong thing. test_ledger.py
    # was broken in exactly this way on 14 September by the same kind of change.
    for _n in ("validate_cycle.py", "run_pins.py"):
        shutil.copy2(SRC / _n, tmp / "scripts" / _n)
    write_lf(tmp / "plan.md", "# plan\n\nbody\n")
    write_lf(tmp / "candidate.diff", "--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n")
    write_lf(tmp / "tests.txt", "ok 1 - everything\n")
    sh("git", "init", "-q", cwd=tmp)
    sh("git", "config", "user.email", "t@t", cwd=tmp)
    sh("git", "config", "user.name", "t", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "fixture", cwd=tmp)
    commit = sh("git", "rev-parse", "HEAD", cwd=tmp).stdout.strip()
    tree = sh("git", "rev-parse", "HEAD^{tree}", cwd=tmp).stdout.strip()
    return tmp, commit, tree


def build(root: Path, commit: str, tree: str, kind: str = "plan",
          mutate=None, sibling: dict | None = None, approval: bool = True) -> Path:
    review = root / "runs" / "T-001" / f"{kind}-review"
    cycle = review / "cycle-01"
    cycle.mkdir(parents=True)

    # B01-F07, the half cycle 04 found still open. Check 9 used to compare the
    # target's governing digests with each other, so these fixtures needed no
    # run at all. It now replays the run's pin history and requires the recorded
    # set to be the one that history produces, which means the fixture has to
    # own a run for its claims to be about.
    #
    # The pins here are the ones _governed() writes into the target. A fixture
    # whose run disagreed with its own targets would make every control below
    # fail for that reason instead of the one it names.
    write_lf(root / "runs" / "T-001" / "run.json", json.dumps({
        "run_id": "T-001",
        "bootstrap_review": "APPROVED",
        "mc1_enforcement": "CONVENTION_ONLY",
        "protocol": {"path": "specs/protocol.md", "sha256": "a" * 64},
        "spec_files": [{"path": "specs/spec.md", "sha256": "b" * 64}],
    }, indent=2) + "\n")

    target = {
        "review_type": kind,
        "run_id": "T-001",
        "cycle": 1,
        "protocol_commit": commit,
        "protocol_sha256": "2" * 64,
        "spec_sha256": "0" * 64,
        "frozen_at": "2026-09-08T13:40:00Z",
    }
    plan_hash = sha256_file(root / "plan.md")
    if kind == "plan":
        target["plan_files"] = [{"path": "plan.md", "sha256": plan_hash}]
        # Preserved copy: check 9 validates the snapshot, not the live tree,
        # so a cycle survives the repairs its review asked for.
        snap = cycle / "artifacts" / "plan.md"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes((root / "plan.md").read_bytes())
    else:
        target.update({
            "candidate_commit": commit,
            "candidate_tree_hash": tree,
            "approved_plan_hash": plan_hash,
            "diff_path": "candidate.diff",
            "diff_hash": sha256_file(root / "candidate.diff"),
            "test_result_path": "tests.txt",
            "test_result_hash": sha256_file(root / "tests.txt"),
        })
        if approval:
            write_lf(root / "runs" / "T-001" / "plan-approval" / "approval.json",
                     json.dumps({"decision": "APPROVE",
                                 # B01-F06: name the artifact, or check 13 can
                                 # only compare a hash with a copy of itself.
                                 "approved_plan_path": "plan.md",
                                 "approved_plan_hash": plan_hash}, indent=2))

    if mutate:
        target = mutate(target, cycle, root) or target

    write_lf(cycle / "target.json", json.dumps(target, indent=2))
    digest = sha256_file(cycle / "target.json")
    write_lf(cycle / "target.sha256", digest + "\n")
    write_lf(cycle / "codex-input.md", f"Review target {digest}\n\n(contents)\n")
    write_lf(cycle / "codex-output-raw.md", "C01-F01 | UNTESTED RULE | R-B7 | ...\n")

    if sibling is not None:
        sib = review / "cycle-02"
        sib.mkdir()
        write_lf(sib / "target.json", json.dumps(sibling, indent=2))
    return cycle


def run(root: Path, cycle: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(root / "scripts" / "validate_cycle.py"),
                        str(cycle)], capture_output=True, text=True)
    return r.returncode, r.stdout


def marks(output: str) -> dict[int, str]:
    out = {}
    for line in output.splitlines():
        s = line.strip()
        if s and s[0].isdigit() and "[" in s and "]" in s:
            try:
                n = int(s.split(".", 1)[0])
            except ValueError:
                continue
            out[n] = s[s.index("[") + 1:s.index("]")].strip()
    return out


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def fresh():
        root, commit, tree = make_repo()
        made.append(root)
        return root, commit, tree

    def expect_fail(label: str, check: int, kind: str, mutate=None,
                    also: tuple[int, ...] = (), **kw) -> None:
        """One mutation, one red check.

        Fixture-validity audit, Alex Zamurko 16 September: "each negative
        control should first establish that its fixture satisfies all
        prerequisites except the single condition it intends to violate."

        The builder and the two clean-cycle controls above already give half of
        that: every fixture here comes from the same builder, which is shown to
        pass unmutated. The half that was missing is the other direction. This
        asserted the intended check went red and never asked what else did, so a
        mutation that broke four checks satisfied a control about one of them,
        and the control would have stayed green if its own check had stopped
        being reachable.

        `also` names checks a mutation legitimately takes with it — a malformed
        target.json cannot be read by anything downstream of it — so that the
        cascade is declared per control rather than tolerated everywhere.
        """
        root, commit, tree = fresh()
        cycle = build(root, commit, tree, kind, mutate=mutate, **kw)
        rc, out = run(root, cycle)
        if rc == 0:
            failures.append(f"{label}: expected FAIL, gate passed")
            return
        got = marks(out)
        if got.get(check) != "FAIL":
            failures.append(f"{label}: expected check {check} to FAIL, "
                            f"it was {got.get(check)!r}")
            return
        collateral = sorted(n for n, v in got.items()
                            if v == "FAIL" and n != check and n not in also)
        if collateral:
            failures.append(
                f"{label}: check {check} failed as intended, and so did "
                f"{collateral}. The fixture violates more than the one "
                f"condition this control is about, so it does not show that "
                f"check {check} is what caught it. Declare the cascade with "
                f"also=(...) if it is genuine.")
            return
        print(f"  [ok] check {check:>2} fails on: {label}")

    # ---- B01-F07: the governing digests are checked, not merely present ----
    # Check 7 confirmed protocol_sha256 and spec_sha256 EXIST and stopped there.
    # Codex set both to the literal "not-a-hash", recomputed target.sha256, and
    # MC-2 returned PASS. The protocol's check 9 is "recorded hashes match the
    # referenced artifacts", so that is where this belongs; it needed no new
    # check and no change to the schema.
    def _governed(protocol_hash: str | None = None,
                  spec_hash: str | None = None,
                  drop_hashes: bool = False,
                  drop_pins: bool = False,
                  remove: str | None = None,
                  edit: str | None = None,
                  claim_preserved: bool = False):
        """A target carrying a governing pin set, as freeze writes since B02-F06.

        C01-F03 changed what this has to provide. The pins used to be "a" * 64
        and "b" * 64 for files whose contents nobody looked at, which was a
        valid fixture while check 9 compared records with records. Check 9 now
        verifies the artifacts too, so a target recording a digest no file has
        is not a baseline any more; it is the defect.

        So the files are written and the recorded digests are theirs. Each
        override still takes a literal, and `None` means "the real one", which
        keeps every control below breaking exactly one thing.
        """
        def _m(target, cycle, root):
            write_lf(root / "specs" / "protocol.md", "# protocol\n\nrules\n")
            write_lf(root / "specs" / "spec.md", "# spec\n\nrequirements\n")
            pins = {"specs/protocol.md": sha256_file(root / "specs/protocol.md"),
                    "specs/spec.md": sha256_file(root / "specs/spec.md")}
            run_dir = root / "runs" / "T-001"
            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            run["protocol"] = {"path": "specs/protocol.md",
                               "sha256": pins["specs/protocol.md"]}
            run["spec_files"] = [{"path": "specs/spec.md",
                                  "sha256": pins["specs/spec.md"]}]
            write_lf(run_dir / "run.json", json.dumps(run, indent=2) + "\n")

            if not drop_pins:
                target["governing_pins"] = sorted(pins)
            if not drop_hashes:
                target["governing_pin_hashes"] = pins
            target["protocol_sha256"] = (
                protocol_hash if protocol_hash is not None
                else pins["specs/protocol.md"])
            target["spec_sha256"] = (
                spec_hash if spec_hash is not None
                else run_pins.spec_digest([{"path": "specs/spec.md",
                                            "sha256": pins["specs/spec.md"]}]))
            if claim_preserved:
                target["governing_artifacts_preserved"] = True
            # Last, so the records above describe the file as it was.
            if remove:
                (root / remove).unlink()
            if edit:
                write_lf(root / edit,
                         "# edited after the digest was recorded\n")
            return target
        return _m

    # What these controls do NOT cover, found by probing rather than assumed:
    # changing the digest FORMAT in run_pins leaves every control here green,
    # because they ask that same function for the expected value. They test that
    # the gate and the writer share one definition, not that the definition is
    # the documented one. The control that pins the format is in
    # test_run_review.py, "spec_sha256 is not reproducible from its documented
    # definition", which recomputes it by hand. Both roles are needed; neither
    # substitutes for the other.
    #
    # The baseline first. Without it every refusal below could be refusing for
    # some unrelated reason and the controls would look green while proving
    # nothing, which is what cycle 03 caught in B01-F11's control.
    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "plan", mutate=_governed()))
    if rc != 0 or marks(out).get(9) != "PASS":
        failures.append(f"a cycle whose digests DO describe its governing set "
                        f"was refused, so the refusals below establish "
                        f"nothing:\n{out}")
    else:
        print("  [ok] check  9 passes on digests that match the governing set")

    # ---- C02-F08: absence of a base is age, or it is a diff bound to nothing ----
    # Check 14 derives the change set from the target's two commits and compares
    # it with the digest recorded at freeze. Implementation cycles frozen before
    # that existed carry neither, and refusing them would invalidate completed
    # work, which is the retroactive invalidation Alex Zamurko ruled out on
    # 10 September. So they are exempt.
    #
    # C02-F03 is what happens when that exemption is granted on absence alone: a
    # modern target simply omits the fields and skips the check. The same
    # distinction, in the place it would otherwise arrive next. A cycle frozen
    # recently enough to preserve its governing artifacts was frozen by a runner
    # that derives diffs, so from that cycle absence is not age.
    def _modern_no_base(t, c, root):
        t = _governed(claim_preserved=True)(t, c, root) or t
        for _rel in ("specs/protocol.md", "specs/spec.md"):
            _dst = c / "artifacts" / _rel
            _dst.parent.mkdir(parents=True, exist_ok=True)
            _dst.write_bytes((root / _rel).read_bytes())
        return t

    # also=(13, 15): C02-F09 made the same marker govern the implementation
    # snapshots, and this fixture has no artifacts directory at all. So a target
    # declaring preservation while preserving nothing legitimately fails three
    # checks, and the cascade is declared rather than quietly tolerated. The
    # audit caught it on the first run, which is what it is for.
    expect_fail("an implementation cycle claiming preserved governing "
                "artifacts while its diff is bound to no commits",
                14, "implementation", mutate=_modern_no_base, also=(13, 15))

    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "implementation"))
    if rc != 0 or marks(out).get(14) != "PASS":
        failures.append(
            f"an implementation cycle carrying no base and no marker of the "
            f"freeze that introduced it was refused. That is the shape of "
            f"evidence frozen before C02-F08, and refusing it invalidates "
            f"completed cycles retroactively. The control above would then be "
            f"passing for the wrong reason:\n{out}")
    else:
        print("  [ok] check 14 still exempts a diff with nothing to date it")

    # ---- C02-F03, second pass: the record says what it is ----
    # Cycle 03 raised this again. Dating a target by the fields it happens to
    # carry means the list has to grow every time the freezer learns to write
    # something, and until it does, a modern target stripped back to the bone
    # reads as historical. Codex: "this does not require erasing every
    # indication of a modern freeze."
    #
    # Each control below removes the governing set and then adds back exactly
    # one thing, so what fires is attributable to that one thing.
    def _stripped_with(extra: dict):
        _base = _governed(drop_pins=True, drop_hashes=True)

        def _m(t, c, root):
            t = _base(t, c, root) or t
            t.update(extra)
            return t
        return _m

    expect_fail("a target declaring an evidence format while omitting the "
                "governing set it was frozen with",
                9, "plan",
                mutate=_stripped_with({"evidence_format": "cycle-target/1"}))

    # Codex's own fixture: the auxiliary manifest alone dates the record, and
    # before this it was not consulted.
    expect_fail("a target dated only by its auxiliary evidence manifest",
                9, "plan",
                mutate=_stripped_with({"auxiliary_evidence_sha256": "e" * 64}))

    # An unknown format, with the governing set intact so nothing else can be
    # what fails. Accepting it would be reading "newer than me" as "fine",
    # which is the same abdication as reading absence as age.
    def _with_format(value: str):
        _base = _governed()

        def _m(t, c, root):
            t = _base(t, c, root) or t
            t["evidence_format"] = value
            return t
        return _m

    expect_fail("a target declaring an evidence format this gate does not know",
                9, "plan", mutate=_with_format("cycle-target/99"))

    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "plan",
                              mutate=_with_format("cycle-target/1")))
    if rc != 0 or marks(out).get(9) != "PASS":
        failures.append(
            f"a target declaring the current evidence format, with a complete "
            f"governing set, was refused. The control above would then be "
            f"failing on the format field rather than on the value:\n{out}")
    else:
        print("  [ok] check  9 accepts the format it knows, with a complete "
              "governing set")

    expect_fail("a protocol digest that is not a digest", 9, "plan",
                mutate=_governed("not-a-hash"))
    expect_fail("a protocol digest that is well formed but not this cycle's",
                9, "plan", mutate=_governed("c" * 64))
    expect_fail("a spec digest that does not describe the governing set",
                9, "plan", mutate=_governed(spec_hash="d" * 64))
    expect_fail("governing pins declared with no hashes to check them against",
                9, "plan", mutate=_governed(drop_hashes=True))

    # ---- C02-F03: the exemption for old evidence, claimed by new evidence ----
    # Check 9 skipped the governing checker entirely when both fields were
    # absent, reading absence as evidence older than the fields. Cycle 02:
    # "a modern target can keep its explicit claim to have preserved governing
    # artifacts while omitting both governing-set fields. Check 9 then skips all
    # governing digest, run-history, chain, and artifact checks."
    #
    # The negative and the positive have to sit together, because the repair is
    # a distinction rather than a rule. Refusing both would be easy and would
    # retroactively invalidate BOOTSTRAP-001's first two cycles, which is the
    # thing the exemption exists to prevent.
    expect_fail("both governing fields removed from a target that still claims "
                "its artifacts were preserved",
                9, "plan", mutate=_governed(drop_pins=True, drop_hashes=True,
                                            claim_preserved=True))

    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "plan",
                              mutate=_governed(drop_pins=True,
                                               drop_hashes=True)))
    if rc != 0 or marks(out).get(9) != "PASS":
        failures.append(
            f"a cycle carrying no governing fields and no marker of the freeze "
            f"that introduced them was refused. That is the shape of evidence "
            f"frozen before B02-F06, and refusing it invalidates completed "
            f"cycles retroactively, which is what the exemption is for. The "
            f"control above would then be passing for the wrong "
            f"reason:\n{out}")
    else:
        print("  [ok] check  9 still exempts evidence with nothing to date it")

    # The two cycle 04 asked for. Codex: "The named negative controls change one
    # assertion while retaining the other, leaving consistent false assertions
    # untested." Every control above keeps a real pin set and breaks one field.
    # Neither of these does. They make the whole governing set false and
    # internally agreed, which is the target Codex built and the gate passed.
    def _fabricated(target, cycle, root):
        """Codex's reproduction: an invented set that agrees with itself."""
        target["governing_pins"] = ["missing-protocol.md"]
        target["governing_pin_hashes"] = {"missing-protocol.md": "not-a-hash"}
        target["protocol_sha256"] = "not-a-hash"
        target["spec_sha256"] = run_pins.spec_digest([])
        return target

    expect_fail("an invented governing set whose every field agrees with itself",
                9, "plan", mutate=_fabricated)

    # And the same shape with well formed digests, so the syntax check cannot be
    # what catches it. Only replaying the run's history can: these are real
    # looking hashes for a pin set this run never had. Without this control the
    # repair could be nothing but the hex check and still look complete.
    def _foreign(target, cycle, root):
        target["governing_pins"] = ["specs/elsewhere.md"]
        target["governing_pin_hashes"] = {"specs/elsewhere.md": "e" * 64}
        target["protocol_sha256"] = "e" * 64
        target["spec_sha256"] = run_pins.spec_digest([])
        return target

    expect_fail("a well formed governing set the run's history never produced",
                9, "plan", mutate=_foreign)

    # The one that isolates the history replay. Both controls above are also
    # caught by the syntax check or by the protocol-identity check, so neither
    # shows that replaying run.json does any work. This target declares the run's
    # real protocol with its real digest, well formed hashes throughout, and a
    # spec_sha256 correctly derived over its own contents. It is consistent in
    # every way the old check could see. The only thing wrong with it is that the
    # run never pinned specs/invented.md, which nothing but the run's own history
    # can say.
    def _extra_pin(target, cycle, root):
        pins = {"specs/protocol.md": "a" * 64,
                "specs/spec.md": "b" * 64,
                "specs/invented.md": "c" * 64}
        target["governing_pins"] = sorted(pins)
        target["governing_pin_hashes"] = pins
        target["protocol_sha256"] = "a" * 64
        target["spec_sha256"] = run_pins.spec_digest(
            [{"path": "specs/spec.md", "sha256": "b" * 64},
             {"path": "specs/invented.md", "sha256": "c" * 64}])
        return target

    expect_fail("a governing set carrying a spec the run never pinned, "
                "self-consistent in every other way", 9, "plan",
                mutate=_extra_pin)

    # C01-F04. Every control above breaks something in the TARGET. This one
    # leaves the target entirely correct and breaks the history it was derived
    # from, which nothing in the target can show.
    #
    # The gate called `load_amendments` and `pin_hashes_for_cycle` and neither
    # `validate_chain` nor `check_frozen_assignments`. The freeze path called
    # all four. So the runner could reject a governing history while the gate
    # accepted a completed cycle conducted against it.
    #
    # Codex's amendment: `prior_pin_set` names `never-pinned.md`, a set this
    # run never held. Direct chain validation refuses it with "amendment 0
    # does not follow the pin history". The replay nevertheless produces the
    # set actually recorded, so every comparison check 9 was able to make
    # agreed, and MC-2 exited 0 with checks 1 to 10 passing.
    #
    # The target has to carry a governing set for this to reach check 9 at all.
    # Without one it is a cycle frozen before `governing_pin_hashes` existed,
    # the governing comparison is skipped, and the control passes while testing
    # nothing. That is how the first version of this control reported "gate
    # passed": it was right, and it was right about a fixture that never got
    # near the code under test.
    def _invalid_chain(target, cycle, root):
        _governed()(target, cycle, root)
        run_dir = root / "runs" / "T-001"
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        final = list(run_pins.initial_pin_set(run))
        write_lf(run_dir / "pin-amendments.json", json.dumps({
            "schema": run_pins.SCHEMA,
            "amendments": [{
                "reason": "fixture: a prior set this run never held, replaying "
                          "to exactly the set the target already records",
                "affected_artifacts": final,
                "prior_pin_set": ["never-pinned.md"],
                "new_pin_set": final,
                "effective_cycle": 1,
                "authorized_by": "review fixture",
                "at": "2026-09-26T00:00:00Z"}]}, indent=2) + "\n")
        return target

    expect_fail("an amendment history the runner rejects, replayed by the gate "
                "without checking it", 9, "plan", mutate=_invalid_chain)

    # C01-F03. Every control so far compares records. Codex established a
    # passing fixture with real governing files and their real digests
    # recorded consistently in the run and the target, then deleted both files
    # without changing either record. The validator still exited 0.
    #
    # "Agreement between the target and run history does not establish that
    # the mandatory governing artifacts are present or that their contents
    # match the recorded hashes."
    #
    # The baseline above already covers the passing case: `_governed()` now
    # writes real files and records their real digests, so check 9 passing
    # there means the artifacts were found and matched.
    #
    # Independently, as the correction asks: each artifact class on its own,
    # so neither refusal can be resting on the other.
    expect_fail("the governing protocol is gone, every record still agreeing",
                9, "plan", mutate=_governed(remove="specs/protocol.md"))
    expect_fail("a governing spec is gone, every record still agreeing",
                9, "plan", mutate=_governed(remove="specs/spec.md"))
    expect_fail("the governing protocol was edited after its digest was "
                "recorded", 9, "plan", mutate=_governed(edit="specs/protocol.md"))
    expect_fail("a governing spec was edited after its digest was recorded",
                9, "plan", mutate=_governed(edit="specs/spec.md"))

    # And the claim that a cycle preserved its governing copies has to be
    # load-bearing. Without this, deleting a snapshot from a cycle frozen by
    # the current runner would fall back to the live file and pass whenever
    # the live file still happened to match, which is the whole defect one
    # level down.
    expect_fail("a cycle claiming preserved governing copies that are not "
                "there", 9, "plan", mutate=_governed(claim_preserved=True))

    # ---- C01-F07: uniqueness among siblings is not identity ----
    # Check 7 asked only whether two targets claimed the same cycle number. It
    # never asked whether a target's number was its own directory's, or its
    # run_id the run it sits in.
    #
    # Those fields are read by different components and read differently:
    # cycle_dirs() takes the cycle number from the DIRECTORY NAME, while
    # _governing_problems selects the pin history with target["cycle"] and
    # cmd_record writes the findings record's cycle from the same field. So
    # one accepted cycle could count as cycle 1 for event projection while
    # being validated against cycle 2's governing pins.
    #
    # Codex tested the mismatches independently on passing fixtures, updating
    # the target hash each time, and both exited 0 with checks 1 to 10 PASS.
    print()
    print("cycle identity: the directory, the target, the run (C01-F07)")

    def _says(field, value):
        def _m(target, cycle, root):
            target[field] = value
            return target
        return _m

    expect_fail("directory cycle-01 with a target that says cycle 2",
                7, "plan", mutate=_says("cycle", 2))
    expect_fail("a target claiming a run it does not sit in",
                7, "plan", mutate=_says("run_id", "ANOTHER-RUN"))
    expect_fail("a plan target sitting in the plan-review directory but "
                "declaring itself an implementation review",
                7, "plan", mutate=_says("review_type", "implementation"),
                # Declaring the other review type legitimately takes checks 11
                # to 15 with it: they become applicable and the plan fixture
                # carries none of what they require. The identity check is
                # still the one that catches the lie.
                also=(9, 11, 12, 13, 14, 15))

    # The one the correction asks for by name. Across a pin amendment the two
    # cycle numbers select DIFFERENT governing documents, so the mismatch is
    # not a bookkeeping slip: the cycle would be validated against a spec set
    # it was never conducted under. Check 9 goes red too, which is the point,
    # and check 7 is what names the cause.
    def _mismatch_across_amendment(target, cycle, root):
        _governed()(target, cycle, root)
        run_dir = root / "runs" / "T-001"
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        prior = list(run_pins.initial_pin_set(run))
        write_lf(root / "specs" / "later.md", "# added by amendment\n")
        after = sorted(prior + ["specs/later.md"])
        write_lf(run_dir / "pin-amendments.json", json.dumps({
            "schema": run_pins.SCHEMA,
            "amendments": [{
                "reason": "fixture: a pin set that differs between cycle 1 "
                          "and cycle 2, so the two numbers are not "
                          "interchangeable",
                "affected_artifacts": ["specs/later.md"],
                "prior_pin_set": prior,
                "new_pin_set": after,
                "effective_cycle": 2,
                "authorized_by": "review fixture",
                "at": "2026-09-26T00:00:00Z"}]}, indent=2) + "\n")
        target["cycle"] = 2
        return target

    expect_fail("a cycle-number mismatch across a pin-amendment boundary, "
                "where the two numbers govern differently",
                7, "plan", mutate=_mismatch_across_amendment, also=(9,))

    # C02-F05. cycle-1 is not cycle-01, and the two readers disagreed about it.
    # Check 7 matched cycle-(\d+) and the controller's cycle_dirs matched
    # cycle-(\d{2}), so these names were an accepted cycle to conformance and
    # not a cycle at all to the projection that counts them toward the budget.
    # A cycle's findings would sit outside the loop's arithmetic while its
    # target passed every check.
    #
    # The matching positive is `clean plan cycle passes` below: a correctly
    # named directory still validates, so this is one grammar being enforced
    # rather than directories being refused.
    for _bad in ("cycle-1", "cycle-001", "cycle-00"):
        _root, _commit, _tree = fresh()
        _cyc = build(_root, _commit, _tree, "plan")
        _renamed = _cyc.parent / _bad
        _cyc.rename(_renamed)
        _rc, _out = run(_root, _renamed)
        if _rc == 0:
            failures.append(
                f"a directory named {_bad} passed MC-2. The controller does "
                f"not enumerate it, so its findings would sit outside the loop "
                f"while its target passed conformance.")
        elif marks(_out).get(7) != "FAIL":
            failures.append(f"{_bad} was refused, but not by check 7\n{_out}")
        else:
            print(f"  [ok] check  7 fails on: a directory named {_bad}")

    # And the historical case, which must NOT fail. Cycles 01 and 02 of
    # BOOTSTRAP-001 were frozen before governing_pin_hashes existed. Failing
    # them now would invalidate two completed cycles and strip authority from
    # every event recorded in them, which is the retroactive invalidation Alex
    # Zamurko ruled out on 10 September arriving through a check instead of an
    # amendment.
    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "plan"))
    if rc != 0 or marks(out).get(9) != "PASS":
        failures.append(
            "a cycle frozen before governing_pin_hashes existed was refused. "
            f"That invalidates completed history through a new check:\n{out}")
    else:
        print("  [ok] check  9 does not invalidate cycles older than the field")

    # ---- clean fixtures ----
    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "plan"))
    m = marks(out)
    if rc != 0:
        failures.append(f"clean plan cycle did not pass:\n{out}")
    else:
        print("  [ok] clean plan cycle passes")
        na = [n for n in range(11, 16) if m.get(n) != "N/A"]
        if na:
            failures.append(f"checks {na} should be N/A on a plan cycle, "
                            f"got {[m.get(n) for n in na]}. Reporting PASS for a "
                            f"check that was never evaluated is the defect this "
                            f"gate exists to catch.")
        else:
            print("  [ok] checks 11-15 report N/A on a plan cycle, not PASS")

    root, commit, tree = fresh()
    rc, out = run(root, build(root, commit, tree, "implementation"))
    if rc != 0:
        failures.append(f"clean implementation cycle did not pass:\n{out}")
    else:
        m = marks(out)
        evaluated = [n for n in range(11, 16) if m.get(n) == "PASS"]
        if len(evaluated) != 5:
            failures.append(f"implementation cycle should evaluate 11-15, got {m}")
        else:
            print("  [ok] clean implementation cycle passes all fifteen")

    # ---- checks 1-10 ----
    # These four mutate the cycle AFTER build(), because build() writes the
    # required files last and a mutate hook would be overwritten by it.
    root, commit, tree = fresh()
    cyc = build(root, commit, tree, "plan")
    (cyc / "codex-output-raw.md").unlink()
    rc, out = run(root, cyc)
    if rc == 0 or marks(out).get(4) != "FAIL":
        failures.append("check 4 did not fail on a missing required file")
    else:
        print("  [ok] check  4 fails on: missing required file")

    root, commit, tree = fresh()
    cyc = build(root, commit, tree, "plan")
    write_lf(cyc / "codex-input.md", "")
    rc, out = run(root, cyc)
    if rc == 0 or marks(out).get(5) != "FAIL":
        failures.append("check 5 did not fail on an empty required file")
    else:
        print("  [ok] check  5 fails on: empty required file")

    root, commit, tree = fresh()
    cyc = build(root, commit, tree, "plan")
    write_lf(cyc / "target.sha256", "a" * 64 + "\n")
    rc, out = run(root, cyc)
    if rc == 0 or marks(out).get(6) != "FAIL":
        failures.append("check 6 did not fail on a wrong target.sha256")
    else:
        print("  [ok] check  6 fails on: target.sha256 does not match target")

    expect_fail("duplicate cycle identifier", 7, "plan",
                sibling={"review_type": "plan", "run_id": "T-001", "cycle": 1})
    expect_fail("referenced commit does not resolve", 8, "plan",
                mutate=lambda t, c, r: {**t, "protocol_commit": "deadbeef" * 5})
    expect_fail("declared artifact hash is wrong", 9, "plan",
                mutate=lambda t, c, r: {**t, "plan_files": [
                    {"path": "plan.md", "sha256": "b" * 64}]})
    # C01-F07 added a genuine cascade here rather than a coincidental one: a
    # review_type outside the closed set is also, necessarily, a review_type
    # that disagrees with the plan-review directory the cycle sits in. Both
    # checks are right to fire, and declaring it keeps the control honest
    # about which one it is really about.
    expect_fail("review_type outside the closed set", 9, "plan",
                mutate=lambda t, c, r: {**t, "review_type": "other"},
                also=(7,))

    root, commit, tree = fresh()
    cyc = build(root, commit, tree, "plan")
    write_lf(cyc / "codex-input.md", "Review the plan.\n")
    rc, out = run(root, cyc)
    if rc == 0 or marks(out).get(10) != "FAIL":
        failures.append("check 10 did not fail when the input lacks the target hash")
    else:
        print("  [ok] check 10 fails on: codex-input.md does not carry the target hash")

    root, commit, tree = fresh()
    cyc = build(root, commit, tree, "plan")
    write_lf(cyc / "target.json", "{ not json")
    rc, out = run(root, cyc)
    if rc == 0 or marks(out).get(7) != "FAIL":
        failures.append("check 7 did not fail on unparseable target.json")
    else:
        print("  [ok] check  7 fails on: target.json is not valid JSON")

    # ---- checks 11-15, §10.2 ----
    # An unresolvable candidate commit takes checks 8 and 12 with it: 8 resolves
    # the referenced commit and 12 hashes that commit's tree, so neither has
    # anything left to work on. Declared rather than tolerated, so that a
    # cascade growing a seventh member is a failure and not a shrug.
    expect_fail("candidate commit does not resolve", 11, "implementation",
                also=(8, 12),
                mutate=lambda t, c, r: {**t, "candidate_commit": "deadbeef" * 5})
    expect_fail("candidate tree hash is wrong", 12, "implementation",
                mutate=lambda t, c, r: {**t, "candidate_tree_hash": "a" * 40})
    expect_fail("approved-plan hash disagrees with the approval record", 13,
                "implementation",
                mutate=lambda t, c, r: {**t, "approved_plan_hash": "c" * 64})
    expect_fail("no approval record to match against", 13, "implementation",
                approval=False)
    expect_fail("diff hash does not match the diff", 14, "implementation",
                mutate=lambda t, c, r: {**t, "diff_hash": "d" * 64})
    expect_fail("diff artifact is missing", 14, "implementation",
                mutate=lambda t, c, r: {**t, "diff_path": "nope.diff"})
    expect_fail("test-result hash does not match", 15, "implementation",
                mutate=lambda t, c, r: {**t, "test_result_hash": "e" * 64})
    # Each §10.1 field is consumed by exactly one later check, so removing it
    # fails check 9 for its absence and that check for having nothing to read.
    # The pairing is the point: it says which check owns which field, and if one
    # of these ever cascades somewhere else the control says so.
    #
    # candidate_commit takes 11 and 12 both, because 12 hashes the tree of the
    # commit 11 resolves.
    _consumes = {
        "candidate_commit":   (11, 12),
        "candidate_tree_hash": (12,),
        "approved_plan_hash":  (13,),
        "diff_hash":           (14,),
        "test_result_hash":    (15,),
    }
    for field, downstream in _consumes.items():
        expect_fail(f"§10.1 field absent: {field}", 9, "implementation",
                    also=downstream,
                    mutate=lambda t, c, r, f=field: {k: v for k, v in t.items() if k != f})

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("all negative controls fired; every check is falsifiable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
