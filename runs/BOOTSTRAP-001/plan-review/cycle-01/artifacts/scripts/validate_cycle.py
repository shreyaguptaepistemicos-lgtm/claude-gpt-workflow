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


def _check_hashed_ref(entry, repo_root: Path, label: str) -> list[str]:
    if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
        return [f"{label} must be an object with path and sha256"]
    p = repo_root / entry["path"]
    if not p.is_file():
        return [f"{label} path not found: {entry['path']}"]
    actual = sha256_file(p)
    if actual != entry["sha256"]:
        return [f"{label} hash mismatch for {entry['path']}: "
                f"recorded {entry['sha256']}, actual {actual}"]
    return []


def _hash_of_declared_file(target: dict, hash_field: str, path_field: str,
                           repo_root: Path) -> tuple[bool, str]:
    """Recorded hash present, its artifact resolvable, and the two agree."""
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
    p = repo_root / rel
    if not p.is_file():
        return False, f"{path_field} not found: {rel}"
    actual = sha256_file(p)
    if actual != recorded:
        return False, f"{rel}\n          recorded {recorded}\n          actual   {actual}"
    return True, ""


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
                problems += _check_hashed_ref(entry, repo_root, "plan_files entry")
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
    approval = cycle_dir.parent.parent / "plan-approval" / "approval.json"
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
            ok = str(ap).lower() == str(frozen).lower()
            r.add(13, "approved-plan hash matches the frozen approved plan", ok,
                  "" if ok else f"target   {ap}\n          approval {frozen}")

    # 14-15. diff and test results
    ok14, d14 = _hash_of_declared_file(target, "diff_hash", "diff_path", repo_root)
    r.add(14, "diff hash matches the reviewed diff", ok14, d14)
    ok15, d15 = _hash_of_declared_file(target, "test_result_hash", "test_result_path",
                                       repo_root)
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
