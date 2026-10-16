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

sys.path.insert(0, str(Path(__file__).resolve().parent))
# B01-F07: one definition of the spec-set digest, shared with the runner that
# writes it rather than reimplemented here.
import run_pins  # noqa: E402

REQUIRED_FILES = ("target.json", "target.sha256", "codex-input.md", "codex-output-raw.md")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")

COMMON_FIELDS = ("review_type", "run_id", "cycle", "protocol_commit",
                 "protocol_sha256", "spec_sha256", "frozen_at")

# §10.1: "These fields are mandatory, not conditional."
IMPL_FIELDS = ("candidate_commit", "candidate_tree_hash", "approved_plan_hash",
               "diff_hash", "test_result_hash")

# C02-F03. Fields only a freeze that writes the governing set produces.
#
# Several checks read a missing field as evidence older than that field. That
# reading is sound only for a record that carries no trace of the freezer which
# introduced it, and the target now carries one. A record that declares its
# artifacts preserved was written by a freeze that also writes the governing
# set, so the absence of the governing set in it is not age. It is an
# incomplete record, and the historical exemption is not available to it.
#
# One list, consulted through one helper, because the same question is asked of
# the implementation artifacts as well, and a second copy of the rule is how
# the two drift apart. That is the shape seven of cycle 01's eight findings had.
# C02-F09 extended this from one field to three. The same question is asked
# about implementation evidence, and Codex found the implementation side still
# answering it by absence: "the compatibility behavior is described as applying
# to cycles frozen before snapshotting, but the code does not test that
# condition. A target carrying the new governing-preservation marker and an
# explicit approval_record_path still gets the fallback."
#
# Each entry is a field only a freeze from a known date onwards emits, so
# carrying any one of them dates the record.
MODERN_MARKERS = (
    "governing_artifacts_preserved",  # B02-F06, 11 September
    "approval_record_path",           # B02-F07, the implementation snapshot set
    "base_commit",                    # C02-F08, the derived diff
    "auxiliary_evidence_sha256",      # B03-F02, the control manifest
)

NA = "N/A"


def modern_markers(target: dict) -> list[str]:
    """Which markers of a modern freeze this target carries, if any.

    Empty means nothing in the record dates it, which is the only state that
    may be read as predating a field rather than omitting one.

    C02-F03, second pass. A declared evidence format settles the question on its
    own and the marker list is not consulted: the list dates a record by what it
    happens to contain, which cycle 03 showed can be emptied, while a format is
    a record saying what it is. The list stays for targets frozen before the
    field existed, which is the only population it can honestly speak for.
    """
    fmt = target.get("evidence_format")
    if fmt is not None:
        return [f"evidence_format {fmt!r}"]
    return [k for k in MODERN_MARKERS if target.get(k) is not None]


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


def git_unstripped(repo_root: Path, args: list[str]) -> tuple[int, str]:
    """As git() but without stripping, for output that is going to be hashed.

    git() strips, which is right for reading a SHA back and wrong for anything
    whose digest is being compared: the freeze hashed what git printed, and a
    checker that hashes a trimmed copy of the same output disagrees with it on
    every cycle. Separate function rather than a flag, so neither caller can
    reach the wrong behaviour by forgetting one.
    """
    try:
        r = subprocess.run(["git", "-C", str(repo_root), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stdout
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
                           cycle_dir: Path | None = None,
                           strict_markers: list[str] | None = None
                           ) -> tuple[bool, str]:
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

    # C02-F09. The fallback below is for cycles frozen before snapshotting, and
    # until now nothing tested that condition: any missing snapshot was quietly
    # replaced by today's matching live file. Codex: "deleting an implementation
    # cycle's preserved diff, test results, approved plan, or approval record
    # does not necessarily invalidate it... The cycle consequently passes
    # without the preserved evidence it was supposed to retain and becomes
    # dependent on later working-tree changes again."
    #
    # A matching live file is not the point. Preservation is the requirement,
    # and a requirement satisfied by whatever happens to be on disk today is not
    # one. So a record that carries a marker of the freeze that preserves gets
    # no fallback: its snapshot is missing, and that is the finding.
    if strict_markers:
        return False, (
            f"{rel} has no preserved copy under artifacts/, and this target "
            f"declares\n          " + ", ".join(strict_markers) +
            ", which only a freeze that preserves emits.\n          A matching "
            "live file is not a substitute: the cycle would then depend on a\n"
            "          working tree that has moved on, which is what preserving "
            "prevents.")

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


_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _governing_problems(target: dict, gph: dict, run_dir: Path,
                        cycle_dir: Path, repo_root: Path) -> list[str]:
    """Check 9's governing digests, against the run rather than themselves.

    B01-F07, the half cycle 04 found still open. The previous version compared
    the target's assertions with each other: protocol_sha256 had to equal the
    recorded hash of SOME governing pin, and spec_sha256 had to be the digest
    over the rest. Codex wrote a target whose governing set was one file,
    `missing-protocol.md`, which does not exist, carrying the literal
    "not-a-hash", with protocol_sha256 set to the same string and spec_sha256
    set to the digest over the resulting empty remainder. Every comparison
    agreed. Check 9 passed and MC-2 returned PASS.

    Two separate things were wrong.

    Nothing validated the syntax, so a value that is not a digest at all was a
    usable digest. And which pin counted as the protocol was INFERRED from the
    field under test: the old `_owner` picked whichever entry's hash equalled
    protocol_sha256, so the check asked its answer to identify itself. An
    invented set satisfies both conditions as easily as a real one, which is
    why the existing controls stayed green — each changed one assertion and
    kept the other, and none made the whole set false together.

    The comment this replaces said that verifying against run.json and the
    amendment history "would make MC-2 depend on run-level state it does not
    currently read. That is a larger change than this finding, and it is not
    claimed here." Cycle 04 is the finding that says do it. The gate now reads
    the run's own record, replays the pin history for this cycle, and requires
    the recorded set to be the one the run actually produced. The protocol is
    the path the RUN declares, not the entry that happens to match.

    The syntax check below is not load-bearing and is not claimed to be. Any
    value that is not a digest also fails the identity or history comparison,
    because it cannot equal a real hash. It earns its place by failing early
    with a message that names the problem, rather than reporting a mismatch and
    leaving the reader to notice that one side was never a digest at all.

    Still not established, said plainly: this checks the digests against the
    run's history, not the bytes on disk against the digests. An artifact could
    be edited after freeze and both records would still agree. Under
    MC1_ENFORCEMENT: CONVENTION_ONLY that remains detection of record drift and
    is not a statement about the files.
    """
    bad = sorted(f"{p}: {h!r}" for p, h in gph.items()
                 if not _HEX64.match(str(h)))
    bad += [f"{f}: {target.get(f)!r}" for f in ("protocol_sha256", "spec_sha256")
            if not _HEX64.match(str(target.get(f, "")))]
    if bad:
        return ["governing digests that are not digests:\n      "
                + "\n      ".join(bad) +
                "\n      A digest is 64 lowercase hex characters. Anything else "
                "names no artifact, and\n      two such values agreeing with "
                "each other establishes nothing at all."]

    run_json = run_dir / "run.json"
    if not run_json.is_file():
        return [f"the governing digests have nothing independent to be checked "
                f"against:\n      {run_json} does not exist.\n"
                "      A cycle's governing set is a claim about its run. "
                "Without the run's own\n      record the claim can only be "
                "compared with itself, which is the defect this\n      check "
                "was rewritten to stop."]
    try:
        run = json.loads(run_json.read_text(encoding="utf-8"))
        # C01-F04. This called `load_amendments` and `pin_hashes_for_cycle`
        # directly, which replays the history without checking it is a valid
        # one. The freeze path validated the chain and the frozen assignments
        # first, so the runner could reject a governing history while this gate
        # accepted a completed cycle conducted against it. Check 9 was
        # comparing the target against an unchecked reconstruction and
        # reporting that comparison as verification.
        expect = run_pins.governing_pin_hashes(run, run_dir,
                                               int(target["cycle"]))
        declared = str(run["protocol"]["path"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError,
            run_pins.PinError) as e:
        return [f"the run's pin history cannot be replayed, so this cycle's "
                f"governing digests\n      cannot be checked: {e}"]

    if dict(gph) != dict(expect):
        only_here = sorted(set(gph) - set(expect))
        only_run = sorted(set(expect) - set(gph))
        moved = sorted(p for p in set(gph) & set(expect) if gph[p] != expect[p])
        detail = []
        if only_here:
            detail.append("recorded but not in the run's history: "
                          + ", ".join(only_here))
        if only_run:
            detail.append("in the run's history but not recorded: "
                          + ", ".join(only_run))
        for p in moved:
            detail.append(f"{p}\n        recorded {gph[p]}\n        "
                          f"history  {expect[p]}")
        return ["the governing set this cycle records is not the one the run's "
                "history produces\n      for cycle "
                f"{target.get('cycle')}:\n      " + "\n      ".join(detail)]

    if str(gph.get(declared, "")) != str(target.get("protocol_sha256", "")):
        return [f"protocol_sha256 is not the digest of the artifact this run "
                f"declares as its\n      protocol:\n        {declared}\n"
                f"        run history  {gph.get(declared)!r}\n"
                f"        target says  {target.get('protocol_sha256')!r}\n"
                "      Which pin is the protocol comes from the run, not from "
                "whichever entry\n      happens to match the field being "
                "checked."]

    rest = [{"path": p, "sha256": h} for p, h in gph.items() if p != declared]
    want = run_pins.spec_digest(rest)
    if str(target.get("spec_sha256", "")) != want:
        return [f"spec_sha256 does not describe this cycle's governing set\n"
                f"      recorded {target.get('spec_sha256')!r}\n"
                f"      derived  {want!r} over {len(rest)} non-protocol pin(s)"]

    # C01-F03. Everything above compares records with records. None of it
    # establishes that the artifacts those records name exist, or that they
    # say what they said. Codex built a passing fixture with real governing
    # files and real digests, deleted both files without touching either
    # record, and the validator still exited 0 with checks 1 to 10 passing.
    #
    # "Agreement between the target and run history does not establish that
    # the mandatory governing artifacts are present or that their contents
    # match the recorded hashes. Declaring this limitation does not satisfy
    # that requirement." The docstring above used to declare exactly that
    # limitation, which is why this is written under it rather than beside it.
    #
    # The preserved copy is authoritative where it exists, as it is for the
    # reviewed artifacts. Checking a completed cycle against today's protocol
    # would invalidate it the moment a legitimate amendment lands, which is
    # the retroactive invalidation B02-F07 was about.
    preserved = bool(target.get("governing_artifacts_preserved"))
    bad = []
    for p, want_h in sorted(gph.items()):
        snap = cycle_dir / "artifacts" / p
        if snap.is_file():
            got = sha256_file(snap)
            if got != want_h:
                bad.append(f"{p}\n        preserved copy {got}\n"
                           f"        recorded       {want_h}\n"
                           "        The snapshot has been altered since the "
                           "freeze.")
            continue
        if preserved:
            # Not a fallback case. This cycle's own target says it kept
            # copies, so their absence is a missing artifact rather than an
            # older cycle that never had them.
            bad.append(f"{p}\n        This cycle records that it preserved "
                       f"its governing artifacts, and\n        this one is "
                       f"not there.")
            continue
        live = repo_root / p
        if not live.is_file():
            bad.append(f"{p}\n        Not preserved by this cycle and not on "
                       f"disk, so nothing establishes\n        what governed "
                       f"the review.")
        elif sha256_file(live) != want_h:
            bad.append(f"{p}\n        live file  {sha256_file(live)}\n"
                       f"        recorded   {want_h}\n"
                       "        No preserved copy exists, so this was checked "
                       "against the live file.\n        A cycle frozen by the "
                       "current runner would have one.")
    if bad:
        return ["the governing artifacts this cycle names cannot be shown to "
                "be what it\n      recorded:\n      " + "\n      ".join(bad)]
    return []


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

        # C01-F07. Uniqueness among siblings is not identity. This check asked
        # only whether two targets claimed the same number, and never whether
        # a target's number was its own directory's, or its run_id the run it
        # sits in.
        #
        # Those are read by different components and read differently:
        # `cycle_dirs()` takes the cycle number from the DIRECTORY NAME, while
        # `_governing_problems` selects the pin history with target["cycle"]
        # and `cmd_record` writes the findings record's cycle from the same
        # field. Codex: directory cycle-01 with target cycle 2 passed checks 1
        # to 10, and so did a target claiming run ANOTHER-RUN inside T-001.
        #
        # So one accepted cycle could count as cycle 1 for event projection
        # while being validated against cycle 2's governing pins. Across a pin
        # amendment those are different documents, and nothing said so.
        mismatch = []
        # C02-F05. This read the name as cycle-(\d+) while the controller read
        # it as cycle-(\d{2}), so cycle-1 satisfied check 7 as cycle 1 and was
        # not a cycle at all to anything that counts them. One grammar now,
        # in run_pins, because this module cannot import the one that runs it.
        _n = run_pins.cycle_dir_number(cycle_dir.name)
        if _n is None:
            mismatch.append(f"directory {cycle_dir.name!r} is not cycle-NN, so "
                            f"the cycle it represents cannot be established")
        elif _n != target.get("cycle"):
            mismatch.append(
                f"directory says cycle {_n}, target says "
                f"{target.get('cycle')!r}. Event projection takes the "
                f"directory's number and\n          pin selection takes the "
                f"target's, so this cycle would be two different\n          "
                f"cycles depending on who is reading it")

        _run_json = cycle_dir.parent.parent / "run.json"
        if _run_json.is_file():
            try:
                _rid = json.loads(_run_json.read_text(encoding="utf-8")).get("run_id")
            except json.JSONDecodeError:
                _rid = None
            if _rid is not None and _rid != target.get("run_id"):
                mismatch.append(
                    f"target claims run {target.get('run_id')!r} but sits in "
                    f"run {_rid!r}, whose metadata\n          it is being "
                    f"validated against")

        _rt = cycle_dir.parent.name
        if _rt.endswith("-review") and rtype is not None:
            _want = _rt[:-len("-review")]
            if _want != rtype:
                mismatch.append(f"target declares review_type {rtype!r} inside "
                                f"{_rt}")

        ok7 = not clashes and not mismatch
        detail = []
        if clashes:
            detail.append(f"cycle {target.get('cycle')} also declared by: "
                          + ", ".join(clashes))
        detail += mismatch
        r.add(7, "cycle identity consistent and unique", ok7,
              "\n          ".join(detail) if detail else
              f"cycle {target.get('cycle')} in {cycle_dir.parent.name}, "
              f"matching its directory and run")

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

    # C02-F03, second pass. A declared format has to be one this gate knows.
    # Accepting an unrecognised value would read it as "newer than me, therefore
    # fine", which is the same mistake as reading absence as age with the sign
    # flipped: in both cases the gate decides it need not look.
    _fmt = target.get("evidence_format")
    if _fmt is not None and _fmt not in run_pins.EVIDENCE_FORMATS:
        problems.append(
            f"target declares evidence_format {_fmt!r}, which this gate does "
            f"not know.\n          Known: "
            + ", ".join(run_pins.EVIDENCE_FORMATS) +
            ".\n          A format this checker cannot interpret is not a "
            "format it may validate against.")

    # B01-F07, the half cycle 03 found still open. The protocol's check 9 is
    # "all mandatory hashed artifacts for that review type are present and their
    # recorded hashes match the referenced artifacts". protocol_sha256 and
    # spec_sha256 are recorded hashes of referenced artifacts, and nothing
    # checked them: check 7 confirmed the fields EXIST and stopped. Codex set
    # both to the literal "not-a-hash", recomputed target.sha256, and the gate
    # returned PASS.
    #
    # Checked against governing_pin_hashes, which the same freeze recorded. What
    # that establishes and what it does not, stated plainly:
    #
    #   it catches a digest that is not a digest, and a digest edited to
    #   something other than what this cycle's pin set produces;
    #
    #   it does NOT independently establish that governing_pin_hashes is itself
    #   right, because both fields are written by one function in one moment.
    #   Doing that needs the gate to replay run.json and the amendment history,
    #   which would make MC-2 depend on run-level state it does not currently
    #   read. That is a larger change than this finding, and it is not claimed
    #   here.
    # Historical handling, which Codex asked for by name. governing_pins and
    # governing_pin_hashes arrived with B02-F06 on 11 September. BOOTSTRAP-001's
    # cycles 01 and 02 were frozen before that and carry neither. Failing them
    # now would invalidate two completed cycles, drop the valid-cycle count, and
    # strip authority from the events recorded in them — the retroactive
    # invalidation Alex Zamurko ruled out on 10 September, arriving through a
    # check rather than through an amendment.
    #
    # Both absent is the signature of evidence older than the field. One present
    # without the other is not old evidence, it is an incoherent record, and
    # that still fails.
    #
    # That weakness used to be stated here and left open: deleting both fields
    # from a modern target bought a pass, because nothing in the target said
    # which version of the freezer wrote it. Cycle 02 found that something now
    # does. C01-F03's repair added governing_artifacts_preserved, which only a
    # freeze that also writes the governing set emits, and this branch ran
    # before anything looked at it. Codex: the comment "explicitly acknowledges
    # that deleting both fields buys a pass, but this branch does not even
    # inspect the new preservation flag."
    #
    # So the exemption is now conditional on the record carrying no marker of
    # the freezer that introduced the fields. MODERN_MARKERS says which those
    # are. This does not close the case of a target with no marker at all; that
    # needs an explicit evidence-format version, which C02-F03 also asks for and
    # which is not claimed here. It closes the case the reviewer could build.
    _gph = target.get("governing_pin_hashes")
    _gp = target.get("governing_pins")
    _modern = modern_markers(target)
    if _gph is None and _gp is None:
        if _modern:
            problems.append(
                "target omits both governing_pins and governing_pin_hashes "
                "while declaring " + ", ".join(_modern) + ", which only a "
                "freeze that writes the governing set emits. Absence of those "
                "fields is read as evidence predating them, and this record "
                "does not predate them")
    elif not isinstance(_gph, dict) or not _gph:
        problems.append(
            "target declares governing_pins but records no "
            "governing_pin_hashes, so the protocol and spec digests it states "
            "cannot be checked against anything")
    else:
        problems += _governing_problems(target, _gph, cycle_dir.parent.parent,
                                        cycle_dir, repo_root)

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
    # C02-F09. Same fallback, same repair. A declared approval snapshot that is
    # not there sends this to the live run-level record, which is the dependency
    # on mutable state that preserving the record removed. The refusal is
    # collected rather than raised so check 13 still reports as one check.
    _mod13 = modern_markers(target)
    _p13_pre: list[str] = []
    if _mod13 and not _appr_rel:
        _p13_pre.append(
            "the target declares " + ", ".join(_mod13) + " but records no "
            "approval_record_path.\n          A freeze that preserves names "
            "what it preserved; without it there is nothing to\n          "
            "validate but the live record, which later approvals replace")
    elif _snap_approval is not None and not _snap_approval.is_file() and _mod13:
        _p13_pre.append(
            f"the approval record snapshot is missing: artifacts/{_appr_rel}.\n"
            "          The live record is not a substitute. A completed cycle "
            "is validated against\n          the bytes that were approved, not "
            "against whatever has replaced them")
    approval = (_snap_approval
                if _snap_approval is not None and _snap_approval.is_file()
                else cycle_dir.parent.parent / "plan-approval" / "approval.json")
    if _p13_pre:
        r.add(13, "approved-plan hash matches the frozen approved plan", False,
              "\n          ".join(_p13_pre))
    elif not ap:
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
                # C02-F09, the third of the same fallback.
                if _mod13 and not snap.is_file():
                    problems13.append(
                        f"the approved plan has no preserved copy: "
                        f"artifacts/{plan_ref}.\n          This target declares "
                        + ", ".join(_mod13) + ", so the snapshot was taken and "
                        "is\n          gone. Ordinary work on the plan would "
                        "otherwise decide whether a completed\n          cycle "
                        "is still valid")
                elif not src.is_file():
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
    _strict = modern_markers(target)
    ok14, d14 = _hash_of_declared_file(target, "diff_hash", "diff_path",
                                       repo_root, cycle_dir, _strict)

    # C02-F08. The hash above establishes that the preserved diff is the one the
    # target recorded. It says nothing about whether that diff describes the
    # candidate commit two checks earlier, and nothing did: "the runner can
    # freeze a real candidate commit B while embedding a diff from A or an
    # arbitrary nonempty diff. The validator can accept the commit/tree pair and
    # the unrelated diff independently."
    #
    # So the change set is re-derived here from the two commits the target
    # names, using the shared builder in run_pins, and compared with the digest
    # recorded at freeze. Built from the target's fields rather than from an
    # argument list stored in it: a target is evidence, and evidence must never
    # become a command this process runs.
    #
    # Folded into check 14 rather than added as check 16. The protocol's check
    # list is Alex Zamurko's to extend; what belongs to the check named "diff
    # hash matches the reviewed diff" is the question of which diff was reviewed.
    if ok14:
        _b = target.get("base_commit")
        _recorded = target.get("diff_raw_sha256")
        _p14: list[str] = []
        if _b or _recorded:
            _c = target.get("candidate_commit")
            # Forty hex characters, not sixty four. HEX64 is for digests, and
            # reaching for it here refused every valid base on the first run.
            if not (isinstance(_b, str)
                    and re.fullmatch(r"[0-9a-f]{40}", _b)):
                _p14.append(f"base_commit is {_b!r}, not a full commit SHA")
            if not _recorded or not HEX64.match(str(_recorded)):
                _p14.append("diff_raw_sha256 is absent or malformed, so the "
                            "recorded change set\n          cannot be compared "
                            "with the one these commits produce")
            _paths = target.get("diff_paths", [])
            if not isinstance(_paths, list) or not all(isinstance(p, str)
                                                       for p in _paths):
                _p14.append("diff_paths is not a list of paths, so the "
                            "selection under review is undefined")
            if not _p14:
                _rc, _raw = git_unstripped(
                    repo_root, run_pins.diff_raw_argv(str(_b), str(_c),
                                                      list(_paths)))
                if _rc != 0:
                    _p14.append(
                        f"the change set between {str(_b)[:12]} and "
                        f"{str(_c)[:12]} cannot be derived here, so\n          "
                        "the reviewed diff cannot be shown to describe this "
                        "candidate")
                else:
                    _actual = hashlib.sha256(_raw.encode("utf-8")).hexdigest()
                    if _actual != str(_recorded):
                        _p14.append(
                            f"the reviewed diff is not the change between the "
                            f"commits this target names\n          recorded "
                            f"{_recorded}\n          derived  {_actual}\n"
                            f"          base {_b}\n          candidate {_c}")
                    else:
                        # C02-F08, third pass. Alex Zamurko, 5 October: "generate
                        # the patch directly from the recorded base commit and
                        # candidate commit; compare the preserved patch
                        # byte-for-byte with that generated patch; reject if
                        # paths, modes, hunks, file entries, or repeated changes
                        # differ; do not skip validation when the expected change
                        # set is empty."
                        #
                        # The previous version compared the patch's HEADERS with
                        # the change set. That caught a substituted patch, a
                        # wrong path, a dropped duplicate and an empty change
                        # set, and it could not see a correct header over an
                        # altered hunk body. I wrote that limit into the source
                        # rather than closing it. Regenerating the patch closes
                        # it: one comparison, over the whole artifact.
                        #
                        # The headers are still compared, demoted from a rule to
                        # an explanation. They are what tells a reader whether
                        # the patch is about a different change or about the same
                        # files with different contents, and they never refuse on
                        # their own. A second rule answering for the first is how
                        # C02-F08 came back twice.
                        #
                        # Byte equality means the same git producing the same
                        # formatting. The diff flags are pinned in run_pins for
                        # exactly that reason, and the message below says the
                        # difference may be formatting rather than content, so a
                        # refusal is never read as more than it is.
                        _dp = str(target.get("diff_path") or "")
                        _snap = cycle_dir / "artifacts" / _dp
                        _src = _snap if _snap.is_file() else (repo_root / _dp)
                        _pbytes = _src.read_bytes() if _src.is_file() else b""
                        _rcp, _pgen = git_unstripped(
                            repo_root,
                            run_pins.diff_patch_argv(str(_b), str(_c),
                                                     list(_paths)))
                        # The freeze wrote `patch.encode("utf-8")` of git's
                        # decoded output, so this encodes the same way rather
                        # than comparing raw stdout. Symmetric with how the
                        # bytes under comparison were produced.
                        _gen = _pgen.encode("utf-8")
                        if _rcp != 0:
                            _p14.append(
                                f"the patch between {str(_b)[:12]} and "
                                f"{str(_c)[:12]} cannot be regenerated here,\n"
                                "          so the preserved patch cannot be "
                                "shown to be this change")
                        elif _pbytes != _gen:
                            _want = run_pins.raw_entries(_raw)
                            _got = run_pins.patch_entries(
                                _pbytes.decode("utf-8", errors="replace"))
                            if _got != _want:
                                _missing = [e for e in _want if e not in _got]
                                _extra = [e for e in _got if e not in _want]
                                _p14.append(
                                    "the preserved patch does not describe the "
                                    "change its own target names.\n          the "
                                    f"change has {len(_want)} entry(ies), the "
                                    f"patch has {len(_got)}"
                                    + (f"\n          absent from the patch: "
                                       + ", ".join(e[0] for e in _missing[:4])
                                       if _missing else "")
                                    + (f"\n          not in the change: "
                                       + ", ".join(e[0] for e in _extra[:4])
                                       if _extra else "") +
                                    "\n          Path, mode and object name are "
                                    "all compared, and repeated entries count,"
                                    "\n          because each of those was a way "
                                    "past an earlier version of this check.")
                            else:
                                _p14.append(
                                    "the preserved patch names the right files, "
                                    "modes and objects and\n          is not the "
                                    "patch these commits produce. The difference "
                                    "is inside the\n          hunks, or in how "
                                    "the patch was written, and a reviewer "
                                    "reading it\n          would be reading lines "
                                    "this candidate does not contain."
                                    f"\n          preserved {len(_pbytes)} "
                                    f"bytes, regenerated {len(_gen)} bytes")
        elif modern_markers(target):
            # The C02-F03 distinction, in the place the same mistake would
            # otherwise arrive next. A target carrying a marker of a later
            # freeze cannot also be claiming to predate the derivation it omits.
            _p14.append(
                "target omits base_commit and diff_raw_sha256 while carrying "
                f"{', '.join(modern_markers(target))}.\n          A cycle "
                "frozen recently enough to preserve its governing artifacts "
                "was frozen\n          with a derived diff, so absence here is "
                "not age; it is a diff bound to\n          nothing")
        if _p14:
            ok14, d14 = False, "\n          ".join(_p14)
        elif _b:
            d14 = (f"{d14}; derived from {str(_b)[:12]}..{str(_c)[:12]}"
                   if d14 else
                   f"the change between {str(_b)[:12]} and {str(_c)[:12]}")

    r.add(14, "diff hash matches the reviewed diff", ok14, d14)
    ok15, d15 = _hash_of_declared_file(target, "test_result_hash",
                                       "test_result_path", repo_root, cycle_dir,
                                       _strict)
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
