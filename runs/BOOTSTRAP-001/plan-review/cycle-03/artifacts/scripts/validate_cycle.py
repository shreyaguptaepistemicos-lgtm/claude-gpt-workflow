#!/usr/bin/env python3
"""MC-2 conformance gate.

Checks one review cycle against specs/evidence-schema-v1.0.md and MC-2 of the
protocol, which specifies fifteen checks: 1 to 10 for every cycle, and 11 to 15
additionally and unconditionally for implementation review cycles (§10.2).

    python scripts/validate_cycle.py runs/A1E-001/plan-review/cycle-01

Exit 0 = PASS, exit 1 = FAIL, exit 2 = the checker could not run.

A FAIL means REVIEW_CYCLE_STATUS = INVALID: the cycle cannot support a finding
and cannot count toward CONVERGED, STALLED, MAX_4_REACHED, or the four-cycle
budget. It is repaired and rerun, not interpreted.

Checks 11 to 15 apply only to implementation review. On a plan review they are
reported N/A rather than PASS. A check that reports success on a cycle it never
examined is the defect this gate exists to prevent, and it would be perverse to
build one into the gate itself.

Written under the anti-whitelist rule: every check derives its expectation from
the protocol text, and nothing passes because a previous run accepted it.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = ("target.json", "target.sha256", "codex-input.md", "codex-output-raw.md")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")

COMMON_FIELDS = ("review_type", "run_id", "cycle", "protocol_commit",
                 "protocol_sha256", "spec_sha256", "frozen_at")

# §10.1: "These fields are mandatory, not conditional."
IMPL_FIELDS = ("candidate_commit", "candidate_tree_hash", "approved_plan_hash",
               "diff_hash", "test_result_hash")

NA = "N/A"


class Result:
    def __init__(self) -> None:
        self.checks: list[tuple[int, str, object, str]] = []

    def add(self, n: int, name: str, ok: object, detail: str = "") -> object:
        self.checks.append((n, name, ok, detail))
        return ok

    def na(self, n: int, name: str, why: str) -> None:
        self.checks.append((n, name, NA, why))

    @property
    def passed(self) -> bool:
        return all(ok is True or ok == NA for _, _, ok, _ in self.checks)

    def report(self, cycle_dir: Path) -> str:
        lines = [f"MC-2 conformance — {cycle_dir}", ""]
        for n, name, ok, detail in self.checks:
            mark = NA if ok == NA else ("PASS" if ok else "FAIL")
            lines.append(f"  {n:>2}. [{mark:^4}] {name}")
            if detail:
                for ln in detail.splitlines():
                    lines.append(f"          {ln}")
        lines += ["", f"MC2_CONFORMANCE: {'PASS' if self.passed else 'FAIL'}"]
        if not self.passed:
            lines.append("REVIEW_CYCLE_STATUS: INVALID")
            lines.append("This cycle does not count toward the four-cycle budget "
                         "or any loop state. Repair the evidence and rerun.")
        return "\n".join(lines)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo_root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo_root), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return 127, ""


def git_commit_exists(repo_root: Path, commit: str) -> bool:
    return git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}")[0] == 0


def _check_hashed_ref(entry, repo_root: Path, label: str,
                      cycle_dir: Path | None = None) -> list[str]:
    """Validate a bound artifact against the cycle's preserved copy.

    Alex Zamurko, 9 September 2026: "At freeze, snapshot the exact reviewed
    artifact bytes into the cycle evidence directory and validate those
    preserved copies, not the live working tree."

    This used to hash `repo_root / path`, the live file. A completed cycle
    therefore went INVALID the moment anyone repaired what it had reviewed —
    and since the controller ignores events in invalid cycles, acting on a
    review erased it. Repair between cycles is the design; it cannot be what
    destroys the previous cycle.

    The live tree is now irrelevant to a completed cycle's validity. That is the
    point: the evidence is self-contained, and a cycle means the same thing on a
    fresh clone a year later as it does here.
    """
    if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
        return [f"{label} must be an object with path and sha256"]

    snap = (cycle_dir / "artifacts" / entry["path"]) if cycle_dir else None
    if snap is not None and snap.is_file():
        actual = sha256_file(snap)
        if actual != entry["sha256"]:
            return [f"{label} preserved copy of {entry['path']} does not match "
                    f"its record: {entry['sha256']} vs {actual}. The snapshot "
                    "has been altered since the freeze."]
        return []

    return [f"{label} has no preserved copy: expected "
            f"{(snap.relative_to(cycle_dir) if snap else '?')}.\n"
            "A cycle frozen without snapshots cannot be validated, because the "
            "only\nremaining source for the reviewed bytes is a working tree "
            "that has since moved on."]


def _approval_plan_path(approval: Path) -> str | None:
    """Which artifact the approval record's hash is of.

    §7.3 freezes APPROVED_PLAN_HASH but the protocol does not say where the
    path lives, so both places are accepted and either is enough. What is not
    acceptable is neither: a hash with no named artifact can only be compared
    against another copy of itself, which is what B01-F06 was.
    """
    try:
        d = json.loads(approval.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    p = d.get("approved_plan_path")
    if p:
        return p
    files = d.get("approved_plan_files")
    if isinstance(files, list) and len(files) == 1:
        return files[0]
    return None


def _hash_of_declared_file(target: dict, hash_field: str, path_field: str,
                           repo_root: Path,
                           cycle_dir: Path | None = None) -> tuple[bool, str]:
    """Recorded hash present, its artifact resolvable, and the two agree.

    B02-F07. This hashed repo_root/<path> — the live file — while freeze had
    already preserved a copy in artifacts/. Codex: "An implementation fixture
    passed initially with preserved copies present. Changing only its live diff
    and test-result files made checks 14 and 15 fail while the preserved copies
    were unchanged."

    So the snapshot-at-freeze repair was built and then two checks kept reading
    past it. Ordinary later work — a rerun of the tests, a regenerated diff —
    retroactively invalidated a completed cycle, which is the exact failure that
    repair exists to prevent, surviving in the two places it was not applied.

    The preserved copy is authoritative where it exists. Falling back to the
    live file is only for cycles frozen before snapshotting, and it says so.
    """
    recorded = target.get(hash_field)
    if not recorded:
        return False, f"{hash_field} is absent; §10.1 makes it mandatory"
    if not HEX64.match(str(recorded)):
        return False, f"{hash_field} is not a lowercase 64-char hex digest"
    rel = target.get(path_field)
    if not rel:
        return False, (f"{path_field} is absent, so {hash_field} cannot be checked "
                       f"against anything. The protocol requires the hash to match "
                       f"the artifact; the schema records where that artifact is.")
    snap = (cycle_dir / "artifacts" / rel) if cycle_dir else None
    if snap is not None and snap.is_file():
        actual = sha256_file(snap)
        if actual != recorded:
            return False, (
                f"the preserved copy of {rel} does not match its record\n"
                f"          recorded {recorded}\n          actual   {actual}\n"
                "          The snapshot has been altered since the freeze.")
        return True, f"{rel} (preserved copy)"

    p = repo_root / rel
    if not p.is_file():
        return False, f"{path_field} not found: {rel}"
    actual = sha256_file(p)
    if actual != recorded:
        return False, (
            f"{rel}\n          recorded {recorded}\n          actual   {actual}\n"
            "          No preserved copy exists, so this was checked against "
            "the live file.\n          A cycle frozen by the current runner "
            "would have one.")
    return True, f"{rel} (live; no preserved copy)"


def validate(cycle_dir: Path, repo_root: Path) -> Result:
    r = Result()

    # 1-4. required files exist
    missing = [n for n in REQUIRED_FILES if not (cycle_dir / n).is_file()]
    for i, name in enumerate(REQUIRED_FILES, start=1):
        present = (cycle_dir / name).is_file()
        r.add(i, f"{name} exists", present, "" if present else "not found")
    if missing:
        r.add(5, "all required files non-empty", False,
              f"skipped, missing: {', '.join(missing)}")
        for n in range(6, 16):
            r.add(n, "(not reached)", False, "earlier checks failed")
        return r

    # 5. non-empty
    empty = [n for n in REQUIRED_FILES if (cycle_dir / n).stat().st_size == 0]
    r.add(5, "all required files non-empty", not empty,
          f"empty: {', '.join(empty)}" if empty else "")

    # 6. SHA256(target) == target.sha256
    recorded = (cycle_dir / "target.sha256").read_text(encoding="utf-8").strip()
    actual = sha256_file(cycle_dir / "target.json")
    if not HEX64.match(recorded):
        r.add(6, "target.sha256 matches target", False,
              f"target.sha256 is not a lowercase 64-char hex digest: {recorded[:80]!r}")
    else:
        r.add(6, "target.sha256 matches target", recorded == actual,
              "" if recorded == actual else
              f"recorded {recorded}\n          actual   {actual}")

    try:
        target = json.loads((cycle_dir / "target.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        for n, name in ((7, "cycle identifier unique"),
                        (8, "referenced git commit exists"),
                        (9, "mandatory hashed artifacts present and matching")):
            r.add(n, name, False, f"target.json is not valid JSON: {e}"
                  if n == 7 else "target.json unreadable")
        for n, name in _impl_check_names():
            r.add(n, name, False, "target.json unreadable")
        _check_10(r, cycle_dir, recorded)
        return r

    rtype = target.get("review_type")

    missing_fields = [f for f in COMMON_FIELDS if f not in target]
    if missing_fields:
        r.add(7, "cycle identifier unique", False,
              f"target.json missing required fields: {', '.join(missing_fields)}")
    else:
        siblings = [d for d in cycle_dir.parent.iterdir()
                    if d.is_dir() and d != cycle_dir and (d / "target.json").is_file()]
        clashes = []
        for s in siblings:
            try:
                other = json.loads((s / "target.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if other.get("cycle") == target.get("cycle"):
                clashes.append(s.name)
        r.add(7, "cycle identifier unique", not clashes,
              f"cycle {target.get('cycle')} also declared by: {', '.join(clashes)}"
              if clashes else f"cycle {target.get('cycle')} in {cycle_dir.parent.name}")

    # 8. referenced git commit exists
    commits = [v for k, v in target.items()
               if k in ("commit", "protocol_commit", "candidate_commit")]
    if not commits:
        r.add(8, "referenced git commit exists", True, "no commit referenced")
    else:
        bad = [c for c in commits if not git_commit_exists(repo_root, str(c))]
        r.add(8, "referenced git commit exists", not bad,
              f"unresolvable: {', '.join(bad)}" if bad
              else f"resolved: {', '.join(map(str, commits))}")

    # 9. mandatory hashed artifacts for that review type
    problems: list[str] = []
    if rtype == "plan":
        files = target.get("plan_files")
        if not files:
            problems.append("plan review requires a non-empty plan_files list")
        else:
            for entry in files:
                problems += _check_hashed_ref(entry, repo_root, "plan_files entry",
                                             cycle_dir)
    elif rtype == "implementation":
        absent = [f for f in IMPL_FIELDS if not target.get(f)]
        if absent:
            problems.append("§10.1 requires all of: " + ", ".join(absent))
    else:
        problems.append(f"review_type must be 'plan' or 'implementation', got {rtype!r}")
    r.add(9, "mandatory hashed artifacts present and matching", not problems,
          "; ".join(problems))

    _check_10(r, cycle_dir, recorded)

    # 11-15. implementation-specific, §10.2
    if rtype != "implementation":
        why = f"review_type is {rtype!r}; §10.2 applies to implementation review only"
        for n, name in _impl_check_names():
            r.na(n, name, why)
        return r

    # 11. candidate commit is present and exists
    cc = target.get("candidate_commit")
    if not cc:
        r.add(11, "candidate commit present and exists", False, "candidate_commit absent")
    else:
        ok = git_commit_exists(repo_root, str(cc))
        r.add(11, "candidate commit present and exists", ok,
              "" if ok else f"does not resolve in this repository: {cc}")

    # 12. candidate tree hash present and matches the candidate tree
    th = target.get("candidate_tree_hash")
    if not th:
        r.add(12, "candidate tree hash matches the candidate tree", False,
              "candidate_tree_hash absent")
    elif not cc:
        r.add(12, "candidate tree hash matches the candidate tree", False,
              "no candidate_commit to resolve a tree from")
    else:
        code, real = git(repo_root, "rev-parse", f"{cc}^{{tree}}")
        if code != 0:
            r.add(12, "candidate tree hash matches the candidate tree", False,
                  f"could not resolve the tree of {cc}")
        else:
            ok = str(th).lower() == real.lower()
            r.add(12, "candidate tree hash matches the candidate tree", ok,
                  "" if ok else f"recorded {th}\n          actual   {real}")

    # 13. approved-plan hash present and matches the frozen approved plan
    ap = target.get("approved_plan_hash")
    # B02-F07. This read the run-level record directly, so a later approval
    # version changed what an already-completed cycle was validated against.
    # Codex: "Check 13 also depends on the current run-level approval record."
    #
    # The preserved copy is authoritative where it exists, for the same reason
    # the diff and test results are: a cycle is validated against the bytes that
    # were reviewed, not against whatever has replaced them since.
    # The path comes from the target, which is what freeze recorded when it took
    # the snapshot. Deriving it here independently is how the two sides end up
    # looking in different places.
    _appr_rel = target.get("approval_record_path")
    _snap_approval = (cycle_dir / "artifacts" / _appr_rel) if _appr_rel else None
    approval = (_snap_approval
                if _snap_approval is not None and _snap_approval.is_file()
                else cycle_dir.parent.parent / "plan-approval" / "approval.json")
    if not ap:
        r.add(13, "approved-plan hash matches the frozen approved plan", False,
              "approved_plan_hash absent")
    elif not approval.is_file():
        r.add(13, "approved-plan hash matches the frozen approved plan", False,
              f"no approval record at {approval.name}; the protocol freezes "
              "APPROVED_PLAN_HASH at Step 7.3, and without that record this "
              "hash has nothing authoritative to match")
    else:
        try:
            frozen = json.loads(approval.read_text(encoding="utf-8")).get("approved_plan_hash")
        except json.JSONDecodeError:
            frozen = None
        if not frozen:
            r.add(13, "approved-plan hash matches the frozen approved plan", False,
                  "approval record carries no approved_plan_hash")
        else:
            # B01-F06. This used to stop here, comparing two recorded strings.
            # Both records could agree perfectly while the plan itself had
            # changed underneath them, so an implementation cycle passed all
            # fifteen checks against a plan nobody approved. Codex demonstrated
            # exactly that on an isolated fixture.
            #
            # So the artifact is hashed, and the approval's decision is read
            # rather than assumed: an approval record that says
            # RETURN_FOR_REWORK is not an approval, and a hash matching one is
            # matching the wrong thing.
            problems13: list[str] = []
            if str(ap).lower() != str(frozen).lower():
                problems13.append(f"target {ap}\n          approval {frozen}")

            decision = None
            try:
                decision = json.loads(
                    approval.read_text(encoding="utf-8")).get("decision")
            except json.JSONDecodeError:
                pass
            if decision != "APPROVE":
                problems13.append(
                    f"the approval record's decision is {decision!r}, not "
                    "APPROVE; §7.3 freezes APPROVED_PLAN_HASH on approval, so a "
                    "hash carried by any other decision is not an approved plan")

            plan_ref = target.get("approved_plan_path") or _approval_plan_path(approval)
            if not plan_ref:
                problems13.append(
                    "neither the target nor the approval record says which "
                    "artifact the approved-plan hash is of, so the hash cannot "
                    "be checked against anything. Two matching records are not "
                    "an approved plan.")
            else:
                snap = cycle_dir / "artifacts" / plan_ref
                live = repo_root / plan_ref
                src = snap if snap.is_file() else live
                if not src.is_file():
                    problems13.append(f"approved plan not found: {plan_ref}")
                else:
                    actual = sha256_file(src)
                    if actual != str(frozen).lower():
                        problems13.append(
                            f"{plan_ref} does not hash to the approved value\n"
                            f"          approved {frozen}\n"
                            f"          actual   {actual}")

            r.add(13, "approved-plan hash matches the frozen approved plan",
                  not problems13, "; ".join(problems13))

    # 14-15. diff and test results
    ok14, d14 = _hash_of_declared_file(target, "diff_hash", "diff_path",
                                       repo_root, cycle_dir)
    r.add(14, "diff hash matches the reviewed diff", ok14, d14)
    ok15, d15 = _hash_of_declared_file(target, "test_result_hash", "test_result_path",
                                       repo_root, cycle_dir)
    r.add(15, "test-result hash matches the supplied test results", ok15, d15)

    return r


def _impl_check_names():
    return ((11, "candidate commit present and exists"),
            (12, "candidate tree hash matches the candidate tree"),
            (13, "approved-plan hash matches the frozen approved plan"),
            (14, "diff hash matches the reviewed diff"),
            (15, "test-result hash matches the supplied test results"))


def _check_10(r: Result, cycle_dir: Path, recorded: str) -> None:
    ci = (cycle_dir / "codex-input.md").read_text(encoding="utf-8", errors="replace")
    bound = HEX64.match(recorded) is not None and recorded in ci
    r.add(10, "codex-input.md contains target SHA-256 verbatim", bound,
          "" if bound else
          "the input does not carry the frozen target hash, so nothing ties the "
          "reviewed artifact to what the reviewer was shown")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cycle_dir = Path(argv[1]).resolve()
    if not cycle_dir.is_dir():
        print(f"not a directory: {cycle_dir}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    result = validate(cycle_dir, repo_root)
    print(result.report(cycle_dir))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
