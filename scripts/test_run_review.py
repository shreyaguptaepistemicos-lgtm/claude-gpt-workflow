#!/usr/bin/env python3
"""Negative controls for the review cycle runner.

Every refusal in run_review.py is demonstrated firing on a fixture built to
trigger exactly that refusal, and the happy path is demonstrated producing a
cycle that passes the MC-2 gate.

A runner whose refusals are never shown to fire is the same defect the v1.0
gate-hardening milestone found thirteen times: a check that cannot come back
false. These are the controls.

The fixture is a throwaway git repository with the two scripts copied in, so
REPO resolves to the fixture and nothing writes into the real runs/ tree.

    python scripts/test_run_review.py

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

# SELF-F16/F20/F25. The Windows console encodes at the locale code page,
# cp1252, and this program holds characters it has no room for. Without
# this the work completes and the print raises UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Issue 8. specs/FIXTURE-SOURCES.md for the rule and why the absent case has
# to be stated.
FIXTURE_SOURCES = {
    "approvals": "canonical: a scope change to the covered manifest is only "
                 "legitimate with an authorisation record, so a fixture that "
                 "approves a bootstrap review needs the manifest and the "
                 "authorisation together. A second set written into this "
                 "suite would be the duplicate source of truth the ruling of "
                 "2 October 2026 removed, wearing a different hat. absent: "
                 "shutil.copytree raises FileNotFoundError and the suite "
                 "stops, so the fixture cannot be built at all without it.",
}

SRC = Path(__file__).resolve().parent
PROTOCOL_BODY = "# protocol\n\nV01 ...\n"
SPEC_BODY = "# spec\n\nrule G1\n"
PROMPT_BODY = "Review the plan against the spec. Report findings.\n"


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")


def write_lf(p: Path, text: str) -> None:
    """Fixtures must be byte-identical on every platform.

    Path.write_text translates \\n to the platform line ending, so a fixture
    written this way hashes differently on Windows and on Linux. That is how
    this suite first failed: it passed on Linux and failed on Windows, on a
    fixture whose bytes were never meant to vary.
    """
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_repo() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="runner-")).resolve()
    (tmp / "scripts").mkdir()
    for name in ("run_review.py", "validate_cycle.py", "bootstrap_gate.py",
                 "ledger.py", "loop_state.py", "findings_format.py",
                 "cycle_projection.py", "authority.py", "run_pins.py"):
        shutil.copy2(SRC / name, tmp / "scripts" / name)
    (tmp / "specs").mkdir()
    # Copied rather than stubbed: it is a covered component now (B01-F10), so
    # the gate hashes it and a stub would diverge from the real one.
    shutil.copy2(SRC.parent / "specs" / "evidence-schema-v1.0.md",
                 tmp / "specs" / "evidence-schema-v1.0.md")
    # C03-F02. The gate reads its covered set from a manifest and requires an
    # authorisation record for it, so a fixture that approves a bootstrap review
    # needs both. Copied from the real repository rather than invented here: a
    # second list written into this suite is the duplicate source of truth the
    # ruling removed, wearing a different hat.
    shutil.copy2(SRC.parent / "specs" / "covered-components.json",
                 tmp / "specs" / "covered-components.json")
    shutil.copytree(SRC.parent / "approvals", tmp / "approvals")
    write_lf(tmp / "specs" / "protocol.md", PROTOCOL_BODY)
    write_lf(tmp / "specs" / "spec.md", SPEC_BODY)
    write_lf(tmp / "specs" / "prompt.md", PROMPT_BODY)
    (tmp / "plan").mkdir()
    write_lf(tmp / "plan" / "01-PLAN.md", "# plan\n\nstep one\n")

    sh("git", "init", "-q", cwd=tmp)
    sh("git", "config", "user.email", "t@t", cwd=tmp)
    sh("git", "config", "user.name", "t", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "fixture", cwd=tmp)
    return tmp


def runner(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    return sh(sys.executable, str(tmp / "scripts" / "run_review.py"), *args, cwd=tmp)


def do_init(tmp: Path, *extra: str) -> subprocess.CompletedProcess:
    # --bootstrap-exempt because these fixtures test the runner's own mechanics
    # and are development evidence, not protocol cycles. Labelling them honestly
    # is the point of the flag. The gate's own effect on init is controlled
    # separately, below, so exempting here does not hide it.
    return runner(tmp, "init", "--run", "T-001", "--bootstrap-exempt",
                  "--protocol", "specs/protocol.md", "--spec", "specs/spec.md",
                  *extra)


def approve_bootstrap(tmp: Path) -> subprocess.CompletedProcess:
    """Record a bootstrap approval bound to a target covering the gate's set.

    B01-F09 makes --target mandatory, so the fixture has to freeze one. Built
    from the gate's own covered set rather than a hand-written list, so adding a
    component to the gate does not silently leave this fixture approving five of
    six things.
    """
    (tmp / "bootstrap-review").mkdir(parents=True, exist_ok=True)
    for n in ("codex-input.md", "codex-output-raw.md", "findings.md",
              "claude-response.md"):
        write_lf(tmp / "bootstrap-review" / n, f"contents of {n}\n")

    import importlib.util
    spec_ = importlib.util.spec_from_file_location(
        "_bg_rr", tmp / "scripts" / "bootstrap_gate.py")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)

    rel_target = "runs/B-BOOT/plan-review/cycle-01/target.json"
    (tmp / rel_target).parent.mkdir(parents=True, exist_ok=True)
    write_lf(tmp / rel_target, json.dumps({
        "review_type": "plan", "run_id": "B-BOOT", "cycle": 1,
        "plan_files": [{"path": p, "sha256": h}
                       for p, h in mod.covered(tmp).items()],
    }, indent=2) + "\n")

    # C02-F07. The preserved input has to name the target the decision is
    # about, so the fixture writes the digest into it. Rewritten here rather
    # than in the loop above because the digest is of the file just frozen.
    #
    # This fixture had the same defect as the gate did: four files of
    # placeholder text, approved without anything tying them to the target.
    # That is worth noticing rather than patching quietly. A fixture that could
    # only be built by exploiting the defect is evidence the defect was real.
    import hashlib
    write_lf(tmp / "bootstrap-review" / "codex-input.md",
             "contents of codex-input.md\ntarget "
             + hashlib.sha256((tmp / rel_target).read_bytes()).hexdigest() + "\n")

    return sh(sys.executable, str(tmp / "scripts" / "bootstrap_gate.py"),
              "record", "--decision", "APPROVE", "--decided-by", "Alex Zamurko",
              "--note", "#gap, 9 Sep 2026, Alex Zamurko: fixture approval",
              "--target", rel_target, cwd=tmp)


def impl_approval(tmp: Path, run_id: str = "T-001") -> str:
    """Write §7.3's plan approval record and return the approved plan's hash.

    B02-F07 made the approval record mandatory for an implementation freeze,
    because the whole implementation evidence set is now preserved and validated
    from the preserved copies — and you cannot preserve an approved plan that
    nothing names. Decision F already said check 13 refuses without the record
    rather than passing vacuously; this makes freeze refuse at the same point
    instead of leaving the cycle to fail the gate afterwards.

    Returns the real hash rather than a dummy: freeze verifies that the supplied
    --approved-plan-hash matches the artifact the approval names, so a fixture
    passing an arbitrary digest is now refused, correctly.

    Module level on purpose. Four controls tonight crashed as NameErrors because
    helpers defined part-way through main() were not yet bound where they were
    used, and a crash reads as a pass.
    """
    plan = tmp / "plan" / "01-PLAN.md"
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    # write_lf does not create parents. Without this the helper raised
    # FileNotFoundError, which killed the suite two thirds of the way through
    # and produced no FAIL line — so the grep read clean and the count refresh
    # recorded 29 controls where there are 95.
    (tmp / "runs" / run_id / "plan-approval").mkdir(parents=True, exist_ok=True)
    write_lf(tmp / "runs" / run_id / "plan-approval" / "approval.json",
             json.dumps({"decision": "APPROVE",
                         "approved_plan_hash": digest,
                         "approved_plan_path": "plan/01-PLAN.md",
                         "decided_by": "Alex Zamurko",
                         "decided_at": "2026-09-12T00:00:00Z"}, indent=2) + "\n")
    return digest


def impl_base(tmp: Path, body: str = "def f():\n    return 1\n") -> str:
    """Commit a change and return the commit before it.

    C02-F08. An implementation freeze now derives the reviewed diff from a base
    and a candidate, so a fixture needs two commits with something between them.
    Until this finding, every implementation fixture here froze a real commit
    beside a four-line diff of a file named x, and passed. That they could only
    be built that way is what the finding says, so they are rebuilt rather than
    adjusted: each one now reviews the change it claims to review.
    """
    write_lf(tmp / "src.py", body)
    sh("git", "add", "-A", cwd=tmp)
    sh("git", "commit", "-qm", "candidate work", cwd=tmp)
    return sh("git", "rev-parse", "HEAD~1", cwd=tmp).stdout.strip()


def do_freeze(tmp: Path, *extra: str) -> subprocess.CompletedProcess:
    return runner(tmp, "freeze", "--run", "T-001", "--type", "plan",
                  "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md", *extra)


def reply_for(tmp: Path, body: str, run: str = "T-001",
              rtype: str = "plan", cycle: int = 1) -> str:
    """A reply quoting the cycle's target hash.

    Capture validity requires it: the review prompt tells the reviewer to quote
    the target SHA-256, and a capture without it is not demonstrably a capture
    of this target. Fixtures have to satisfy the same rule real captures do.
    """
    p = (tmp / "runs" / run / f"{rtype}-review" / f"cycle-{cycle:02d}"
         / "target.sha256")
    if not p.is_file():
        # Some fixtures deliberately have no frozen cycle — recording against an
        # unfrozen directory is one of the refusals under test. Those never
        # reach capture validity, so the body alone is right.
        return body
    return f"TARGET_SHA256 {p.read_text(encoding='utf-8').strip()}\n\n{body}"


def fake_cycles(tmp: Path, n: int, close_last: bool = True) -> None:
    """n cycle directories, each with raw output unless the last is left open.

    These deliberately do NOT pass MC-2 — they carry a target.json with only a
    cycle number and no hashed artifacts. That makes them the right fixture for
    "a directory exists" questions and the wrong one for anything about the
    four-cycle budget, which counts cycles that pass the gate. See B01-F01.
    """
    rd = tmp / "runs" / "T-001" / "plan-review"
    for i in range(1, n + 1):
        c = rd / f"cycle-{i:02d}"
        c.mkdir(parents=True)
        write_lf(c / "target.json", json.dumps({"cycle": i}))
        if i < n or close_last:
            write_lf(c / "codex-output-raw.md", "findings\n")


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def expect_refused(label: str, needle: str, body) -> None:
        tmp = make_repo()
        made.append(tmp)
        r = body(tmp)
        if r.returncode == 0:
            failures.append(f"{label}: expected refusal, exit 0\n{r.stdout}")
            return
        text = r.stderr + r.stdout
        if needle.lower() not in text.lower():
            failures.append(f"{label}: refused, but not for the stated reason\n"
                            f"  wanted {needle!r}\n  got    {text.strip()[:300]}")
            return
        print(f"  [ok] refused: {label}")

    # ---- C01-F08: the commit and the hash must describe the same bytes ----
    # `cmd_init` recorded `git rev-parse HEAD` as protocol_commit and hashed
    # the protocol from the WORKING TREE, with nothing connecting the two.
    # Codex changed specs/protocol.md without committing it, initialised an
    # ordinary run, and got exit 0; the blob at the recorded commit then
    # hashed to something else.
    #
    # "A real run can begin under uncommitted protocol bytes while its record
    # claims a commit containing different bytes."
    print()
    print("the protocol this run pins, at the commit it names (C01-F08)")

    def _modified_protocol(tmp):
        write_lf(tmp / "specs" / "protocol.md",
                 "# Changed protocol, not committed\n")
        return do_init(tmp)

    def _untracked_protocol(tmp):
        write_lf(tmp / "specs" / "elsewhere.md", "# never committed\n")
        return runner(tmp, "init", "--run", "T-001", "--bootstrap-exempt",
                      "--protocol", "specs/elsewhere.md",
                      "--spec", "specs/spec.md")

    expect_refused("a tracked protocol modified since the commit being pinned",
                   "not the protocol at the commit", _modified_protocol)
    expect_refused("a protocol that is not in the commit at all",
                   "not in the commit", _untracked_protocol)

    # The other half of the correction, stated in as many words: "Unrelated
    # working-tree changes need not prevent initialization." A check that
    # refused any dirty tree would satisfy the finding and break the tool, so
    # it is controlled rather than assumed.
    tmp = make_repo()
    made.append(tmp)
    write_lf(tmp / "plan" / "01-PLAN.md", "# plan\n\nedited, uncommitted\n")
    r = do_init(tmp)
    if r.returncode != 0:
        failures.append(f"an unrelated uncommitted change prevented init, "
                        f"which the correction excludes:\n{r.stderr}{r.stdout}")
    else:
        print("  [ok] an unrelated uncommitted change does not prevent init")

    # And the positive one: the pair has to agree, not merely both exist. This
    # reproduces Codex's own check rather than trusting that init refusing the
    # bad cases means it recorded the good one correctly.
    tmp = make_repo()
    made.append(tmp)
    r = do_init(tmp)
    if r.returncode != 0:
        failures.append(f"init failed on a clean tree:\n{r.stderr}{r.stdout}")
    else:
        _run = json.loads((tmp / "runs" / "T-001" / "run.json")
                          .read_text(encoding="utf-8"))
        _blob = subprocess.run(
            ["git", "-C", str(tmp), "show",
             f"{_run['protocol_commit']}:specs/protocol.md"],
            capture_output=True)
        _at_commit = hashlib.sha256(_blob.stdout).hexdigest()
        if _blob.returncode != 0:
            failures.append("the recorded protocol_commit does not contain "
                            "the protocol at all")
        elif _at_commit != _run["protocol"]["sha256"]:
            failures.append(
                f"the run records a commit and a digest that describe "
                f"different bytes\n  at commit {_at_commit}\n  recorded  "
                f"{_run['protocol']['sha256']}")
        else:
            print("  [ok] the recorded commit and digest describe the same "
                  "protocol bytes")

    # ---- happy path first; every negative below is meaningless without it ----
    tmp = make_repo()
    made.append(tmp)
    r = do_init(tmp)
    if r.returncode != 0:
        failures.append(f"init failed:\n{r.stderr}{r.stdout}")
    else:
        run_json = tmp / "runs" / "T-001" / "run.json"
        run = json.loads(run_json.read_text(encoding="utf-8"))
        # Derived from the file's actual bytes, not from re-encoding the constant.
        # The claim under test is the digest-over-digests formula in spec_digest;
        # re-hashing SPEC_BODY would instead be testing file I/O, which is what
        # made this assertion platform-dependent in the first place.
        on_disk = hashlib.sha256((tmp / "specs" / "spec.md").read_bytes()).hexdigest()
        want = hashlib.sha256(f"specs/spec.md:{on_disk}\n".encode()).hexdigest()
        if run["spec_sha256"] != want:
            failures.append("spec_sha256 is not reproducible from its documented definition")
        else:
            print("  [ok] init pins protocol and specs; spec_sha256 reproducible by hand")

        if b"\r" in run_json.read_bytes():
            failures.append("run.json carries CR bytes; its hash will not reproduce "
                            "on another platform")
        else:
            print("  [ok] run.json is LF on this platform")

        r = do_freeze(tmp)
        if r.returncode != 0:
            failures.append(f"freeze failed:\n{r.stderr}{r.stdout}")
        else:
            cyc = tmp / "runs" / "T-001" / "plan-review" / "cycle-01"
            digest = (cyc / "target.sha256").read_text(encoding="utf-8").strip()
            ci = (cyc / "codex-input.md").read_text(encoding="utf-8")
            if digest not in ci:
                failures.append("frozen input does not carry the target hash")
            else:
                print("  [ok] freeze binds codex-input.md to the target hash")

            # The reviewer is asked to judge conformance to the protocol, so the
            # protocol has to be in the file it is judging from. An earlier
            # version named PROTOCOL_SHA256 in the header and stopped, which
            # would have produced a review of a document the reviewer never saw.
            proto_text = (tmp / "specs" / "protocol.md").read_text(encoding="utf-8")
            body = "\n".join(l for l in proto_text.splitlines() if l.strip())
            missing = [l for l in body.splitlines() if l not in ci]
            if missing:
                failures.append(
                    "codex-input.md does not carry the protocol text, only its "
                    "hash. The reviewer cannot read a hash, so it would be asked "
                    "to check conformance to a document it never saw.\n"
                    f"  first absent line: {missing[0][:70]!r}")
            else:
                print("  [ok] codex-input.md carries the protocol text, not just its hash")

            crlf = [n for n in ("target.json", "target.sha256", "codex-input.md")
                    if b"\r" in (cyc / n).read_bytes()]
            if crlf:
                failures.append(f"frozen evidence carries CR bytes: {', '.join(crlf)}\n"
                                "  the same freeze on another platform would produce a "
                                "different TARGET_SHA256")
            else:
                print("  [ok] frozen evidence is LF, so its hashes are platform-neutral")

            write_lf(tmp / "reply.md", reply_for(tmp,
                "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                "Requirement ID: R-B7\nEvidence: ...\n"))
            r = runner(tmp, "record", "--cycle", str(cyc),
                       "--output", "reply.md", "--invocation", "manual")
            if r.returncode != 0:
                failures.append(f"record failed the MC-2 gate on a clean cycle:\n{r.stdout}")
            elif "MC2_CONFORMANCE: PASS" not in r.stdout:
                failures.append(f"record did not run the gate:\n{r.stdout}")
            else:
                print("  [ok] recorded cycle passes the MC-2 gate end to end")

            inv = json.loads((cyc / "invocation.json").read_text(encoding="utf-8"))
            if inv.get("invocation") != "manual":
                failures.append("invocation mode not recorded")
            else:
                print("  [ok] invocation mode recorded, with its limit stated")

    # ---- refusals ----
    expect_refused("init twice on one run id", "already exists",
                   lambda t: (do_init(t), do_init(t))[1])

    expect_refused("freeze without init", "no run.json", do_freeze)

    # ---- B01-F14: the enforcement status is required, not just written ----
    # cmd_init wrote mc1_enforcement, but nothing required it when a run was
    # consumed, so the rule held only for runs that already satisfied it. The
    # actual BOOTSTRAP-001 run lacked the field and was accepted for cycle 02.
    def strip_mc1(t: Path):
        do_init(t)
        rj = t / "runs" / "T-001" / "run.json"
        d = json.loads(rj.read_text(encoding="utf-8"))
        d.pop("mc1_enforcement", None)
        write_lf(rj, json.dumps(d, indent=2) + "\n")
        return do_freeze(t)
    expect_refused("a run with no mc1_enforcement", "records no mc1_enforcement",
                   strip_mc1)

    def bad_mc1(t: Path):
        do_init(t)
        rj = t / "runs" / "T-001" / "run.json"
        d = json.loads(rj.read_text(encoding="utf-8"))
        d["mc1_enforcement"] = "ENFORCED"
        write_lf(rj, json.dumps(d, indent=2) + "\n")
        return do_freeze(t)
    expect_refused("a run claiming an unrecognised enforcement status",
                   "not a recognised status", bad_mc1)

    # A new run writes it, so the positive side is covered too: a refusal-only
    # pair would pass just as well if init had stopped writing the field.
    tmc = make_repo(); made.append(tmc)
    do_init(tmc)
    _rj = json.loads((tmc / "runs/T-001/run.json").read_text(encoding="utf-8"))
    if _rj.get("mc1_enforcement") != "CONVENTION_ONLY":
        failures.append(f"init did not record the enforcement status: "
                        f"{_rj.get('mc1_enforcement')!r}")
    else:
        print("  [ok] a new run records its enforcement status")

    def protocol_drift(t: Path):
        do_init(t)
        write_lf(t / "specs" / "protocol.md", PROTOCOL_BODY + "V22 added later\n")
        return do_freeze(t)
    # The message changed with B02-F05: the pin check now walks the effective
    # governing set rather than run.json's protocol and spec_files separately,
    # so one refusal covers both and names the path. The needle asserts the
    # path, which is what a reader needs, rather than which branch produced it.
    expect_refused("protocol edited after init",
                   "governing artifact changed: specs/protocol.md",
                   protocol_drift)

    def spec_drift(t: Path):
        do_init(t)
        write_lf(t / "specs" / "spec.md", SPEC_BODY + "rule G8\n")
        return do_freeze(t)
    expect_refused("spec edited after init",
                   "governing artifact changed: specs/spec.md", spec_drift)

    def missing_prompt(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "plan",
                      "--prompt", "specs/nope.md", "--file", "plan/01-PLAN.md")
    expect_refused("prompt file missing", "prompt file not found", missing_prompt)

    def empty_prompt(t: Path):
        do_init(t)
        write_lf(t / "specs" / "prompt.md", "")
        return do_freeze(t)
    expect_refused("prompt file empty", "prompt file is empty", empty_prompt)

    def no_plan_file(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "plan",
                      "--prompt", "specs/prompt.md")
    expect_refused("plan review with no artifact", "needs at least one --file", no_plan_file)

    # ---- B01-F01: the budget counts valid cycles, not directories ----
    # This control used to call fake_cycles(4), which builds directories that
    # fail MC-2, and assert the fifth freeze was refused. So it asserted that
    # four INVALID cycles exhaust the budget — the finding itself, written down
    # as expected behaviour and passing for weeks.
    #
    # §2: "Only cycles that pass the MC-2 conformance gate count toward this
    # maximum." §3: an invalid cycle "cannot consume one of the four valid
    # review cycles."
    print()
    print("the four-cycle budget counts valid cycles")

    tbud = make_repo(); made.append(tbud)
    do_init(tbud)
    fake_cycles(tbud, 4)
    r = do_freeze(tbud)
    if r.returncode != 0 and "budget" in (r.stdout + r.stderr):
        failures.append("four cycles that fail MC-2 exhausted the budget; "
                        "invalid cycles cannot consume it")
    else:
        print("  [ok] four cycles that fail MC-2 do not consume the budget")

    # And four that pass it do. Built through the real freeze and record path,
    # because a fixture that hand-writes cycles is how the control above came to
    # assert the wrong thing.
    tfull = make_repo(); made.append(tfull)
    do_init(tfull)

    def close_cycle(root: Path, n: int) -> bool:
        c = root / "runs" / "T-001" / "plan-review" / f"cycle-{n:02d}"
        th = (c / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(root / f"reply{n}.md",
                 f"TARGET_SHA256 {th}\n\nNo findings in any category.\n")
        rr = runner(root, "record", "--cycle",
                    f"runs/T-001/plan-review/cycle-{n:02d}",
                    "--output", f"reply{n}.md", "--invocation", "manual",
                    "--zero-findings")
        return rr.returncode == 0

    def led(root: Path, *a: str) -> subprocess.CompletedProcess:
        return sh(sys.executable, str(root / "scripts" / "ledger.py"), *a,
                  "--review", "runs/T-001/plan-review", cwd=root)

    def build_four(root: Path, stall_last: bool = False) -> int:
        """Four valid cycles, optionally with a fourth that reduces nothing.

        The loop has to stay on CONTINUE to reach four cycles, which means each
        one must show progress. A cycle that only adds an open finding is
        STALLED by §6 at n=2 — correctly — and the freeze after it is refused
        before the budget is ever consulted. So each cycle resolves the previous
        finding and raises its own.

        stall_last skips that for cycle 4, which is legal: cycles 1 to 3 showed
        progress, so freezing the fourth is permitted, and only the boundary
        AFTER it stalls. That is the fixture B01-F02 needed and did not have.
        """
        n = 0
        for i in range(1, 5):
            if do_freeze(root).returncode != 0:
                break
            if not close_cycle(root, i):
                break
            n = i
            if stall_last and i == 4:
                continue
            if i > 1:
                led(root, "resolve", "--cycle", str(i), "--id",
                    f"C{i-1:02d}-F01",
                    "--evidence", "repaired and demonstrated in this cycle")
            led(root, "raise", "--cycle", str(i), "--id", f"C{i:02d}-F01",
                "--class", "UNTESTED RULE", "--source", "CODEX_REVIEW")
            led(root, "respond", "--cycle", str(i), "--id", f"C{i:02d}-F01",
                "--disposition", "ACCEPT", "--note", "will repair next cycle")
        return n

    built = build_four(tfull)

    if built < 4:
        failures.append(f"fixture: only built {built} valid cycle(s), cannot "
                        "test the budget")
    else:
        r = do_freeze(tfull)
        if r.returncode == 0:
            failures.append("a fifth cycle was frozen after four valid ones")
        elif "budget" not in (r.stdout + r.stderr):
            failures.append(f"refused, but not for the budget\n{r.stdout}{r.stderr}")
        else:
            print("  [ok] four cycles that pass MC-2 do consume the budget")

        # ---- B01-F02, on Alex Zamurko's ruling of 15 September ----
        # Codex recorded an authorization naming MAX_4_REACHED at n=4 in a
        # fixture like this one. The controller exited 0 with LOOP_STATUS:
        # CONTINUE and freeze exited 1 on the budget: two components announcing
        # different things about the same boundary, and the runner refusing a
        # permission the controller said it had granted.
        #
        # He ruled that the four-valid-cycle maximum is not clearable, so the
        # offer goes rather than the refusal. Matching, missing and mismatched
        # authorization, end to end, as the correction asked.
        def authorize(root: Path, outcome: str, n: int = 4) -> None:
            write_lf(root / "runs/T-001/plan-review/loop-authorizations.json",
                     json.dumps({"schema": "loop-authorization/1",
                                 "authorizations": [{
                                     "after_valid_cycle": n,
                                     "outcome": outcome,
                                     "authorized_by": "Alex Zamurko",
                                     "reason": "fixture: a recorded human "
                                               "authorization at the budget "
                                               "boundary"}]}, indent=2) + "\n")

        def loop_status(root: Path) -> subprocess.CompletedProcess:
            return sh(sys.executable, str(root / "scripts" / "loop_state.py"),
                      "--review", "runs/T-001/plan-review", "--development",
                      cwd=root)

        def boundary(label: str, needle: str) -> None:
            c = loop_status(tfull)
            cb = c.stdout + c.stderr
            f = do_freeze(tfull)
            fb = f.stdout + f.stderr
            if "LOOP_STATUS: MAX_4_REACHED" not in cb:
                failures.append(f"{label}: the controller did not report "
                                f"MAX_4_REACHED at the budget boundary\n"
                                f"{cb[-400:]}")
            elif needle and needle not in cb:
                failures.append(f"{label}: MAX_4_REACHED was reported but the "
                                f"output never says {needle!r}, so a reader "
                                f"cannot tell the authorization was seen\n"
                                f"{cb[-400:]}")
            elif f.returncode == 0:
                failures.append(f"{label}: a fifth cycle was frozen")
            elif "budget" not in fb:
                failures.append(f"{label}: freeze refused, but not for the "
                                f"budget\n{fb[:300]}")
            else:
                print(f"  [ok] {label}")

        boundary("no authorization: controller and runner agree the loop is "
                 "over", "")
        authorize(tfull, "MAX_4_REACHED")
        boundary("an authorization naming MAX_4_REACHED is read, refused, and "
                 "said out loud", "is NOT honoured")
        authorize(tfull, "STALLED")
        boundary("an authorization for a different exit does not reach the "
                 "budget", "")

        # ---- B01-F02, the half cycle 04 found still open ----
        # Everything above authorises at a boundary that already produces
        # MAX_4_REACHED, so the unclearable list is what refuses and the budget
        # is never the thing under test. Codex: "The named control tests a
        # boundary that already produces MAX_4_REACHED. Its mismatched STALLED
        # authorization does not exercise a boundary that actually produces
        # STALLED."
        #
        # §6 evaluates STALLED before the budget. So a fourth boundary that
        # genuinely stalls reports STALLED, never meets the unclearable list,
        # and a matching authorisation used to clear it straight into CONTINUE
        # with the ceiling never consulted. The controller told the operator to
        # open a fifth cycle while the runner refused to.
        tstall = make_repo(); made.append(tstall)
        do_init(tstall)
        if build_four(tstall, stall_last=True) < 4:
            failures.append("fixture: could not build four valid cycles with a "
                            "stalled fourth, so the ceiling is untested against "
                            "a clearable exit")
        else:
            _pre = loop_status(tstall)
            if "LOOP_STATUS: STALLED" not in (_pre.stdout + _pre.stderr):
                failures.append(
                    "fixture: boundary 4 does not actually STALL, so "
                    "authorising STALLED there\n      tests nothing\n"
                    f"      {(_pre.stdout + _pre.stderr).strip()[-200:]}")
            else:
                print("  [ok] a fourth boundary that reduces nothing reports "
                      "STALLED, not MAX_4_REACHED")
                authorize(tstall, "STALLED", 4)
                c = loop_status(tstall)
                cb = c.stdout + c.stderr
                f = do_freeze(tstall)
                fb = f.stdout + f.stderr
                if "LOOP_STATUS: CONTINUE" in cb:
                    failures.append(
                        "a matching authorization cleared STALLED at the "
                        "budget boundary and the\n      controller granted "
                        "another cycle. The ceiling was never consulted, and "
                        "the\n      runner refuses what the controller just "
                        "permitted")
                elif "LOOP_STATUS: MAX_4_REACHED" not in cb:
                    failures.append(
                        f"the cleared stall did not resolve to MAX_4_REACHED\n"
                        f"      {cb.strip()[-240:]}")
                elif f.returncode == 0:
                    failures.append("a fifth cycle was frozen after a cleared "
                                    "stall at the budget boundary")
                elif "budget" not in fb:
                    failures.append(f"freeze refused, but not for the budget\n"
                                    f"      {fb.strip()[:240]}")
                else:
                    print("  [ok] clearing a real STALLED at the fourth "
                          "boundary does not buy a fifth cycle")

    def prev_open(t: Path):
        do_init(t)
        fake_cycles(t, 1, close_last=False)
        return do_freeze(t)
    expect_refused("previous cycle has no recorded output", "no recorded output", prev_open)

    def impl_missing(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD")
    expect_refused("implementation review missing approved plan hash", "requires --approved-plan-hash", impl_missing)

    def impl_bad_hash(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD",
                      "--approved-plan-hash", "NOT-A-HASH")
    expect_refused("approved plan hash not a digest", "64-char hex", impl_bad_hash)

    # ---- B01-F17: the other three implementation refusals ----
    # cmd_freeze raises five refusals for implementation review. Two were
    # exercised above and three were not, while this suite's closing line said
    # every refusal is reachable. Each is a distinct guard on a distinct §10.1
    # field, so covering two of five and claiming five is the same shape of
    # over-claim as the seam-1 probes.
    GOOD_HASH = "a" * 64

    def impl_no_commit(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md",
                      "--approved-plan-hash", GOOD_HASH)
    expect_refused("implementation review with no candidate commit",
                   "requires --candidate-commit", impl_no_commit)

    def impl_unresolvable_commit(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md",
                      "--candidate-commit", "0" * 40,
                      "--approved-plan-hash", GOOD_HASH)
    expect_refused("candidate commit that does not resolve",
                   "does not resolve", impl_unresolvable_commit)

    # ---- B01-F07: the recorded hashes describe THIS cycle's pin set ----
    # Codex: "protocol_sha256 and spec_sha256 are checked for presence only; no
    # check ties them to the pinned artifacts or to run.json." They were copied
    # verbatim from run.json, so they described the set as it stood at init.
    #
    # BOOTSTRAP-001 shows the consequence: its cycle 02 records the digest of a
    # spec set that the amendment effective at cycle 2 had already released.
    print()
    print("recorded hashes follow the cycle's own pin set (B01-F07)")

    t7 = make_repo(); made.append(t7)
    do_init(t7); do_freeze(t7)
    run7 = json.loads((t7 / "runs/T-001/run.json").read_text(encoding="utf-8"))
    tgt7a = json.loads((t7 / "runs/T-001/plan-review/cycle-01/target.json")
                       .read_text(encoding="utf-8"))
    if tgt7a["protocol_sha256"] != run7["protocol_sha256"]:
        failures.append("cycle 01 records a protocol hash that is not the "
                        "pinned one")
    elif tgt7a["spec_sha256"] != run7["spec_sha256"]:
        failures.append("with no amendment in force the recorded spec digest "
                        "should equal the run's")
    else:
        print("  [ok] with no amendment, the recorded hashes match the run")

    # Now release the spec from the governing set, effective cycle 2. The next
    # cycle must record a different spec digest, because a different set governs
    # it. Copying run.json forward would leave both cycles claiming the same one.
    # Cycle 01 closed through the real record path. Writing codex-output-raw.md
    # by hand leaves no findings.json, the controller then refuses to say
    # whether another cycle is permitted, and B01-F02's check blocks the freeze
    # — so this control would report a pin failure that never happened. One open
    # finding, raised in the ledger, keeps the loop on CONTINUE.
    _th7 = (t7 / "runs/T-001/plan-review/cycle-01/target.sha256") \
        .read_text(encoding="utf-8").strip()
    write_lf(t7 / "reply7.md",
             f"TARGET_SHA256 {_th7}\n\nFinding ID: C01-F01\n"
             "Class: UNTESTED RULE\nEvidence: x\n")
    _r7 = runner(t7, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
                 "--output", "reply7.md", "--invocation", "manual")
    if _r7.returncode != 0:
        failures.append(f"fixture: could not record cycle 01\n{_r7.stderr}{_r7.stdout}")
    _l7 = sh(sys.executable, str(t7 / "scripts" / "ledger.py"), "raise",
             "--review", "runs/T-001/plan-review", "--cycle", "1",
             "--id", "C01-F01", "--class", "UNTESTED RULE",
             "--source", "CODEX_REVIEW", cwd=t7)
    if _l7.returncode != 0:
        failures.append(f"fixture: could not raise the finding\n{_l7.stderr}{_l7.stdout}")

    # Written here rather than calling amend(), which is defined further down in
    # this function and was therefore not yet bound: the block crashed on a
    # NameError after the first assertion, printing one [ok] and no failure.
    # A control that never runs is indistinguishable from one that passed.
    write_lf(t7 / "runs" / "T-001" / "pin-amendments.json", json.dumps({
        "schema": "run-pin-amendments/1",
        "amendments": [{
            "effective_cycle": 2,
            "reason": "the pinned spec is also a review target, which the "
                      "separation specification forbids",
            "affected_artifacts": ["specs/spec.md"],
            "prior_pin_set": ["specs/protocol.md", "specs/spec.md"],
            "new_pin_set": ["specs/protocol.md"],
            "authorized_by": "Alex Zamurko",
            "at": "2026-09-10T00:00:00Z",
        }]}, indent=2) + "\n")
    r = do_freeze(t7)
    if r.returncode != 0:
        failures.append(f"freeze after the amendment failed\n{r.stdout}{r.stderr}")
    else:
        tgt7b = json.loads((t7 / "runs/T-001/plan-review/cycle-02/target.json")
                           .read_text(encoding="utf-8"))
        if tgt7b["spec_sha256"] == tgt7a["spec_sha256"]:
            failures.append(
                "cycle 02 records the same spec digest as cycle 01 despite an "
                "amendment releasing the spec; the field is copied from "
                "run.json rather than derived from what governs the cycle")
        elif "specs/spec.md" in tgt7b.get("governing_pins", []):
            failures.append("the released spec is still in the governing set")
        else:
            print("  [ok] releasing a spec changes what the next cycle records")

        # And cycle 01 is untouched: its record still describes the set it was
        # actually conducted under. "Never validate historical cycles against
        # the latest pin set" applies to what they recorded, too.
        again = json.loads((t7 / "runs/T-001/plan-review/cycle-01/target.json")
                           .read_text(encoding="utf-8"))
        if again["spec_sha256"] != tgt7a["spec_sha256"]:
            failures.append("the amendment changed what cycle 01 recorded")
        else:
            print("  [ok] the earlier cycle's record is unchanged by the "
                  "amendment")

        # The half cycle 03 found still open. Everything above checks what the
        # cycle RECORDS. The reviewer never reads target.json; it reads the
        # header of codex-input.md, and that was still quoting run.json. So the
        # repair was demonstrably present in the record and absent from the only
        # copy anyone acts on.
        #
        # BOOTSTRAP-001's own cycle 03 shows it with no fixture at all:
        # target.json records spec_sha256 e3b0c442… and the header says
        # ad7f1099…. Compared here rather than asserted against a literal,
        # because the point is that the two agree, not that either equals some
        # value this control also had to know.
        _hdr = (t7 / "runs/T-001/plan-review/cycle-02/codex-input.md") \
            .read_text(encoding="utf-8")
        # Parsed rather than string-matched: the header pads the key out for
        # alignment, so looking for "KEY value" with one space between them
        # fails on a header that is perfectly correct. The first version of this
        # control did that and reported the repair broken when it was not.
        _got = {}
        for _line in _hdr.splitlines():
            _p = _line.split()
            if len(_p) == 2 and _p[0].endswith("_SHA256"):
                _got[_p[0]] = _p[1]
        _want = [("PROTOCOL_SHA256", tgt7b["protocol_sha256"]),
                 ("SPEC_SHA256", tgt7b["spec_sha256"])]
        _wrong = [f"{k}: target says {v}, header says {_got.get(k, '(absent)')}"
                  for k, v in _want if _got.get(k) != v]
        if _wrong:
            failures.append(
                "the composed input's header disagrees with the target it is "
                "bound to:\n      " + "\n      ".join(_wrong) +
                "\n      The reviewer reads the header, so the digests it was "
                "given describe a\n      pin set other than the one governing "
                "this cycle. That is B01-F07.")
        else:
            print("  [ok] the input header quotes the cycle's own digests, not "
                  "the run's")

    # ---- B01-F04: the reviewer is given what it is asked to judge against ----
    # Codex: "compose_input carries the protocol but not the pinned spec, and
    # for implementation review omits the target identifiers entirely." A hash
    # in a header is not a document a reviewer can read.
    print()
    print("the review input carries the spec and the target identity")

    t4 = make_repo(); made.append(t4)
    do_init(t4); do_freeze(t4)
    ci4 = (t4 / "runs/T-001/plan-review/cycle-01/codex-input.md") \
        .read_text(encoding="utf-8")
    spec_body = (t4 / "specs" / "spec.md").read_text(encoding="utf-8").strip()
    if spec_body.splitlines()[0] not in ci4:
        failures.append("the composed input does not contain the pinned spec "
                        "text, only its hash")
    elif "The pinned specification" not in ci4:
        failures.append("the spec is present but not identified as the pinned "
                        "specification")
    else:
        print("  [ok] the pinned spec is embedded, not merely hashed")

    # Editing a pinned spec must not silently reach the reviewer: the text
    # embedded has to be the text the header names.
    t4b = make_repo(); made.append(t4b)
    do_init(t4b)
    sp = t4b / "specs" / "spec.md"
    sp.write_text(sp.read_text(encoding="utf-8") + "\nrule G9\n", encoding="utf-8")
    r = do_freeze(t4b)
    # Fixture-validity audit, 17 September. This asserted only that freeze
    # refused. Freeze refuses for a dozen reasons, and the fixture edits a spec
    # on disk, so "it refused" did not establish that the drift is what stopped
    # it. Same correction applied to the four other bare refusal assertions in
    # this suite; the remaining twenty-nine already named their reason.
    #
    # Naming the reason changed what this control is about. It was called "a
    # drifted spec is not embedded under its old hash" and read as a control on
    # the snapshot comparison in cmd_freeze. It is not: the pin check refuses
    # first, and the snapshot comparison is never reached.
    #
    # That comparison appears to be unreachable by any fixture. It hashes the
    # copy it has just written and compares it against a hash computed from the
    # same file a few lines earlier in the same call, so the two can differ only
    # if the file changes on disk between those two reads. It is a defensive
    # branch, and this suite was reporting a control over it that does not
    # exist.
    #
    # Left as it stands rather than repaired. run_review.py is in the frozen
    # BOOTSTRAP-002 cycle-01 target and editing it now would put an unreviewed
    # change into the file under review. It belongs in the reviewer's findings.
    if r.returncode == 0:
        failures.append("a cycle was frozen embedding a spec that no longer "
                        "matches the hash in its own header")
    elif "run pins no longer hold" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the drifted governing pin\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: a drifted governing spec stops the freeze at the "
              "pin check")

    # Implementation review: the §10.1 fields have to reach the reviewer.
    t4c = make_repo(); made.append(t4c)
    do_init(t4c)
    base4 = impl_base(t4c)
    write_lf(t4c / "results.txt", "3 passed\n")
    head4 = sh("git", "rev-parse", "HEAD", cwd=t4c).stdout.strip()
    plan4 = impl_approval(t4c)
    r = runner(t4c, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--candidate-commit", head4,
               "--approved-plan-hash", plan4, "--base", base4,
               "--test-results", "results.txt")
    if r.returncode != 0:
        failures.append(f"implementation freeze failed\n{r.stdout}{r.stderr}")
    else:
        ci = (t4c / "runs/T-001/implementation-review/cycle-01/codex-input.md") \
            .read_text(encoding="utf-8")
        # The field names are the target's own, not invented here. Writing
        # test_result_sha256 when the target records test_result_hash is how a
        # control asserts something the system never claimed.
        missing = [f for f in (head4, plan4, "candidate_tree_hash",
                               "test_result_hash", "diff_hash") if f not in ci]
        if missing:
            failures.append(
                "the implementation review input omits target identifiers the "
                f"reviewer needs: {missing}")
        else:
            print("  [ok] an implementation review input carries the §10.1 "
                  "target identity")

    # ---- C02-F08: the reviewed diff is the candidate's own change ----
    # "The runner can freeze a real candidate commit B while embedding a diff
    # from A or an arbitrary nonempty diff. The validator can accept the
    # commit/tree pair and the unrelated diff independently. The reviewer is
    # told that the artifacts are the implementation's contents, but the
    # supplied code establishes no such relationship."
    print()
    print("C02-F08  the reviewed diff derived from the candidate")

    _t4 = t4c / "runs/T-001/implementation-review/cycle-01"
    if (_t4 / "target.json").is_file():
        _tg = json.loads((_t4 / "target.json").read_text(encoding="utf-8"))
        _patch = (_t4 / "artifacts" / "candidate.diff")
        if _tg.get("base_commit") != base4:
            failures.append(f"the target does not record the base the diff was "
                            f"measured from: {_tg.get('base_commit')!r}")
        elif not _tg.get("diff_raw_sha256"):
            failures.append("the target records no change-set digest, so the "
                            "diff is bound to the commits by nothing")
        elif not _patch.is_file():
            failures.append("the derived diff was not preserved in the cycle")
        elif "src.py" not in _patch.read_text(encoding="utf-8"):
            failures.append(
                "the preserved diff does not describe the candidate's own "
                "change; it is some other file's")
        elif sha256_file(_patch) != _tg.get("diff_hash"):
            failures.append("the preserved diff does not match its record")
        else:
            print("  [ok] the diff is derived from the candidate, preserved, "
                  "and bound by a change-set digest")

    # Codex asked for exactly this fixture: "two valid candidate commits and
    # swap only the diff/content between them; it must fail rather than passing
    # because each independent hash is well formed."
    #
    # Done from the other side, which is the same swap and easier to build
    # honestly: the cycle keeps its diff and is repointed at a second, equally
    # valid candidate. Checks 11 and 12 pass, because that commit resolves and
    # its tree agrees. Check 14's hash passes, because the preserved diff is
    # untouched and still matches its record. Every independent hash is well
    # formed, which was the whole complaint, and the cycle must still fail.
    _th4 = (_t4 / "target.sha256").read_text(encoding="utf-8").strip()
    write_lf(t4c / "reply4.md",
             f"TARGET_SHA256 {_th4}\n\nNo findings in any category.\n")
    _rec = runner(t4c, "record", "--cycle", str(_t4), "--output", "reply4.md",
                  "--invocation", "manual", "--zero-findings")
    if _rec.returncode != 0:
        failures.append(f"the C02-F08 fixture could not be recorded:\n"
                        f"{_rec.stdout}{_rec.stderr}")
    else:
        def _mc2(where: Path) -> subprocess.CompletedProcess:
            return sh(sys.executable, str(t4c / "scripts" / "validate_cycle.py"),
                      str(where), cwd=t4c)

        _clean = _mc2(_t4)
        if _clean.returncode != 0:
            failures.append(
                f"the fixture does not pass MC-2 before the swap, so a failure "
                f"after it would say nothing:\n{_clean.stdout}{_clean.stderr}")
        else:
            print("  [ok] a derived-diff implementation cycle passes MC-2")

            write_lf(t4c / "src.py", "def f():\n    return 2\n")
            sh("git", "add", "-A", cwd=t4c)
            sh("git", "commit", "-qm", "a second, equally valid candidate",
               cwd=t4c)
            _other = sh("git", "rev-parse", "HEAD", cwd=t4c).stdout.strip()
            _otree = sh("git", "rev-parse", f"{_other}^{{tree}}",
                        cwd=t4c).stdout.strip()
            _tg = json.loads((_t4 / "target.json").read_text(encoding="utf-8"))
            _tg["candidate_commit"] = _other
            _tg["candidate_tree_hash"] = _otree
            write_lf(_t4 / "target.json", json.dumps(_tg, indent=2))
            write_lf(_t4 / "target.sha256",
                     sha256_file(_t4 / "target.json") + "\n")
            # Check 10 wants codex-input.md to quote the target's digest
            # verbatim, and the swap changes that digest. Left stale, the cycle
            # is refused by check 10 and this control passes on a refusal that
            # has nothing to do with the diff, which is exactly the defect it
            # exists to catch. Found by the probe: with the derivation check
            # removed the cycle was still refused, and the control still looked
            # green until it asked which check had spoken.
            #
            # Every other check is deliberately left satisfiable. The complaint
            # is that each hash can be well formed on its own, so the fixture
            # has to make all of them so.
            _new_th = sha256_file(_t4 / "target.json")
            _ci = _t4 / "codex-input.md"
            write_lf(_ci, _ci.read_text(encoding="utf-8").replace(_th4, _new_th))

            _sw = _mc2(_t4)
            _out = _sw.stdout + _sw.stderr
            if _sw.returncode == 0:
                failures.append(
                    "a cycle pinning one candidate and carrying another's diff "
                    "passed MC-2. Every hash in it is well formed, which is "
                    "why hashing them separately was never a binding.")
            elif "not the change between the commits" not in _out:
                failures.append(f"refused, but not for the unrelated diff\n"
                                f"{_out}")
            else:
                print("  [ok] refused: the diff is not the change between the "
                      "commits this target names")

    # ---- C02-F08, raised again by cycle 03 ----
    # The swap above moves the candidate. Codex asked for the other direction,
    # which the first repair did not cover: "retain the candidate, base, and
    # correct diff_raw_sha256; substitute another patch and update diff_hash,
    # the target digest, and the corresponding input content. The patch hash and
    # raw-metadata comparison both pass independently."
    #
    # Every hash in the resulting cycle is correct about something. The patch
    # hashes to its record, the change set hashes to its record, and the two
    # records describe different changes.
    t8 = make_repo(); made.append(t8)
    do_init(t8)
    base8 = impl_base(t8, "def h():\n    return 11\n")
    write_lf(t8 / "results.txt", "11 passed\n")
    head8 = sh("git", "rev-parse", "HEAD", cwd=t8).stdout.strip()
    plan8 = impl_approval(t8)
    r = runner(t8, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--candidate-commit", head8,
               "--approved-plan-hash", plan8, "--base", base8,
               "--test-results", "results.txt")
    c8 = t8 / "runs" / "T-001" / "implementation-review" / "cycle-01"
    if r.returncode != 0:
        failures.append(f"the C02-F08 patch-substitution fixture could not be "
                        f"frozen:\n{r.stdout}{r.stderr}")
    else:
        _th8 = (c8 / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(t8 / "reply8.md",
                 f"TARGET_SHA256 {_th8}\n\nNo findings in any category.\n")
        _r8 = runner(t8, "record", "--cycle", str(c8), "--output", "reply8.md",
                     "--invocation", "manual", "--zero-findings")
        if _r8.returncode != 0:
            failures.append(f"the C02-F08 patch-substitution fixture could not "
                            f"be recorded:\n{_r8.stdout}{_r8.stderr}")
        else:
            # A real patch of a different change, rather than edited text. The
            # point is that a reviewer handed this would read a coherent diff
            # and have no way to tell it is not the one the target names.
            write_lf(t8 / "other.py", "def other():\n    return 0\n")
            sh("git", "add", "-A", cwd=t8)
            sh("git", "commit", "-qm", "an unrelated change", cwd=t8)
            _other = sh("git", "-c", "core.quotepath=false", "diff",
                        "--no-color", "--full-index", "-M0", "HEAD~1", "HEAD",
                        cwd=t8).stdout

            _snap = c8 / "artifacts" / "candidate.diff"
            _orig8 = _snap.read_text(encoding="utf-8")
            write_lf(_snap, _other)
            _tg8 = json.loads((c8 / "target.json").read_text(encoding="utf-8"))
            _tg8["diff_hash"] = sha256_file(_snap)
            write_lf(c8 / "target.json", json.dumps(_tg8, indent=2))
            _new8 = sha256_file(c8 / "target.json")
            write_lf(c8 / "target.sha256", _new8 + "\n")
            _ci8 = c8 / "codex-input.md"
            write_lf(_ci8, _ci8.read_text(encoding="utf-8").replace(_th8, _new8))

            _rr = sh(sys.executable,
                     str(t8 / "scripts" / "validate_cycle.py"), str(c8), cwd=t8)
            _out8 = _rr.stdout + _rr.stderr
            if _rr.returncode == 0:
                failures.append(
                    "a cycle carrying a patch of an entirely different change "
                    "passed MC-2. Its patch hashes to its record and its change "
                    "set hashes to its record; the two records are about "
                    "different changes, which hashing each one separately "
                    "cannot see.")
            elif "does not describe the change its own target names" not in _out8:
                failures.append(f"refused, but not for the substituted patch\n"
                                f"{_out8[-400:]}")
            else:
                print("  [ok] refused: the preserved patch describes a "
                      "different change from the one the target names")

            # And the case the recorded change-set digest catches on its own.
            # The probe found that the blob comparison above subsumes it for a
            # moved candidate, so without this control the digest rule could be
            # removed and nothing would notice: the stronger check was answering
            # for both. Here the patch and the commits agree with each other and
            # only the recorded digest is wrong, which the blob comparison
            # cannot see because it never consults it.
            write_lf(_snap, _orig8)
            _tg8 = json.loads((c8 / "target.json").read_text(encoding="utf-8"))
            # The real one, kept before it is spoiled below. The cycle 04
            # controls further down need the record to be correct about
            # everything except the one thing each of them breaks.
            _rawsha8 = str(_tg8.get("diff_raw_sha256") or "")
            _tg8["diff_hash"] = sha256_file(_snap)
            _tg8["diff_raw_sha256"] = "d" * 64
            write_lf(c8 / "target.json", json.dumps(_tg8, indent=2))
            _n8 = sha256_file(c8 / "target.json")
            write_lf(c8 / "target.sha256", _n8 + "\n")
            _ci8 = c8 / "codex-input.md"
            write_lf(_ci8, _ci8.read_text(encoding="utf-8").replace(_new8, _n8))

            _rr = sh(sys.executable,
                     str(t8 / "scripts" / "validate_cycle.py"), str(c8), cwd=t8)
            _out8 = _rr.stdout + _rr.stderr
            if _rr.returncode == 0:
                failures.append(
                    "a target recording a change set these commits do not "
                    "produce passed MC-2. The digest is the only thing tying "
                    "the record to the repository, and nothing checked it.")
            elif "not the change between the commits" not in _out8:
                failures.append(f"refused, but not for the recorded change set\n"
                                f"{_out8[-400:]}")
            else:
                print("  [ok] refused: the recorded change set is not what "
                      "these commits produce")

            # ---- C02-F08, raised a third time by cycle 04 ----
            # The comparison cycle 03 left behind matched unordered SETS of
            # (before, after) blob pairs. Cycle 04 named three ways past it:
            # "correct index headers with altered hunks or paths", "set
            # comparison hides omission of an entry when another entry shares
            # the same blob pair", and "an empty expected set bypasses
            # comparison entirely through `if _want`".
            #
            # So the comparison is now over full entries — path, both modes,
            # both object names — as a list rather than a set, and it runs
            # whether or not the change set is empty. One control for each hole.
            # Each edits the patch and reseals every record around it, so what
            # refuses is the comparison and not some hash noticing the tamper.
            _cur8 = _n8

            def _reseal8(patch_text: str, **fields) -> None:
                nonlocal _cur8
                write_lf(_snap, patch_text)
                _t = json.loads((c8 / "target.json").read_text(encoding="utf-8"))
                _t["diff_hash"] = sha256_file(_snap)
                _t["diff_raw_sha256"] = _rawsha8
                # Restored too, so each control below starts from the same
                # correct record and breaks exactly one thing. Without this the
                # base left behind by one control silently became the premise of
                # the next, and the next control stopped being about what it
                # said it was about.
                _t["base_commit"] = base8
                _t.update(fields)
                write_lf(c8 / "target.json", json.dumps(_t, indent=2))
                _nx = sha256_file(c8 / "target.json")
                write_lf(c8 / "target.sha256", _nx + "\n")
                _ci = c8 / "codex-input.md"
                write_lf(_ci,
                         _ci.read_text(encoding="utf-8").replace(_cur8, _nx))
                _cur8 = _nx

            def _refused8(label: str, needle: str, passed: str) -> None:
                _p = sh(sys.executable,
                        str(t8 / "scripts" / "validate_cycle.py"), str(c8),
                        cwd=t8)
                _o = _p.stdout + _p.stderr
                if _p.returncode == 0:
                    failures.append(passed)
                elif needle not in _o:
                    failures.append(f"refused, but not for {label}\n"
                                    f"{_o[-400:]}")
                else:
                    print(f"  [ok] refused: {label}")

            # The baseline. Without it each refusal below could be a refusal
            # left over from the digest control above, and all three would look
            # green while establishing nothing. This is the mistake cycle 03
            # found in B01-F11's control, so it is checked rather than assumed.
            _reseal8(_orig8)
            _p8 = sh(sys.executable, str(t8 / "scripts" / "validate_cycle.py"),
                     str(c8), cwd=t8)
            if _p8.returncode != 0:
                failures.append(
                    f"the cycle does not pass MC-2 with its own patch and its "
                    f"own digests restored, so the three controls below prove "
                    f"nothing:\n{(_p8.stdout + _p8.stderr)[-400:]}")
            else:
                print("  [ok] the restored cycle passes, so the refusals that "
                      "follow are attributable")

                # 1. Correct index lines, a different path. Under a set of blob
                # pairs this is invisible: the objects are right and the path
                # was never part of what was compared.
                _wrong = (_orig8
                          .replace("a/src.py b/src.py",
                                   "a/elsewhere.py b/elsewhere.py")
                          .replace("--- a/src.py", "--- a/elsewhere.py")
                          .replace("+++ b/src.py", "+++ b/elsewhere.py"))
                if _wrong == _orig8:
                    failures.append(
                        "the fixture's patch does not name src.py, so the "
                        "path-substitution control changed nothing and would "
                        "pass for the wrong reason")
                else:
                    _reseal8(_wrong)
                    _refused8(
                        "a patch whose index lines are right and whose path is "
                        "not",
                        "does not describe the change its own target names",
                        "a patch naming a file the change never touched passed "
                        "MC-2. Its blob names are correct, which is all the "
                        "previous comparison looked at.")

                # 2. An empty change set with a nonempty patch. Freeze refuses
                # to produce one, so it is reached the only honest way left:
                # a base equal to the candidate, with the digest of the empty
                # change set recorded truthfully beside it. Every record here
                # is correct; the patch is simply about something.
                _reseal8(_orig8, base_commit=head8,
                         diff_raw_sha256=hashlib.sha256(b"").hexdigest())
                _refused8(
                    "a nonempty patch for a change set with nothing in it",
                    "does not describe the change its own target names",
                    "a cycle whose two commits are the same commit, carrying a "
                    "patch of real work, passed MC-2. An empty expected set "
                    "skipped the comparison, so a cycle with nothing to review "
                    "accepted any patch at all.")

                # 3. Correct headers, altered hunk body. Alex Zamurko asked for
                # this one on 5 October, and he was right that the header
                # comparison could never see it: paths, modes and object names
                # all stay correct while the reviewer reads lines the candidate
                # does not contain. It is the case the gate now catches by
                # regenerating the patch and comparing bytes.
                _lines8 = _orig8.splitlines(keepends=True)
                _added8 = [i for i, l in enumerate(_lines8)
                           if l.startswith("+") and not l.startswith("+++")]
                if not _added8:
                    failures.append(
                        "the fixture's patch has no added line to alter, so the "
                        "hunk-body control would change nothing and pass for the "
                        "wrong reason")
                else:
                    _lines8[_added8[0]] = "+    return 99  # not in the change\n"
                    _reseal8("".join(_lines8))
                    _refused8(
                        "a patch whose headers are right and whose hunk body is "
                        "not",
                        "is not the patch these commits produce",
                        "a patch showing the reviewer a line the candidate does "
                        "not contain passed MC-2. Every path, mode and object "
                        "name in it is correct, which is all the header "
                        "comparison ever looked at.")

    # ---- C02-F08, the third hole: one of two entries sharing a blob pair ----
    # A set loses duplicates, so a change in which two files move between the
    # same pair of objects collapses to one entry, and a patch that omits either
    # of them compares equal. That needs a fixture the others cannot provide:
    # two files whose change is literally the same change.
    t10 = make_repo(); made.append(t10)
    do_init(t10)
    write_lf(t10 / "one.py", "x = 0\n")
    write_lf(t10 / "two.py", "x = 0\n")
    write_lf(t10 / "results.txt", "2 passed\n")
    sh("git", "add", "-A", cwd=t10)
    sh("git", "commit", "-qm", "two files with identical contents", cwd=t10)
    base10 = sh("git", "rev-parse", "HEAD", cwd=t10).stdout.strip()
    write_lf(t10 / "one.py", "x = 1\n")
    write_lf(t10 / "two.py", "x = 1\n")
    sh("git", "add", "-A", cwd=t10)
    sh("git", "commit", "-qm", "the same edit to both", cwd=t10)
    head10 = sh("git", "rev-parse", "HEAD", cwd=t10).stdout.strip()
    plan10 = impl_approval(t10)
    r = runner(t10, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--candidate-commit", head10,
               "--approved-plan-hash", plan10, "--base", base10,
               "--test-results", "results.txt")
    c10 = t10 / "runs" / "T-001" / "implementation-review" / "cycle-01"
    if r.returncode != 0:
        failures.append(f"the C02-F08 duplicate-entry fixture could not be "
                        f"frozen:\n{r.stdout}{r.stderr}")
    else:
        _th10 = (c10 / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(t10 / "reply10.md",
                 f"TARGET_SHA256 {_th10}\n\nNo findings in any category.\n")
        _r10 = runner(t10, "record", "--cycle", str(c10), "--output",
                      "reply10.md", "--invocation", "manual", "--zero-findings")
        if _r10.returncode != 0:
            failures.append(f"the C02-F08 duplicate-entry fixture could not be "
                            f"recorded:\n{_r10.stdout}{_r10.stderr}")
        else:
            _snap10 = c10 / "artifacts" / "candidate.diff"
            _orig10 = _snap10.read_text(encoding="utf-8")
            _ix10 = [l for l in _orig10.splitlines() if l.startswith("index ")]
            _secs10 = ["diff --git " + s
                       for s in _orig10.split("diff --git ")[1:]]
            _keep10 = [s for s in _secs10
                       if not s.splitlines()[0].endswith("b/two.py")]
            if len(_ix10) != 2 or len(set(_ix10)) != 1:
                # The premise, stated as a check. If the two files do not share
                # one blob pair the omission below is an ordinary missing entry
                # and the control is about nothing.
                failures.append(
                    f"the duplicate-entry fixture's two files do not share one "
                    f"blob pair ({_ix10}), so dropping one of them does not "
                    f"exercise what this control is about")
            elif len(_secs10) != 2 or len(_keep10) != 1:
                failures.append(
                    f"the duplicate-entry fixture's patch has {len(_secs10)} "
                    f"file section(s), not the two it was built to have")
            else:
                write_lf(_snap10, _orig10.split("diff --git ")[0]
                         + "".join(_keep10))
                _t10 = json.loads((c10 / "target.json")
                                  .read_text(encoding="utf-8"))
                _t10["diff_hash"] = sha256_file(_snap10)
                write_lf(c10 / "target.json", json.dumps(_t10, indent=2))
                _n10 = sha256_file(c10 / "target.json")
                write_lf(c10 / "target.sha256", _n10 + "\n")
                _ci10 = c10 / "codex-input.md"
                write_lf(_ci10, _ci10.read_text(encoding="utf-8")
                         .replace(_th10, _n10))

                _p10 = sh(sys.executable,
                          str(t10 / "scripts" / "validate_cycle.py"), str(c10),
                          cwd=t10)
                _o10 = _p10.stdout + _p10.stderr
                if _p10.returncode == 0:
                    failures.append(
                        "a patch showing one of two identical changes passed "
                        "MC-2. Both files move between the same pair of "
                        "objects, so comparing sets of blob pairs cannot tell "
                        "one file from two, and half the change under review "
                        "was never shown to the reviewer.")
                elif "does not describe the change its own target names" not in _o10:
                    failures.append(f"refused, but not for the omitted file\n"
                                    f"{_o10[-400:]}")
                else:
                    print("  [ok] refused: a patch omitting one of two files "
                          "that share a blob pair")

    # ---- C02-F09: a missing snapshot is not replaced by a live file ----
    # "Deleting an implementation cycle's preserved diff, test results,
    # approved plan, or approval record does not necessarily invalidate it:
    # each missing snapshot can be replaced implicitly by today's matching live
    # file... The cycle consequently passes without the preserved evidence it
    # was supposed to retain and becomes dependent on later working-tree
    # changes again."
    #
    # One snapshot at a time, with the live file left exactly where it is, which
    # is what Codex asked for. A matching live file is the hard case: the bytes
    # agree, so nothing looks wrong, and the cycle has still lost the property
    # that made it a record.
    print()
    print("C02-F09  preserved implementation evidence")

    t9 = make_repo(); made.append(t9)
    do_init(t9)
    base9 = impl_base(t9, "def g():\n    return 7\n")
    write_lf(t9 / "results.txt", "7 passed, 0 failed\n")
    head9 = sh("git", "rev-parse", "HEAD", cwd=t9).stdout.strip()
    plan9 = impl_approval(t9)
    r = runner(t9, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--candidate-commit", head9,
               "--approved-plan-hash", plan9, "--base", base9,
               "--test-results", "results.txt")
    c9 = t9 / "runs" / "T-001" / "implementation-review" / "cycle-01"
    if r.returncode != 0:
        failures.append(f"the C02-F09 fixture could not be frozen:\n"
                        f"{r.stdout}{r.stderr}")
    else:
        _th9 = (c9 / "target.sha256").read_text(encoding="utf-8").strip()
        write_lf(t9 / "reply9.md",
                 f"TARGET_SHA256 {_th9}\n\nNo findings in any category.\n")
        _r9 = runner(t9, "record", "--cycle", str(c9), "--output", "reply9.md",
                     "--invocation", "manual", "--zero-findings")
        if _r9.returncode != 0:
            failures.append(f"the C02-F09 fixture could not be recorded:\n"
                            f"{_r9.stdout}{_r9.stderr}")
        else:
            def _mc2_9() -> subprocess.CompletedProcess:
                return sh(sys.executable,
                          str(t9 / "scripts" / "validate_cycle.py"), str(c9),
                          cwd=t9)

            if _mc2_9().returncode != 0:
                failures.append(
                    "the C02-F09 fixture does not pass MC-2 with its evidence "
                    "intact, so every deletion below would prove nothing")
            else:
                print("  [ok] a cycle with its implementation evidence "
                      "preserved passes MC-2")

            _tg9 = json.loads((c9 / "target.json").read_text(encoding="utf-8"))
            for _rel, _needle, _what in (
                    (_tg9["test_result_path"], "no preserved copy under",
                     "the test results"),
                    (_tg9["approval_record_path"],
                     "approval record snapshot is missing",
                     "the approval record"),
                    (_tg9["approved_plan_path"],
                     "approved plan has no preserved copy",
                     "the approved plan")):
                _snap = c9 / "artifacts" / _rel
                if not _snap.is_file():
                    failures.append(f"fixture: freeze did not preserve {_rel}")
                    continue
                if not (t9 / _rel).is_file():
                    failures.append(
                        f"fixture: {_rel} has no live copy, so deleting its "
                        f"snapshot would not test the fallback")
                    continue
                _kept = _snap.read_bytes()
                _snap.unlink()
                _rr = _mc2_9()
                _out9 = _rr.stdout + _rr.stderr
                _snap.write_bytes(_kept)
                if _rr.returncode == 0:
                    failures.append(
                        f"the snapshot of {_what} was deleted and the cycle "
                        f"still passed: a live file standing in for preserved "
                        f"evidence, which is C02-F09 exactly")
                elif _needle not in _out9:
                    failures.append(
                        f"refused after deleting the snapshot of {_what}, but "
                        f"not for the missing preserved copy\n{_out9}")
                else:
                    print(f"  [ok] refused: {_what} has no preserved copy, and "
                          f"the live file is not a substitute")

            if _mc2_9().returncode != 0:
                failures.append(
                    "the fixture did not survive its own controls; the "
                    "restores above are incomplete and later results here are "
                    "not attributable")

    # ---- C02-F10: the controls preserved and run, not counted ----
    # "A count and an implementer description cannot establish fixture
    # validity, the intended refusal, absence of unintended failing
    # prerequisites, mutation sensitivity, or interruption behavior... Preserve
    # or otherwise make those exact suite bytes available, not only their
    # path/hash manifest... with a clear distinction between source inspection,
    # observed execution, and implementer assertion."
    print()
    print("C02-F10  auxiliary control evidence")

    GREEN_SUITE = ("import sys\n\nprint('  [ok] a control that holds')\n"
                   "sys.exit(0)\n")
    RED_SUITE = ("import sys\n\nprint('FAIL: a control that does not hold')\n"
                 "sys.exit(1)\n")

    t10 = make_repo(); made.append(t10)
    write_lf(t10 / "scripts" / "test_green_fixture.py", GREEN_SUITE)
    do_init(t10)
    r = do_freeze(t10)
    c10 = t10 / "runs" / "T-001" / "plan-review" / "cycle-01"
    if r.returncode != 0:
        failures.append(f"a freeze with a passing control suite was refused:\n"
                        f"{r.stdout}{r.stderr}")
    else:
        _pres = c10 / "auxiliary" / "scripts" / "test_green_fixture.py"
        _run = c10 / "auxiliary" / "observed-run.txt"
        _man = json.loads((c10 / "auxiliary-evidence.json")
                          .read_text(encoding="utf-8"))
        _entry = next((s for s in _man["suites"]
                       if s["path"].endswith("test_green_fixture.py")), None)
        # C02-F03, second pass. The dating rule is worth nothing if the freeze
        # does not emit the field, and a checker that never sees one would go
        # on dating records by inference without anybody noticing.
        _tg10 = json.loads((c10 / "target.json").read_text(encoding="utf-8"))
        if _tg10.get("evidence_format") != "cycle-target/1":
            failures.append(
                f"the freeze did not declare the evidence format, so every "
                f"target it writes still has to be dated by guessing at its "
                f"contents: {_tg10.get('evidence_format')!r}")
        else:
            print("  [ok] a frozen target declares the evidence format it was "
                  "written in")
        if not _pres.is_file():
            failures.append(
                "the control suite's bytes were not preserved, so the reviewer "
                "has a filename and a digest and nothing to read. That is the "
                "manifest cycle 02 refused.")
        elif _pres.read_text(encoding="utf-8") != GREEN_SUITE:
            failures.append("the preserved control suite is not the suite")
        elif not _run.is_file():
            failures.append("no observed run was recorded, so execution is "
                            "still an assertion")
        elif "test_green_fixture.py   exit 0" not in \
                _run.read_text(encoding="utf-8"):
            failures.append(f"the observed run does not record this suite's "
                            f"outcome\n{_run.read_text(encoding='utf-8')[:400]}")
        elif _entry is None or _entry.get("observed_exit_code") != 0:
            failures.append(f"the manifest does not carry the observed "
                            f"outcome: {_entry}")
        elif _man["observed_run"]["sha256"] != sha256_file(_run):
            failures.append("the manifest's digest does not describe the "
                            "observed run beside it")
        else:
            print("  [ok] control sources preserved and their run observed, "
                  "both bound to the record")

    # A suite that does not pass must be named, or the freeze is telling a
    # reviewer the repairs are held by controls while one of them is red.
    t10b = make_repo(); made.append(t10b)
    write_lf(t10b / "scripts" / "test_red_fixture.py", RED_SUITE)
    do_init(t10b)
    r = do_freeze(t10b)
    if r.returncode == 0:
        failures.append(
            "a cycle froze with a failing control suite and said nothing. The "
            "prompt would then claim the repairs are watched by controls, one "
            "of which does not run.")
    elif "test_red_fixture.py" not in (r.stdout + r.stderr):
        failures.append(f"refused, but without naming the suite that failed\n"
                        f"{r.stdout}{r.stderr}")
    elif (t10b / "runs" / "T-001" / "plan-review" / "cycle-01").exists():
        failures.append(
            "the refusal left a cycle directory behind, so the next freeze "
            "fails over a half-made cycle rather than over whatever it is "
            "actually given. A refused command has to be a no-op.")
    else:
        print("  [ok] refused: a control suite that does not pass, unnamed, "
              "and nothing created")

    r = do_freeze(t10b, "--aux-known-red", "test_red_fixture.py")
    if r.returncode == 0:
        failures.append("a known-red suite was accepted with no reason given")
    elif "requires --aux-known-red-reason" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the missing reason\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: a known failure with no account of it")

    r = do_freeze(t10b, "--aux-known-red", "test_red_fixture.py",
                  "--aux-known-red-reason",
                  "pre-existing: an approval package for a run with no ledger "
                  "stays silent, and silence reads as no findings")
    if r.returncode != 0:
        failures.append(f"a named and explained failure was still refused:\n"
                        f"{r.stdout}{r.stderr}")
    else:
        _c = t10b / "runs" / "T-001" / "plan-review" / "cycle-01"
        _m = json.loads((_c / "auxiliary-evidence.json")
                        .read_text(encoding="utf-8"))
        if _m["observed_run"]["known_red"] != ["test_red_fixture.py"]:
            failures.append(f"the record does not name the known failure: "
                            f"{_m['observed_run']}")
        elif "silence reads as no findings" not in \
                _m["observed_run"]["known_red_reason"]:
            failures.append("the record does not carry the reason")
        elif "exit 1" not in (_c / "auxiliary" / "observed-run.txt") \
                .read_text(encoding="utf-8"):
            failures.append("the observed run does not show the failure it was "
                            "excused for")
        else:
            print("  [ok] a named failure is recorded with its reason and its "
                  "output, not hidden")

    # ---- B01-F05: a mutable reference is resolved before it is recorded ----
    # Alex Zamurko, 10 September: "resolve any mutable reference such as HEAD to
    # an immutable commit SHA at freeze time and verify the corresponding tree
    # hash." Before this the reference was stored as typed, so a target could
    # name HEAD and the reviewed implementation could move underneath it while
    # checks 11 and 12 kept passing against whatever HEAD had become.
    print()
    print("mutable candidate references")

    t5 = make_repo(); made.append(t5)
    do_init(t5)
    base5 = impl_base(t5)
    write_lf(t5 / "results.txt", "ok\n")
    head = sh("git", "rev-parse", "HEAD", cwd=t5).stdout.strip()
    plan5 = impl_approval(t5)
    r = runner(t5, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD",
               "--approved-plan-hash", plan5, "--base", base5,
               "--test-results", "results.txt")
    if r.returncode != 0:
        failures.append(f"freezing with HEAD was refused outright; the decision "
                        f"is to resolve it, not reject it\n{r.stdout}{r.stderr}")
    else:
        tgt = json.loads((t5 / "runs/T-001/implementation-review/cycle-01"
                          / "target.json").read_text(encoding="utf-8"))
        if tgt["candidate_commit"] == "HEAD":
            failures.append("the target recorded the literal reference HEAD, so "
                            "the reviewed implementation can still move under it")
        elif tgt["candidate_commit"] != head:
            failures.append(f"HEAD resolved to {tgt['candidate_commit']}, "
                            f"expected {head}")
        elif tgt.get("candidate_commit_supplied") != "HEAD":
            failures.append("the target does not record that a mutable "
                            "reference was supplied, so a reader cannot tell")
        else:
            # The tree must belong to the resolved commit, not be re-derived
            # from the name a second time.
            tree = sh("git", "rev-parse", f"{head}^{{tree}}", cwd=t5).stdout.strip()
            if tgt["candidate_tree_hash"] != tree:
                failures.append("the recorded tree does not belong to the "
                                "resolved commit")
            else:
                print("  [ok] HEAD is resolved to an immutable SHA, the "
                      "reference is recorded, and the tree matches")

    # And the resolution has to actually bind: moving HEAD afterwards must not
    # change what the frozen cycle refers to.
    if r.returncode == 0:
        write_lf(t5 / "later.txt", "a commit made after the freeze\n")
        sh("git", "add", "-A", cwd=t5)
        sh("git", "commit", "-qm", "after the freeze", cwd=t5)
        new_head = sh("git", "rev-parse", "HEAD", cwd=t5).stdout.strip()
        tgt = json.loads((t5 / "runs/T-001/implementation-review/cycle-01"
                          / "target.json").read_text(encoding="utf-8"))
        if new_head == head:
            failures.append("fixture: HEAD did not move")
        elif tgt["candidate_commit"] != head:
            failures.append("the frozen target followed HEAD to a later commit")
        else:
            print("  [ok] the frozen target still names the commit that was "
                  "reviewed after HEAD moves on")

    def impl_no_base(t: Path):
        do_init(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD",
                      "--approved-plan-hash", GOOD_HASH)
    expect_refused("implementation review with no comparison base",
                   "requires --base", impl_no_base)

    # C02-F08. A supplied diff is refused rather than ignored, so nobody is left
    # believing the file they named was the one reviewed.
    def impl_supplied_diff(t: Path):
        do_init(t)
        write_lf(t / "candidate.diff", "--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n")
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD",
                      "--approved-plan-hash", GOOD_HASH, "--base", "HEAD~1",
                      "--diff", "candidate.diff")
    expect_refused("a diff supplied beside the candidate",
                   "no longer accepted", impl_supplied_diff)

    def impl_no_test_results(t: Path):
        do_init(t)
        _b = impl_base(t)
        return runner(t, "freeze", "--run", "T-001", "--type", "implementation",
                      "--prompt", "specs/prompt.md", "--candidate-commit", "HEAD",
                      "--approved-plan-hash", GOOD_HASH, "--base", _b)
    expect_refused("implementation review with no test results",
                   "requires --test-results", impl_no_test_results)

    def record_twice(t: Path):
        do_init(t)
        do_freeze(t)
        cyc = t / "runs" / "T-001" / "plan-review" / "cycle-01"
        write_lf(t / "reply.md", reply_for(t,
                     "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                     "Requirement ID: R-B7\nEvidence: ...\n"))
        runner(t, "record", "--cycle", str(cyc), "--output", "reply.md",
               "--invocation", "manual")
        write_lf(t / "reply2.md", reply_for(t, "Finding ID: C01-F02\n"
                                       "Class: WRONG OWNERSHIP\n"))
        return runner(t, "record", "--cycle", str(cyc), "--output", "reply2.md",
                      "--invocation", "manual")
    # Was a flat write-once refusal. Issue 6 replaced it: a second capture is
    # recorded and preserved, it simply does not displace the designated one
    # without explicit invalidation. The evidence is still never overwritten.
    expect_refused("re-recording without superseding", "already the authoritative",
                   record_twice)

    def record_unfrozen(t: Path):
        write_lf(t / "reply.md", reply_for(t,
                     "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                     "Requirement ID: R-B7\nEvidence: ...\n"))
        return runner(t, "record", "--cycle", str(t / "nowhere"),
                      "--output", "reply.md", "--invocation", "manual")
    expect_refused("record against an unfrozen directory", "not a frozen cycle", record_unfrozen)

    def record_empty(t: Path):
        do_init(t)
        do_freeze(t)
        write_lf(t / "reply.md", "")
        return runner(t, "record", "--cycle",
                      str(t / "runs" / "T-001" / "plan-review" / "cycle-01"),
                      "--output", "reply.md", "--invocation", "manual")
    expect_refused("empty reviewer output", "reviewer output is empty", record_empty)

    def freeze_over_existing(t: Path):
        do_init(t)
        fake_cycles(t, 1)
        # next_cycle only counts directories, so a non-directory sitting on the
        # next cycle's name is the one way the path can be occupied. Without the
        # guard this surfaces as a mkdir traceback rather than a refusal.
        write_lf(t / "runs" / "T-001" / "plan-review" / "cycle-02", "stray\n")
        return do_freeze(t)
    expect_refused("cycle path already occupied", "already exists", freeze_over_existing)

    # ---- the bootstrap gate, from the runner's side ----
    # Every init above passes --bootstrap-exempt, so without these three the gate
    # would be entirely absent from this suite and could be deleted from
    # cmd_init without a single test noticing.
    print()
    print("bootstrap gate")

    def real_init(t: Path) -> subprocess.CompletedProcess:
        return runner(t, "init", "--run", "A1E-001", "--protocol",
                      "specs/protocol.md", "--spec", "specs/spec.md")

    expect_refused("a real run created with no bootstrap review",
                   "bootstrap_review not satisfied", real_init)

    t2 = make_repo(); made.append(t2)
    if approve_bootstrap(t2).returncode != 0:
        failures.append("could not record a bootstrap approval in the fixture")
    else:
        r = real_init(t2)
        if r.returncode != 0:
            failures.append("a real run was refused despite an approved bootstrap "
                            f"review; the gate would block everything:\n{r.stdout}{r.stderr}")
        else:
            run_json = json.loads(
                (t2 / "runs" / "A1E-001" / "run.json").read_text(encoding="utf-8"))
            if run_json.get("bootstrap_review") != "APPROVED":
                failures.append("the run does not record that it ran under an "
                                "approved bootstrap review")
            else:
                print("  [ok] a real run proceeds once the bootstrap review is approved")

    # Editing a gated component after approval must re-block, or the approval
    # outlives the code it covered. Asserted inline rather than through
    # expect_refused, which builds its own fresh repo: this control needs the
    # same repo that was just approved, and a fresh one would refuse for the
    # ordinary no-review reason and look like a pass.
    p = t2 / "scripts" / "validate_cycle.py"
    p.write_text(p.read_text(encoding="utf-8") + "\n# later edit\n", encoding="utf-8")
    r = runner(t2, "init", "--run", "A1E-002", "--protocol", "specs/protocol.md",
               "--spec", "specs/spec.md")
    blob = (r.stdout + r.stderr).lower()
    if r.returncode == 0:
        failures.append("a real run was created after a reviewed component "
                        "changed; the approval outlived the code it covered")
    elif "has changed since it was reviewed" not in blob:
        failures.append("refused after a component changed, but not for that "
                        f"reason:\n  got {blob.strip()[:300]}")
    else:
        print("  [ok] refused: a real run after a reviewed component changed")

    # ---- issue 4: authoritative per-cycle findings ----
    # Alex Zamurko, 9 September: "Add tests for populated findings, explicit
    # zero findings, missing findings, and malformed findings."
    print()
    print("authoritative findings")

    def recorded(t: Path, body: str, *extra: str):
        do_init(t)
        do_freeze(t)
        write_lf(t / "reply.md", reply_for(t, body))
        cyc = t / "runs" / "T-001" / "plan-review" / "cycle-01"
        return runner(t, "record", "--cycle", str(cyc), "--output", "reply.md",
                      "--invocation", "manual", *extra), cyc

    POPULATED = ("Finding ID: C01-F01\nClass: UNTESTED RULE\nEvidence: x\n\n"
                 "Finding ID: C01-F02\nClass: WRONG OWNERSHIP\nEvidence: y\n")

    t6 = make_repo(); made.append(t6)
    r, cyc = recorded(t6, POPULATED)
    if r.returncode != 0:
        failures.append(f"recording populated findings failed:\n{r.stdout}{r.stderr}")
    else:
        d = json.loads((cyc / "findings.json").read_text(encoding="utf-8"))
        ids = [f["id"] for f in d["findings"]]
        if ids != ["C01-F01", "C01-F02"] or d["count"] != 2:
            failures.append(f"findings.json did not capture both findings: {d}")
        elif d.get("source_sha256") != hashlib.sha256(
                (cyc / "codex-output-raw.md").read_bytes()).hexdigest():
            failures.append("findings.json is not bound to the capture it was "
                            "extracted from")
        else:
            print("  [ok] populated: both findings extracted and bound to the capture")

    t7 = make_repo(); made.append(t7)
    r, cyc = recorded(t7, "The plan is sound. No findings.\n", "--zero-findings")
    if r.returncode != 0:
        failures.append(f"explicit zero findings should record:\n{r.stdout}{r.stderr}")
    else:
        d = json.loads((cyc / "findings.json").read_text(encoding="utf-8"))
        if d["count"] != 0 or not d.get("zero_findings_asserted"):
            failures.append("zero findings recorded without the assertion flag")
        else:
            print("  [ok] explicit zero: recorded as asserted, not inferred")

    t8 = make_repo(); made.append(t8)
    r, _ = recorded(t8, "The plan is sound. No findings.\n")
    if r.returncode == 0:
        failures.append("a review with no finding blocks recorded silently as "
                        "zero; absence must never mean zero")
    elif "--zero-findings" not in (r.stdout + r.stderr):
        failures.append("refused a no-blocks review without naming --zero-findings")
    else:
        print("  [ok] refused: no finding blocks and no explicit zero assertion")

    t9 = make_repo(); made.append(t9)
    r, _ = recorded(t9, POPULATED, "--zero-findings")
    if r.returncode == 0:
        failures.append("--zero-findings accepted alongside two finding blocks")
    else:
        print("  [ok] refused: --zero-findings contradicted by present findings")

    t10 = make_repo(); made.append(t10)
    r, cyc = recorded(t10, "Finding ID: C01-F01\nClass: SOMETHING INVENTED\n")
    if r.returncode == 0:
        failures.append("a class outside the closed vocabulary was recorded")
    elif (cyc / "codex-output-raw.md").exists():
        failures.append("raw output was written despite the findings being "
                        "unparseable; nothing should be written on refusal")
    else:
        print("  [ok] refused: class outside §4, and nothing written")

    t11 = make_repo(); made.append(t11)
    r, cyc = recorded(t11, "Finding ID: C01-F01\nEvidence: no class line here\n")
    if r.returncode == 0:
        failures.append("a finding block with no Class: line was recorded")
    elif "neither a Class: line nor a Status: line" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the missing class line\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: finding block with no class")

    # ---- issue 5: deterministic review-result integrity ----
    # Alex Zamurko's minimum spec, 9 September. The first version of
    # --zero-findings stopped absence meaning zero, but left the case he named:
    # the reviewer produced findings, the parser failed to see them, and an
    # honest operator asserts zero over a review nobody read correctly.
    print()
    print("review-result integrity")

    t12 = make_repo(); made.append(t12)
    r, _ = recorded(t12, "Required correction: separate the deficiency.\n",
                    "--zero-findings")
    if r.returncode == 0:
        failures.append("zero was asserted over a review carrying finding "
                        "signals the parser did not account for")
    else:
        print("  [ok] refused: zero asserted over an unparsed finding signal")

    t13 = make_repo(); made.append(t13)
    r, _ = recorded(t13, "Finding ID: not-an-id\nClass: UNTESTED RULE\n")
    if r.returncode == 0:
        failures.append("an identifier outside the canonical grammar was "
                        "silently accepted")
    elif "canonical grammar" not in (r.stdout + r.stderr):
        failures.append("refused a bad identifier without naming the grammar")
    else:
        print("  [ok] refused: identifier outside the canonical grammar")

    # Requirement 5: never silently corrected. The refusal above must not have
    # written a repaired identifier anywhere.
    t14 = make_repo(); made.append(t14)
    r, cyc = recorded(t14, "Finding ID: C1-F1\nClass: UNTESTED RULE\n")
    if (cyc / "findings.json").exists():
        failures.append("a findings.json was written for a review whose "
                        "identifier failed the grammar")
    else:
        print("  [ok] a malformed identifier writes nothing, corrected or otherwise")

    # The grammar has one authoritative home, and the runner reads it rather
    # than restating it. Break the declaration and the parse must stop.
    t15 = make_repo(); made.append(t15)
    sch = t15 / "specs" / "evidence-schema-v1.0.md"
    sch.write_text(sch.read_text(encoding="utf-8")
                   .replace("FINDING_ID_GRAMMAR", "REMOVED_GRAMMAR"),
                   encoding="utf-8")
    r, _ = recorded(t15, "Finding ID: C01-F01\nClass: UNTESTED RULE\n")
    # This one needed it most. The fixture mutilates the evidence schema, which
    # several earlier checks also read, so a refusal proves the schema is broken
    # and not that the missing grammar is what noticed.
    if r.returncode == 0:
        failures.append("the runner parsed findings with no canonical grammar "
                        "declared; it is carrying its own copy")
    elif "no FINDING_ID_GRAMMAR declared" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the absent grammar declaration\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: no canonical grammar declared in the schema")

    # ---- issue 6: authoritative capture ----
    # Before this, a failed capture killed the cycle, so the only way to retry
    # was to delete what was there. That happened three times in one afternoon,
    # two junk captures passed MC-2, and a better capture sat unnoticed in
    # another directory with nothing saying which governed.
    print()
    print("authoritative capture")

    def with_target(t: Path, body: str) -> str:
        th = (t / "runs" / "T-001" / "plan-review" / "cycle-01"
              / "target.sha256").read_text(encoding="utf-8").strip()
        return f"TARGET_SHA256 {th}\n\n{body}"

    GOOD = "Finding ID: C01-F01\nClass: UNTESTED RULE\nEvidence: x\n"

    t16 = make_repo(); made.append(t16)
    do_init(t16); do_freeze(t16)
    cyc = t16 / "runs" / "T-001" / "plan-review" / "cycle-01"
    write_lf(t16 / "junk.md", "Get-Clipboard -Raw | Set-Content reply.md\n")
    r = runner(t16, "record", "--cycle", str(cyc), "--output", "junk.md",
               "--invocation", "manual")
    if r.returncode == 0:
        failures.append("a capture not quoting the target hash was accepted")
    elif not (cyc / "captures" / "attempt-01" / "raw.md").is_file():
        failures.append("a rejected capture was not preserved; the only way to "
                        "retry is then to delete evidence, which is the "
                        "behaviour issue 6 removes")
    else:
        print("  [ok] an invalid capture is refused and preserved, not discarded")

    write_lf(t16 / "good.md", with_target(t16, GOOD))
    r = runner(t16, "record", "--cycle", str(cyc), "--output", "good.md",
               "--invocation", "manual", "--reason", "attempt 1 caught the shell command")
    if r.returncode != 0:
        failures.append(f"a valid retry after a failed capture was refused:\n{r.stdout}{r.stderr}")
    else:
        log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
        if log["authoritative"] != 2 or len(log["attempts"]) != 2:
            failures.append(f"capture log did not record both attempts: {log}")
        else:
            print("  [ok] the first valid capture becomes authoritative, both kept")

    write_lf(t16 / "other.md", with_target(t16, GOOD.replace("F01", "F02")))
    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual")
    if r.returncode == 0:
        failures.append("a later capture displaced the authoritative one with "
                        "no explicit invalidation")
    elif "already the authoritative" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the existing authoritative "
                        f"capture\n{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: a later capture cannot displace silently")

    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual", "--supersede-capture")
    if r.returncode == 0:
        failures.append("--supersede-capture was accepted with no reason")
    elif "requires --reason" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the missing reason\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: superseding without a stated reason")

    # ---- ruling 3, 9 September: supersession needs an outside authority ----
    # "Allowing the implementing agent to choose a later Codex capture creates a
    # direct cherry-picking path. Preserving all attempts is not sufficient if
    # the same party can decide which one governs."
    #
    # --reason alone was not an outside authority. It is a string the
    # implementing agent types, in a command the implementing agent runs.
    log_before = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
    superseded = log_before["authoritative_sha256"]
    superseding = hashlib.sha256((t16 / "other.md").read_bytes()).hexdigest()
    approval_path = cyc / "capture-supersession-approval.json"

    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual", "--supersede-capture",
               "--reason", "partial paste; full reply recaptured")
    if r.returncode == 0:
        failures.append("supersession succeeded on a reason alone, with no "
                        "approval from outside the implementing agent")
    elif "not authorized" not in (r.stdout + r.stderr):
        failures.append(f"supersession refused, but not for want of authority:\n"
                        f"{r.stdout}{r.stderr}")
    elif superseding not in (r.stdout + r.stderr):
        failures.append("the refusal did not print the hashes the approval must "
                        "name, so obtaining one would be guesswork")
    else:
        print("  [ok] refused: a reason alone does not authorize supersession")

    def approve(**over):
        rec = {"schema": "capture-supersession/2",
               "cycle": cyc.name,
               "superseded_sha256": superseded,
               "superseding_sha256": superseding,
               "authorized_by": "Alex Zamurko",
               "reason": "attempt 2 truncated mid-finding; recapture is complete",
               "at": "2026-09-09T21:40:00Z",
               # Alex Zamurko, 9 October 2026: an authorisation must be
               # verifiable rather than resting on a name someone typed. The
               # source says where he actually said it and quotes the words,
               # so a reader can go and check. It does not prove authorship
               # and the code says so; see AR-2 in specs/ACCEPTED-RISKS.md.
               "source": {
                   "medium": "Slack",
                   "reference": "workflow channel, 9 September 2026, 9:38 pm",
                   "quote": "go ahead and replace that capture"}}
        rec.update(over)
        write_lf(approval_path, json.dumps(rec, indent=2) + "\n")

    # Alex Zamurko, 16 October 2026, on D04-F01: "use a stable, identifiable
    # failure signal from its named test, preferably a specific test or
    # assertion identifier rather than fragile prose."
    #
    # The probe matched D04-F01 on "is null: accepted". Six controls in this
    # function end their label that way: three source fields and three
    # top-level fields, each generated with "null" among its bad values. So a
    # sweep could remove the repair, watch an unintended control go red, and
    # count it as a catch. That is the wrong-control result his decision
    # refuses, and the preflight anchor check cannot see it, because the
    # anchor is fine and the signal is ambiguous.
    #
    # Each control now carries an identifier that is assigned rather than
    # derived from its wording, so rewording the label cannot move it and two
    # controls cannot collide into one signal. seen_ids below refuses a
    # duplicate, because an identifier that is not unique is the same defect
    # wearing a shorter name.
    seen_ids: dict[str, str] = {}

    def refuse_with(cid: str, label: str, needle: str, **over) -> None:
        if cid in seen_ids:
            failures.append(f"control id {cid} is used twice: "
                            f"{seen_ids[cid]!r} and {label!r}. A signal that "
                            f"names two controls names neither.")
            return
        seen_ids[cid] = label
        approve(**over)
        rr = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
                    "--invocation", "manual", "--supersede-capture",
                    "--reason", "partial paste; full reply recaptured")
        if rr.returncode == 0:
            failures.append(f"[{cid}] {label}: accepted")
        elif needle.lower() not in (rr.stdout + rr.stderr).lower():
            failures.append(f"[{cid}] {label}: refused for the wrong reason\n"
                            f"  wanted {needle!r}\n  got {(rr.stderr + rr.stdout)[:300]}")
        else:
            print(f"  [ok] [{cid}] refused: {label}")

    refuse_with("AUTH-WHO-EMPTY",
                "an approval naming nobody", "authorized_by", authorized_by="")
    refuse_with("AUTH-REASON-PLACEHOLDER",
                "an approval whose reason is a placeholder", "at least",
                reason="ok")
    refuse_with("AUTH-CAPTURE-MISMATCH",
                "an approval for a different capture", "does not match",
                superseding_sha256="0" * 64)
    refuse_with("AUTH-CYCLE-MISMATCH",
                "an approval for a different cycle", "does not match",
                cycle="cycle-09")
    refuse_with("AUTH-SCHEMA-WRONG",
                "an approval of the wrong kind", "schema",
                schema="runner-approval/1")

    # B02-F10, second half. Alex Zamurko: "Add negative controls for every
    # claimed refusal, including malformed JSON and absent timestamp cases."
    # Both refusals existed in require_approval and neither was exercised, while
    # the suite's closing line reported every refusal as reachable.
    refuse_with("AUTH-AT-EMPTY",
                "an approval with no timestamp", "no `at` timestamp", at="")

    # Alex Zamurko, 9 October 2026: "Make sure the authorisation is properly
    # documented and can be verified, rather than relying only on a name
    # entered into a file." Four refusals, because the source has three parts
    # that each do different work and a quote too short to match is the same
    # as no quote at all.
    refuse_with("AUTH-SRC-ABSENT",
                "an approval with no source at all", "no `source`",
                source=None)
    refuse_with("AUTH-SRC-MEDIUM-EMPTY",
                "an approval whose source names no medium", "medium",
                source={"medium": "", "reference": "somewhere",
                        "quote": "go ahead and replace that capture"})
    refuse_with("AUTH-SRC-REFERENCE-EMPTY",
                "an approval whose source cannot be located", "reference",
                source={"medium": "Slack", "reference": "",
                        "quote": "go ahead and replace that capture"})
    refuse_with("AUTH-SRC-QUOTE-EMPTY",
                "an approval quoting nothing", "quote",
                source={"medium": "Slack", "reference": "workflow channel",
                        "quote": ""})
    refuse_with("AUTH-SRC-QUOTE-SHORT",
                "an approval whose quote is too short to match", "at least",
                source={"medium": "Slack", "reference": "workflow channel",
                        "quote": "ok fine"})

    # Grandfathering, and the hole in it.
    #
    # Requiring a source from approvals recorded before anyone asked for one
    # would mean either editing those records, which is rewriting evidence, or
    # a gate that refuses its own history. So a record declares which rule it
    # was made under, exactly as C03-F01 made a finished review reparse with
    # its own grammar rather than today's.
    #
    # This case proves the old rule is actually applied rather than merely
    # described: a pre-cutoff `/1` record with no source at all must get past
    # the source check and fail on the hash binding instead. If the source
    # check still ran, the refusal would name the source and this would fail.
    refuse_with("AUTH-GRANDFATHER-PREDATES",
                "a /1 approval from before the rule is read under the old one",
                "does not match",
                schema="capture-supersession/1", at="2026-09-09T21:40:00Z",
                source=None, superseding_sha256="0" * 64)

    # And the hole: declaring the old schema on a record written after the
    # rule took effect would opt out of it by typing one character.
    refuse_with("AUTH-GRANDFATHER-AFTER",
                "a /1 approval dated after the rule does not get the old one",
                "predates the requirement",
                schema="capture-supersession/1", at="2026-10-09T12:00:00Z",
                source=None)

    # D04-F01, BOOTSTRAP-003 cycle 04. Every presence check here was written
    # as `str(x).strip()`, and `str(None)` is the four-character string
    # "None", so a JSON null satisfied every one of them. The five controls
    # above all test the empty string and not one tests null, which is the
    # same failure as the rule they guard: checking the shape you thought of.
    #
    # The reviewer named the source fields. These cover the other three in
    # the same function, because the expression was identical in all of them
    # and repairing only what was pointed at is what D02-F01 took three
    # cycles to teach.
    # Alex Zamurko, 11 October: "Verify rejection of null, non-string values,
    # missing fields and whitespace-only strings across all relevant source
    # fields." Written as a matrix rather than as the cases that occurred to
    # me, because the cases that occurred to me are what produced D04-F01:
    # five controls for this rule and all five tested the empty string.
    #
    # Every field crossed with every way a value can fail to be one. Twelve
    # for the source, nine for the fields around it. The loop is deliberate:
    # a list written by hand has the same blind spot as the one before it.
    _OK_SOURCE = {"medium": "Slack",
                  "reference": "workflow channel, 9 September 2026",
                  "quote": "go ahead and replace that capture"}
    # The identifier token is carried in the table rather than made from the
    # prose. Slugifying "whitespace only" would work until somebody writes
    # "only whitespace", which is the dependency being removed.
    _BAD = (("null", None, "NULL"), ("a number", 7, "NUMBER"),
            ("a list", [], "LIST"), ("whitespace only", "   ", "BLANK"),
            ("absent", "__omit__", "MISSING"))

    for _f in ("medium", "reference", "quote"):
        for _how, _val, _tok in _BAD:
            _src = dict(_OK_SOURCE)
            if _val == "__omit__":
                _src.pop(_f)
            else:
                _src[_f] = _val
            refuse_with(f"AUTH-SRC-{_f.upper()}-{_tok}",
                        f"an approval whose source {_f} is {_how}", _f,
                        source=_src)

    # The three beside the source carried the identical expression and so the
    # identical defect. The reviewer named only the source; repairing what was
    # pointed at is what D02-F01 took three cycles to teach.
    for _f, _needle in (("authorized_by", "authorized_by"),
                        ("reason", "at least"),
                        ("at", "no `at` timestamp")):
        for _how, _val, _tok in _BAD[:4]:
            refuse_with(f"AUTH-{_f.upper()}-{_tok}",
                        f"an approval whose {_f} is {_how}", _needle,
                        **{_f: _val})

    write_lf(approval_path, "{ this is not json\n")
    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual", "--supersede-capture",
               "--reason", "partial paste; full reply recaptured")
    if r.returncode == 0:
        failures.append("a malformed approval record was accepted")
    elif "not valid JSON" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the malformed record\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: an approval record that is not valid JSON")

    # ---- B02-F04: a refused supersession must leave the cycle intact ----
    # Codex's reproduction, exactly: a valid authoritative capture, a correctly
    # bound approval, and a replacement containing a finding, invoked with
    # --zero-findings. The command returned 1 saying "Nothing written" while
    # codex-output-raw.md and findings.json had already been deleted and the
    # log still designated the old attempt. The bytes survived in captures/;
    # the cycle did not.
    approve()
    before_raw = (cyc / "codex-output-raw.md").read_bytes()
    before_fj = (cyc / "findings.json").read_bytes()
    before_log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual", "--supersede-capture",
               "--reason", "partial paste; full reply recaptured",
               "--zero-findings")
    if r.returncode == 0:
        failures.append("--zero-findings was accepted against a reply carrying "
                        "a finding")
    elif not (cyc / "codex-output-raw.md").is_file():
        failures.append("a refused supersession deleted codex-output-raw.md; "
                        "the cycle was destroyed by a command that reported "
                        "nothing written")
    elif not (cyc / "findings.json").is_file():
        failures.append("a refused supersession deleted findings.json")
    elif (cyc / "codex-output-raw.md").read_bytes() != before_raw:
        failures.append("a refused supersession altered the authoritative raw "
                        "capture")
    elif (cyc / "findings.json").read_bytes() != before_fj:
        failures.append("a refused supersession altered findings.json")
    else:
        after_log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
        if after_log.get("authoritative") != before_log.get("authoritative"):
            failures.append("a refused supersession moved the designation")
        else:
            print("  [ok] a refused supersession leaves the authoritative "
                  "capture, findings and designation intact")

    # The refusal above created an attempt directory. The log must know about
    # it, or next_attempt (which counts directories) and the log disagree, and
    # the next designation points past the end of the recorded attempts. Found
    # only because the B02-F04 control happened to run a refusal before a
    # success; nothing was asserting it.
    _log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
    _dirs = sorted((cyc / "captures").glob("attempt-*"))
    if len(_log["attempts"]) != len(_dirs):
        failures.append(
            f"the capture log records {len(_log['attempts'])} attempt(s) but "
            f"{len(_dirs)} exist on disk. A refused attempt is preserved and "
            "must be recorded, or the count of attempts is understated.")
    else:
        print(f"  [ok] a refused attempt is recorded in the log, not only on "
              f"disk ({len(_dirs)} attempts)")

    r = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
               "--invocation", "manual", "--supersede-capture",
               "--reason", "partial paste; full reply recaptured")
    if r.returncode != 0:
        failures.append(f"an authorized supersession was refused:\n{r.stdout}{r.stderr}")
    else:
        log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
        # Every attempt so far, counted rather than hardcoded. A refused
        # supersession still preserves its attempt — that is issue 6's whole
        # point — so inserting the B02-F04 control above consumes a number, and
        # a literal 3 here made this control fail for a reason that had nothing
        # to do with what it tests.
        n_attempts = len(log["attempts"])
        kept = all((cyc / "captures" / f"attempt-{i:02d}" / "raw.md").is_file()
                   for i in range(1, n_attempts + 1))
        inv = (log.get("invalidated") or [{}])[-1]
        if log["authoritative"] != n_attempts:
            failures.append(
                f"supersession did not move the designation to the new attempt: "
                f"authoritative={log['authoritative']}, attempts={n_attempts}")
        elif not kept:
            failures.append("supersession removed a prior attempt; both must be "
                            "preserved")
        elif not log.get("invalidated"):
            failures.append("supersession did not record the invalidation")
        elif inv.get("authorized_by") != "Alex Zamurko":
            failures.append("the invalidation record does not carry the "
                            "authority, so deleting the approval file would "
                            f"leave an unattributed supersession: {inv}")
        else:
            print("  [ok] an authorized supersession moves the designation, "
                  "keeps every attempt and records who authorized it")

    # The staged files are an implementation detail of the swap and must never
    # outlive it. A leftover .staged file is a half-written record sitting in a
    # cycle directory, which is the kind of thing a later reader treats as
    # evidence.
    debris = sorted(p.name for p in cyc.glob("*.staged")) + \
             sorted(p.name for p in cyc.glob(".*.staged"))
    if debris:
        failures.append(f"staging files survived in the cycle directory: "
                        f"{debris}")
    else:
        print("  [ok] no staging files are left behind in the cycle")

    # ---- C02-F06: a designation earned but never written ----
    # The atomic-write repair above made the designation a single moment. It did
    # not say what happens to a capture that completed every check and was
    # interrupted on the way to being named. Codex: "an interruption after the
    # first attempt's findings.json is written and before the designation rename
    # leaves a complete, valid first capture and a log with authoritative = None.
    # On retry, recovery does nothing, and the caller can supply a different
    # output. That later attempt is designated without supersession approval."
    #
    # Which makes it a route to choosing a more favourable review, with the
    # party the supersession control constrains deciding when the control
    # applies. The ruling it defeats is Alex Zamurko's of 9 September: the first
    # capture meeting the validity requirements governs.
    print()
    print("C02-F06  designation interrupted before it was recorded")

    def interrupt_before_designation(c: Path) -> None:
        """Leave the cycle as a crash at the commit point leaves it.

        Everything recording writes before the designation stays; everything it
        writes after is removed. This is not an approximation of the interrupted
        state, it is that state: the code under test reads the capture log, the
        attempt directories and the working copies, and in all three this is
        byte-identical to a process that died at that line. How the arrangement
        arose is not something it can see.

        Injecting a real crash would need the runner to be killed mid-command,
        which these controls cannot do: they drive it as a subprocess.
        """
        lg = json.loads((c / "capture-log.json").read_text(encoding="utf-8"))
        lg["authoritative"] = None
        lg.pop("authoritative_sha256", None)
        write_lf(c / "capture-log.json", json.dumps(lg, indent=2) + "\n")
        for _n in ("codex-output-raw.md", "findings.json", "invocation.json"):
            (c / _n).unlink(missing_ok=True)

    def f06_fixture(first_body: str = "Finding ID: C01-F01\nClass: UNTESTED "
                                      "RULE\nEvidence: the first capture\n"):
        t = make_repo(); made.append(t)
        do_init(t); do_freeze(t)
        c = t / "runs" / "T-001" / "plan-review" / "cycle-01"
        write_lf(t / "first.md", with_target(t, first_body))
        write_lf(t / "second.md", with_target(
            t, "Finding ID: C01-F02\nClass: MISSING REQUIREMENT\n"
               "Evidence: a different, later capture\n"))
        rr = runner(t, "record", "--cycle", str(c), "--output", "first.md",
                    "--invocation", "manual")
        if rr.returncode != 0:
            failures.append(f"the C02-F06 fixture could not record its first "
                            f"capture:\n{rr.stdout}{rr.stderr}")
        interrupt_before_designation(c)
        return t, c

    t17, c17 = f06_fixture()
    first_sha = hashlib.sha256((t17 / "first.md").read_bytes()).hexdigest()

    r = runner(t17, "record", "--cycle", str(c17), "--output", "second.md",
               "--invocation", "manual")
    _lg = json.loads((c17 / "capture-log.json").read_text(encoding="utf-8"))
    if r.returncode == 0:
        failures.append(
            "a later capture was designated after an interruption left the "
            "first one complete and undesignated. The first valid capture "
            "governs, and displacing it takes a supersession approval.")
    elif _lg.get("authoritative") != 1:
        failures.append(f"the interrupted designation was not recovered, so "
                        f"nothing owns the review: {_lg}")
    elif "C01-F01" not in (c17 / "findings.json").read_text(encoding="utf-8"):
        failures.append("recovery designated the first attempt but published "
                        "findings from somewhere else")
    elif not _lg.get("recovered"):
        failures.append("the designation was recovered without recording that "
                        "it had been, so the log shows an owner no command "
                        "wrote")
    else:
        print("  [ok] an interrupted designation is finished, and the first "
              "valid capture still governs")

    # The other half, and the reason this is a recovery rather than a lock: with
    # the approval the ruling requires, the later capture does take over. Refuse
    # both and the finding would be traded for a cycle nobody can correct.
    write_lf(c17 / "capture-supersession-approval.json", json.dumps({
        "schema": "capture-supersession/1",
        "cycle": c17.name,
        "superseded_sha256": first_sha,
        "superseding_sha256": hashlib.sha256(
            (t17 / "second.md").read_bytes()).hexdigest(),
        "authorized_by": "Alex Zamurko",
        "reason": "the first capture stopped mid-reply; recaptured in full",
        "at": "2026-10-01T10:00:00Z"}, indent=2) + "\n")
    r = runner(t17, "record", "--cycle", str(c17), "--output", "second.md",
               "--invocation", "manual", "--supersede-capture",
               "--reason", "recaptured in full after the first stopped short")
    if r.returncode != 0:
        failures.append(f"an authorized supersession of a recovered capture "
                        f"was refused:\n{r.stdout}{r.stderr}")
    else:
        _lg = json.loads((c17 / "capture-log.json").read_text(encoding="utf-8"))
        _inv = (_lg.get("invalidated") or [{}])[-1]
        if _lg.get("authoritative") != 2:
            failures.append(f"the approved supersession did not move the "
                            f"designation: {_lg}")
        elif _inv.get("attempt") != 1:
            failures.append(f"the supersession did not invalidate the "
                            f"recovered capture it replaced: {_inv}")
        else:
            print("  [ok] a recovered capture is still superseded by an "
                  "approval bound to its bytes")

    # Codex, on what must not become the discriminator: "distinguish a fully
    # valid pending generation from an attempt that failed later semantic
    # checks; do not trust the early valid boolean alone."
    #
    # capture.json records valid=true from capture_validity, which runs before
    # the zero-findings assertion and recurrence resolution. An attempt refused
    # by either still carries that flag and has no findings.json, because that
    # file is written only once everything has passed. So the control is the
    # file, and this proves the two are not confused: the same interruption with
    # the findings record missing leaves nothing to recover.
    t18, c18 = f06_fixture()
    (c18 / "captures" / "attempt-01" / "findings.json").unlink()
    r = runner(t18, "record", "--cycle", str(c18), "--output", "second.md",
               "--invocation", "manual")
    _lg = json.loads((c18 / "capture-log.json").read_text(encoding="utf-8"))
    if r.returncode != 0:
        failures.append(
            f"an attempt interrupted before its findings record was written "
            f"blocked the retry. It never met the designation prerequisites, "
            f"so there is nothing for it to own:\n{r.stdout}{r.stderr}")
    elif _lg.get("recovered"):
        failures.append("an incomplete attempt was recovered as though it were "
                        "a pending generation; valid=true was trusted on its "
                        "own")
    elif _lg.get("authoritative") != 2:
        failures.append(f"the retry did not become authoritative: {_lg}")
    else:
        print("  [ok] an attempt that never completed is not recovered, and "
              "the retry governs")

    # A generation whose findings were read out of other bytes is damaged, not
    # pending. Designating it would bind the cycle to findings its own capture
    # does not support, which is the defect this repair exists to prevent
    # arriving by the repair's own route.
    t19, c19 = f06_fixture()
    _fj = c19 / "captures" / "attempt-01" / "findings.json"
    _doc = json.loads(_fj.read_text(encoding="utf-8"))
    _doc["source_sha256"] = "0" * 64
    write_lf(_fj, json.dumps(_doc, indent=2) + "\n")
    r = runner(t19, "record", "--cycle", str(c19), "--output", "second.md",
               "--invocation", "manual")
    if r.returncode == 0:
        failures.append("an undesignated generation whose findings do not "
                        "describe its own capture was passed over silently, "
                        "and a later capture took the cycle")
    elif "does not describe its own capture" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the mismatched generation\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: a findings record that does not describe its "
              "own capture")

    # ---- B02-F04, the half cycle 04 found still open ----
    # The controls below corrupt working copies while leaving a readable
    # designation, so what they demonstrate is publication recovery. Codex:
    # "They demonstrate publication recovery, not survival of this earlier write
    # boundary." The boundary it means comes before the commit point, where
    # recording rewrites capture-log.json during preparation. Truncate it there
    # and the previous generation is still on disk with nothing able to say
    # which attempt it was.
    #
    # A crash cannot be injected from here. These controls drive the runner as a
    # subprocess, and "die halfway through a write" is not something a command
    # line argument can ask for. So this reads the source and requires every
    # write to that file to be the atomic one.
    #
    # That is a weaker kind of control than the rest of this suite and it is
    # named as such. It also happens to be the kind that fits the claim: the
    # property is that no code path leaves this file partly written, which is a
    # statement about code paths rather than about one execution.
    #
    # Alex Zamurko, 16 September 2026, ruling on exactly this control:
    #
    #   "Acceptable temporarily, but mark it as structural evidence, not
    #    behavioral fault-injection evidence. It does not need to block the
    #    verification run if the atomic-write primitive itself already has
    #    behavioral tests."
    #
    # It is marked STRUCTURAL in its own output line, so the distinction reaches
    # a reader scanning results rather than only one reading this comment.
    #
    # The second half of that ruling was a condition, and on 17 September it was
    # not met: write_lf_atomic had no test of any kind. The structural control
    # says every write goes through the primitive; nothing said the primitive
    # works. Two statements, and the pair is only worth something with both. The
    # behavioural controls for it are immediately below.
    _rr = (SRC / "run_review.py").read_text(encoding="utf-8")
    _logw = [(i, l.strip()) for i, l in enumerate(_rr.splitlines(), 1)
             if "capture-log.json" in l and "write_lf" in l]
    _plain = [(i, l) for i, l in _logw if "write_lf_atomic" not in l]
    if not _logw:
        failures.append("no capture-log write was found in the runner at all, "
                        "so this control is checking nothing")
    elif _plain:
        failures.append(
            "capture-log.json is written non-atomically at:\n      "
            + "\n      ".join(f"line {i}: {l}" for i, l in _plain) +
            "\n      An interruption there truncates the pointer naming which "
            "generation governs,\n      and the atomic commit point below it "
            "cannot undo that. B02-F04.")
    else:
        print(f"  [ok] STRUCTURAL: all {len(_logw)} capture-log writes go through the "
              f"atomic path")

    # ---- BEHAVIOURAL: the atomic primitive itself ----
    # The condition attached to accepting the structural control above. These
    # exercise write_lf_atomic directly rather than through the runner, which is
    # what makes fault injection possible here and impossible there: the
    # primitive is a function this suite can call, so a failure can be put
    # inside it at the exact instant that matters.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_rr_probe", SRC / "run_review.py")
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    _atomic_dir = Path(tempfile.mkdtemp())
    _target = _atomic_dir / "capture-log.json"

    # 1. It writes, and with LF endings, which is the other half of the name.
    _mod.write_lf_atomic(_target, '{"authoritative": 1}\n')
    if _target.read_bytes() != b'{"authoritative": 1}\n':
        failures.append("write_lf_atomic did not write the content it was given, "
                        f"got {_target.read_bytes()!r}")
    else:
        print("  [ok] BEHAVIOURAL: the atomic write writes, with LF endings")

    # 2. A failure partway through leaves the PREVIOUS generation readable and
    #    complete. This is the actual B02-F04 property, and until now nothing
    #    tested it: the old control proved the call site, not the guarantee.
    _orig_write = _mod.write_lf

    def _die_mid_write(p, text):
        # Stage a truncated file exactly as a half-completed write would, then
        # fail before the rename can commit it.
        _orig_write(p, text[:len(text) // 2])
        raise OSError("disk full, halfway through")

    _mod.write_lf = _die_mid_write
    try:
        _mod.write_lf_atomic(_target, '{"authoritative": 2}\n')
    except OSError:
        pass
    finally:
        _mod.write_lf = _orig_write

    _survived = _target.read_bytes()
    _staged_left = sorted(_atomic_dir.glob(".*.staged"))
    if _survived != b'{"authoritative": 1}\n':
        failures.append(
            "a write that failed partway through changed the file it was "
            f"replacing. It now reads {_survived!r}. The previous generation "
            "must survive whole: that is the entire property B02-F04 asked for, "
            "and a rename that does not provide it is not a commit point.")
    elif _staged_left:
        failures.append(
            f"a failed write left staging files behind: "
            f"{[p.name for p in _staged_left]}. They are not the authoritative "
            "name so nothing reads them as governing, but they accumulate and "
            "the next reader has to know which names to ignore.")
    else:
        print("  [ok] BEHAVIOURAL: a write that dies partway leaves the "
              "previous generation whole")

    # 3. The replacement is all-or-nothing on success too: no window where the
    #    target exists but is short. Checked by staging under a name the reader
    #    of the real file would never pick up.
    _mod.write_lf_atomic(_target, '{"authoritative": 3}\n')
    if _target.read_bytes() != b'{"authoritative": 3}\n':
        failures.append("the atomic write did not replace the previous "
                        "generation on success")
    elif sorted(_atomic_dir.glob(".*.staged")):
        failures.append("a successful atomic write left its staging file in "
                        "place, so the directory grows one file per write")
    else:
        print("  [ok] BEHAVIOURAL: a successful atomic write replaces "
              "completely and cleans up")
    shutil.rmtree(_atomic_dir, ignore_errors=True)

    # ---- B02-F04: interruption at the publication boundary ----
    # Cycle 03: "the required transactional supersession is not implemented. A
    # partial replacement still leaves the authoritative representation
    # internally inconsistent." Codex injected a failure between the two
    # renames and got a cycle whose raw capture was new and whose findings were
    # old, with the designation still on the previous attempt.
    #
    # There is now one commit point, the rename of capture-log.json, and
    # everything at the top of the cycle is published from whatever it
    # designates. These two controls are the two sides of that line.
    _log = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
    _n = _log["authoritative"]
    _gen = cyc / "captures" / f"attempt-{_n:02d}"

    if not (_gen / "findings.json").is_file():
        failures.append(
            "the designated attempt carries no findings.json, so the generation "
            "is not self-contained and there is nothing to republish from")
    else:
        print("  [ok] the designated attempt holds its own findings, not just "
              "raw bytes")

        # After the commit, before publication. The log designates the new
        # generation; the working copies are still the old one. This is exactly
        # the state Codex produced, and it must heal deterministically rather
        # than needing a human.
        _stale = "stale contents from a generation that no longer governs\n"
        write_lf(cyc / "codex-output-raw.md", _stale)
        write_lf(cyc / "findings.json", '{"schema": "cycle-findings/1"}\n')

        # Recording without --supersede-capture, which this cycle refuses. The
        # point is that recovery happens BEFORE the refusal: even a command that
        # is turned away must not leave a half-published cycle sitting there.
        _rec = runner(t16, "record", "--cycle", str(cyc), "--output", "other.md",
                      "--invocation", "manual")
        _out = _rec.stdout + _rec.stderr
        if "recovered" not in _out:
            failures.append(
                "a half-published cycle was not recovered, or the recovery was "
                f"silent. A repair nobody can see is not auditable:\n{_out[:300]}")
        elif _rec.returncode == 0:
            failures.append("recording without --supersede-capture was accepted "
                            "on a cycle that already has a designated capture")
        else:
            print("  [ok] a half-published cycle is recovered even by a command "
                  "that is then refused")

        def _h(p: Path) -> str:
            return hashlib.sha256(p.read_bytes()).hexdigest()

        # Read back from disk rather than trusting the command's account of
        # itself. The cycle must now be whole: working copies equal to the
        # generation the log designates.
        _log2 = json.loads((cyc / "capture-log.json").read_text(encoding="utf-8"))
        _g2 = cyc / "captures" / f"attempt-{_log2['authoritative']:02d}"
        if (_h(cyc / "codex-output-raw.md") != _h(_g2 / "raw.md")
                or _h(cyc / "findings.json") != _h(_g2 / "findings.json")):
            failures.append(
                "the cycle's working copies do not match the generation the "
                "capture log designates. That is the mixed state B02-F04 is "
                "about, still reachable.")
        else:
            print("  [ok] the working copies match the designated generation")

    # ---- B02-F01 and B02-F02: the parser reads what the prompt asks for ----
    # Two defects found by cycle 02, in the module that exists to stop the
    # prompt, the parser and the ledger from disagreeing.
    print()
    print("recurrence blocks, and blocks the strict parser cannot see")

    import importlib.util as _iu
    _sp = _iu.spec_from_file_location("_ff", SRC / "findings_format.py")
    _ff = _iu.module_from_spec(_sp); _sp.loader.exec_module(_ff)

    def parses(label: str, body: str, want_ids, want_kinds=None) -> None:
        got, probs = _ff.extract(body)
        if probs:
            failures.append(f"{label}: unexpected problems {probs}")
            return
        if [g["id"] for g in got] != list(want_ids):
            failures.append(f"{label}: got {[g['id'] for g in got]}, "
                            f"wanted {list(want_ids)}")
            return
        if want_kinds and [g.get("kind") for g in got] != list(want_kinds):
            failures.append(f"{label}: kinds {[g.get('kind') for g in got]}")
            return
        print(f"  [ok] parsed: {label}")

    def refuses(label: str, body: str, needle: str) -> None:
        got, probs = _ff.extract(body)
        if not probs:
            failures.append(f"{label}: parsed cleanly, expected a problem "
                            f"(got {[g['id'] for g in got]})")
        elif not any(needle.lower() in p.lower() for p in probs):
            failures.append(f"{label}: wrong problem\n  wanted {needle!r}\n"
                            f"  got {probs}")
        else:
            print(f"  [ok] refused: {label}")

    NEW = "Finding ID: B02-F01\nClass: UNTESTED RULE\nEvidence: x\n"
    REC = ("Finding ID: B01-F11\nStatus: REPAIR NOT DEMONSTRATED\n"
           "Evidence: x\nFinding: y\nRequired correction: z\n")

    parses("a new finding", NEW, ["B02-F01"], ["finding"])
    parses("a recurrence with no Class line", REC, ["B01-F11"], ["recurrence"])
    parses("a review mixing both forms", NEW + "\n" + REC,
           ["B02-F01", "B01-F11"], ["finding", "recurrence"])

    refuses("a block carrying both Class and Status",
            "Finding ID: B02-F01\nClass: UNTESTED RULE\n"
            "Status: REPAIR NOT DEMONSTRATED\nEvidence: x\n",
            "either a new finding")
    refuses("a block with neither Class nor Status",
            "Finding ID: B02-F01\nEvidence: x\n", "neither a Class")
    refuses("an unrecognised Status",
            "Finding ID: B01-F11\nStatus: LOOKS FINE TO ME\nEvidence: x\n",
            "not recognised")

    # B02-F01 proper. Codex's reproduction: one canonical block, one indented by
    # a single space. Before the repair this returned one identifier and an
    # empty problems list, because the signal net only ran when nothing parsed.
    refuses("a second block indented by one space",
            NEW + "\n Finding ID: B02-F02\nClass: UNTESTED RULE\nEvidence: y\n",
            "apparent finding block")
    # Caught by the SIGNALS net rather than by the loose-header comparison: when
    # the indented block is the only one, nothing parses at all. Verified by
    # mutation — with the loose comparison disabled this control still passes,
    # so it is evidence about the signal net and is labelled as such. Left in
    # because two independent mechanisms covering the case is worth recording,
    # and a control named for the wrong mechanism is worth not having.
    refuses("a review whose only block is indented, caught by the signal net",
            " Finding ID: B02-F01\nClass: UNTESTED RULE\nEvidence: x\n",
            "signals that one is present")

    # D02-F01, BOOTSTRAP-003 cycle 02. The signal net treated any canonical
    # identifier anywhere as evidence of a block the parser had missed, so a
    # review assessing an earlier repair and reporting nothing new could not be
    # recorded at all. The cycle 02 prompt asked for exactly that reply.
    #
    # The positive comes first because it is the one that was broken, and the
    # three refusals after it are what stop the repair from becoming "mentioning
    # an identifier is always fine".
    parses("a zero-finding review that names a demonstrated repair",
           "The repair to D01-F01 is demonstrated. No new findings.\n", [])
    parses("the same naming several earlier findings",
           "D01-F01 and C02-F08 are both demonstrated; C03-F02 holds.\n"
           "This review makes no claim of convergence.\n", [])
    # And the net still does its job: an identifier with a declaration attached
    # is a block the parser failed to read, whichever line the declaration is
    # on. Without these the repair above would have switched the net off for
    # every malformed block that happens to lack a usable header.
    refuses("an identifier with a Class line below it, header malformed",
            "Finding-ID D02-F09\nClass: UNTESTED RULE\nEvidence: x\n",
            "signals that one is present")
    refuses("an identifier with a Status line below it, header malformed",
            "Finding_ID D02-F09\nStatus: REPAIR NOT DEMONSTRATED\n"
            "Evidence: x\n",
            "signals that one is present")
    refuses("an identifier and its class on one line",
            "D02-F09 Class: UNTESTED RULE and here is why\n",
            "signals that one is present")

    # D02-F01, second pass. BOOTSTRAP-003 cycle 03: the net ran only when
    # nothing parsed, so a malformed declaration beside a valid finding was
    # invisible. His reproduction, rebuilt: one canonical block, then one whose
    # header the strict parser cannot see.
    refuses("a malformed declaration beside a finding that parses",
            NEW + "\nFinding-ID B02-F09\nClass: UNTESTED RULE\n"
            "Evidence: second defect\n",
            "declaration(s) the parser could not read")
    refuses("the same with a Status line",
            NEW + "\nFinding_ID B01-F11\nStatus: REPAIR NOT DEMONSTRATED\n"
            "Evidence: second defect\n",
            "declaration(s) the parser could not read")

    # D02-F01, third pass, and the case the first two repairs both missed.
    # BOOTSTRAP-003 cycle 04: the reconciliation compared a SET of declared
    # identifiers against a SET of parsed ones, so two declarations carrying
    # the SAME identifier collapsed to one element on each side and the
    # difference was empty. One canonical block, one malformed block wearing
    # its identifier and describing something else entirely, and the second
    # vanished with no problem reported. The duplicate check elsewhere cannot
    # see it either, because that looks only at what parsed.
    #
    # The two controls above would both have passed on the broken code, which
    # is the point: each was built from the example the reviewer showed, and
    # the rule underneath them was wrong all three times.
    refuses("a malformed duplicate of an identifier that also parses",
            NEW + "\nFinding-ID B02-F01\nClass: WRONG OWNERSHIP\n"
            "Evidence: a different defect carrying the same identifier\n",
            "declaration(s) the parser could not read")
    # And the count is shown, because "B02-F01" alone would not tell a reader
    # which of the two blocks went missing or that there were two at all.
    refuses("the refusal says how many were declared and how many parsed",
            NEW + "\nFinding-ID B02-F01\nClass: WRONG OWNERSHIP\n"
            "Evidence: a different defect carrying the same identifier\n",
            "declared 2, parsed 1")

    # Alex Zamurko, 11 October: "verify individual declaration occurrences,
    # not just matching counts, which can conceal errors."
    #
    # A fair worry, and the four below are where matching counts could hide
    # something. Two of them pass through this check untouched and are caught
    # by the duplicate rule instead, which is the honest answer: counting
    # alone does not establish correspondence, and it is not asked to. The
    # pair of rules together is what does, and these say which rule catches
    # which case rather than leaving a reader to assume one of them covers
    # everything.
    refuses("two canonical blocks sharing an identifier are a duplicate",
            NEW + "\nFinding ID: B02-F01\nClass: WRONG OWNERSHIP\n"
            "Requirement ID: x\nEvidence: second\nFinding: second\n"
            "Required correction: second\n",
            "duplicate finding identifiers")
    refuses("neither of two declarations parsing is still reported",
            "Finding-ID B02-F01\nClass: UNTESTED RULE\nEvidence: first\n\n"
            "Finding_ID B02-F01\nStatus: REPAIR NOT DEMONSTRATED\n"
            "Evidence: second\n",
            "declared 2, parsed 0")
    refuses("a malformed duplicate hides among several sound findings",
            NEW + "\n" + NEW.replace("B02-F01", "B02-F02") +
            "\nFinding-ID B02-F01\nClass: WRONG OWNERSHIP\n"
            "Evidence: wearing the first one's identifier\n",
            "B02-F01 (declared 2, parsed 1)")
    # And the counting rule must not fire on a review that is simply correct,
    # or it would refuse everything and the controls above would prove
    # nothing about it.
    parses("two sound findings with different identifiers are untouched",
           NEW + "\n" + NEW.replace("B02-F01", "B02-F02"),
           ["B02-F01", "B02-F02"], ["finding", "finding"])

    # And the defect that arrived inside cycle 03's own review: its evidence
    # quoted a specimen finding block in a code fence, the parser read the
    # specimen as a declaration, and the capture recorded a finding the
    # reviewer never raised.
    parses("a finding block quoted inside a code fence is not a declaration",
           NEW + "\nFor example, a review might contain:\n\n"
           "```\nFinding ID: B03-F90\nClass: UNTESTED RULE\n"
           "Evidence: illustrative only\n```\n",
           ["B02-F01"], ["finding"])
    parses("a tilde fence too, and a zero-finding review around it",
           "No new findings. For illustration only:\n\n"
           "~~~\nFinding ID: B03-F91\nStatus: REPAIR NOT DEMONSTRATED\n~~~\n",
           [])
    # A review whose only blocks are fenced parses to nothing, deliberately.
    # A guard against that was written and removed the same hour: it fired on
    # the control above, a zero-finding review quoting an example, which is the
    # exact shape this repair exists to accept. The risk is left to the
    # explicit --zero-findings step instead, and this control pins the
    # behaviour so the trade is visible rather than assumed.
    parses("a review whose only finding blocks are fenced parses to nothing",
           "Here is my review.\n\n```\nFinding ID: B03-F92\n"
           "Class: UNTESTED RULE\nEvidence: x\n```\n",
           [])

    # And the class really does come from the ledger, not from the review.
    tf = make_repo(); made.append(tf)
    do_init(tf); do_freeze(tf)
    sh(sys.executable, str(tf / "scripts" / "ledger.py"), "raise",
       "--review", "runs/T-001/plan-review", "--cycle", "1", "--id", "C01-F01",
       "--class", "WRONG OWNERSHIP", "--source", "CODEX_REVIEW", cwd=tf)
    write_lf(tf / "rec.md", with_target(tf, "Finding ID: C01-F01\n"
                                            "Status: REPAIR NOT DEMONSTRATED\n"
                                            "Evidence: x\nFinding: y\n"
                                            "Required correction: z\n"))
    r = runner(tf, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
               "--output", "rec.md", "--invocation", "manual")
    if r.returncode != 0:
        failures.append(f"a recurrence was refused:\n{r.stdout}{r.stderr}")
    else:
        fj = json.loads((tf / "runs/T-001/plan-review/cycle-01/findings.json")
                        .read_text(encoding="utf-8"))
        rec0 = fj["findings"][0]
        if rec0.get("class") != "WRONG OWNERSHIP":
            failures.append(f"the recurrence class was not resolved from the "
                            f"ledger: {rec0}")
        elif rec0.get("kind") != "recurrence":
            failures.append(f"the recurrence was not marked as one: {rec0}")
        else:
            print("  [ok] a recurrence takes its class from the ledger, not the "
                  "review")

    tu = make_repo(); made.append(tu)
    do_init(tu); do_freeze(tu)
    write_lf(tu / "rec.md", with_target(tu, "Finding ID: C01-F09\n"
                                            "Status: REPAIR NOT DEMONSTRATED\n"
                                            "Evidence: x\n"))
    r = runner(tu, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
               "--output", "rec.md", "--invocation", "manual")
    if r.returncode == 0:
        failures.append("a recurrence was recorded for an identifier the ledger "
                        "has never seen")
    elif "never" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the unknown identifier\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: a recurrence for an identifier never raised")

    # ---- run-pin and review-target separation, 10 September ----
    # "No review process may require an artifact to remain byte-invariant for
    # the duration of a run while simultaneously requiring that same artifact
    # version to change in order to resolve review findings."
    #
    # BOOTSTRAP-001 required exactly that and deadlocked between cycles 01 and
    # 02. Nothing compared the pin set against the target list, so the
    # contradiction was only discoverable by hitting it.
    print()
    print("run pins and review targets are disjoint")

    tp = make_repo(); made.append(tp)
    do_init(tp)
    # Freeze a cycle whose review target IS the run's pinned spec.
    r = runner(tp, "freeze", "--run", "T-001", "--type", "plan",
               "--prompt", "specs/prompt.md", "--file", "specs/spec.md")
    if r.returncode == 0:
        failures.append("a cycle was frozen with the run's pinned spec as its "
                        "own review target; the governing invariant is not "
                        "enforced")
    elif "exactly one role" not in (r.stdout + r.stderr):
        failures.append(f"freeze refused, but not for the separation rule\n"
                        f"{r.stdout}{r.stderr}")
    elif (tp / "runs/T-001/plan-review/cycle-01").exists():
        failures.append("freeze refused but left a cycle directory behind")
    else:
        print("  [ok] refused: an artifact that is both a run pin and a review "
              "target")

    # The ordinary case still works, or the check above is just breaking freeze.
    if do_freeze(tp).returncode != 0:
        failures.append("freeze of an ordinary cycle was refused by the "
                        "separation check")
    else:
        print("  [ok] a cycle whose target is not a pinned artifact still freezes")

    # ---- the amendment history ----
    def amend(root: Path, **over) -> None:
        rec = {
            "effective_cycle": 2,
            "reason": "the pinned spec is also a review target, which the "
                      "separation specification forbids",
            "affected_artifacts": ["specs/spec.md"],
            "prior_pin_set": ["specs/protocol.md", "specs/spec.md"],
            "new_pin_set": ["specs/protocol.md"],
            "authorized_by": "Alex Zamurko",
            "at": "2026-09-10T00:00:00Z",
        }
        rec.update(over)
        write_lf(root / "runs" / "T-001" / "pin-amendments.json", json.dumps({
            "schema": "run-pin-amendments/1", "amendments": [rec]}, indent=2) + "\n")

    def amend_refuses(label: str, needle: str, **over) -> None:
        # These refuse inside check_pins_still_hold, before the loop controller
        # is consulted, so cycle 01 does not need closing here. The control
        # asserts the amendment chain is rejected, and the message it matches on
        # says which rule rejected it.
        root = make_repo(); made.append(root)
        do_init(root); do_freeze(root)
        amend(root, **over)
        rr = do_freeze(root)
        if rr.returncode == 0:
            failures.append(f"{label}: accepted")
        elif needle.lower() not in (rr.stdout + rr.stderr).lower():
            failures.append(f"{label}: refused for the wrong reason\n"
                            f"  wanted {needle!r}\n"
                            f"  got {(rr.stderr + rr.stdout)[:300]}")
        else:
            print(f"  [ok] refused: {label}")

    amend_refuses("an amendment that starts from a pin set that never existed",
                  "does not follow the pin history",
                  prior_pin_set=["specs/protocol.md"])

    # ---- B02-F05: amendments are constrained by role ----
    # "The governing protocol cannot be removed; added pins must be validated."
    # The first version accepted any structurally valid edit, so an inconvenient
    # mandatory pin could simply be dropped and a new one declared without ever
    # being checked.
    amend_refuses("an amendment that removes the governing protocol",
                  "removes the governing protocol",
                  affected_artifacts=["specs/protocol.md"],
                  new_pin_set=["specs/spec.md"])

    # The half cycle 03 found still open. Removing the protocol path was
    # refused; changing the protocol's BYTES through the added-hash map was not.
    # added_pin_hashes was validated for the paths being added and then applied
    # wholesale, so this amendment declares only specs/extra.md, keeps every
    # existing path, and replaces the governing protocol's hash on the way
    # through. Codex reproduced it against the real functions.
    # Written out rather than going through amend_refuses, because the amendment
    # has to be legitimate in every other respect. specs/extra.md must exist and
    # hash correctly, or the freeze refuses on a missing governing pin and the
    # control passes without ever reaching the defect. The first version of this
    # control did exactly that, and the mutation probe is what exposed it.
    tP = make_repo(); made.append(tP)
    write_lf(tP / "specs" / "extra.md", "# extra\n\nan added governing spec\n")
    sh("git", "add", "-A", cwd=tP)
    sh("git", "commit", "-qm", "extra", cwd=tP)
    do_init(tP); do_freeze(tP)

    # Cycle 01 has to be genuinely closed. amend_refuses gets away without this
    # because its amendments fail inside check_pins_still_hold, which runs
    # first. This one is meant to REACH the pin machinery and be accepted by it
    # when the repair is absent, so anything refusing later would mask the
    # result: the mutation probe showed the freeze failing on an unrecorded
    # cycle 01 and the control reporting "wrong reason" when the truth was that
    # the override had been accepted.
    write_lf(tP / "replyP.md",
             reply_for(tP, "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                           "Evidence: x\n"))
    _rp0 = runner(tP, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
                  "--output", "replyP.md", "--invocation", "manual")
    if _rp0.returncode != 0:
        failures.append(f"fixture: could not close cycle 01 for the retained-pin "
                        f"control\n{_rp0.stderr}{_rp0.stdout}")
    _lp0 = sh(sys.executable, str(tP / "scripts" / "ledger.py"), "raise",
              "--review", "runs/T-001/plan-review", "--cycle", "1",
              "--id", "C01-F01", "--class", "UNTESTED RULE",
              "--source", "CODEX_REVIEW", cwd=tP)
    if _lp0.returncode != 0:
        failures.append(f"fixture: could not raise the finding\n{_lp0.stderr}{_lp0.stdout}")

    _xh = hashlib.sha256((tP / "specs" / "extra.md").read_bytes()).hexdigest()
    amend(tP,
          affected_artifacts=["specs/extra.md"],
          new_pin_set=["specs/protocol.md", "specs/spec.md", "specs/extra.md"],
          added_pin_hashes={"specs/extra.md": _xh,
                            "specs/protocol.md": "b" * 64})
    _rp = do_freeze(tP)
    _out = (_rp.stdout + _rp.stderr).lower()
    if _rp.returncode == 0:
        failures.append(
            "an amendment declaring only specs/extra.md replaced the governing "
            "protocol's hash and was accepted. Keeping the protocol's path is "
            "not keeping its version, which is B02-F05 unrepaired.")
    elif "does not add" not in _out:
        failures.append(
            "an amendment that rewrites a retained pin's hash: refused for the "
            f"wrong reason\n      wanted 'does not add'\n      got "
            f"{(_rp.stderr + _rp.stdout)[:200]}")
    else:
        print("  [ok] refused: an amendment that rewrites a retained pin's hash")
    # What this does NOT cover, stated rather than left to be assumed: the
    # repair has a second half, a filter in pin_hashes_for_cycle that applies
    # only an amendment's own additions even when validate_chain has not run.
    # This control reaches that function through the runner, which always
    # validates first, so the filter is never the thing refusing here. It is
    # defence for callers that skip validation, and it has no control of its
    # own. Claiming otherwise would be the defect this finding is about.

    # ---- B01-F04: an added spec reaches the reviewer, not just the target ----
    # compose_input built the embedded specs from run["spec_files"], the set as
    # it stood at init, filtered through the cycle's governing set. Filtering a
    # stale list can only remove entries, never add them, so a spec introduced
    # by amendment was in governing_pins, was hashed into the target, and was
    # never given to the reviewer. Codex reproduced it end to end.
    #
    # The drift half of Codex's requested pair already exists above, as
    # "an artifact added by amendment is checked like any other governing pin".
    # This is the successful-addition half it asked for alongside it.
    print()
    print("a spec added by amendment is embedded, not only hashed (B01-F04)")

    tS = make_repo(); made.append(tS)
    UNIQUE = "GOVERNING-RULE-ADDED-BY-AMENDMENT-9F2A"
    write_lf(tS / "specs" / "extra.md", f"# extra\n\n{UNIQUE}\n")
    sh("git", "add", "-A", cwd=tS)
    sh("git", "commit", "-qm", "extra", cwd=tS)
    do_init(tS); do_freeze(tS)

    write_lf(tS / "replyS.md",
             reply_for(tS, "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                           "Evidence: x\n"))
    _rs = runner(tS, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
                 "--output", "replyS.md", "--invocation", "manual")
    _ls = sh(sys.executable, str(tS / "scripts" / "ledger.py"), "raise",
             "--review", "runs/T-001/plan-review", "--cycle", "1",
             "--id", "C01-F01", "--class", "UNTESTED RULE",
             "--source", "CODEX_REVIEW", cwd=tS)
    if _rs.returncode != 0 or _ls.returncode != 0:
        failures.append(f"fixture: could not close cycle 01 for B01-F04\n"
                        f"{_rs.stderr}{_ls.stderr}")
    else:
        _xs = hashlib.sha256(
            (tS / "specs" / "extra.md").read_bytes()).hexdigest()
        amend(tS, affected_artifacts=["specs/extra.md"],
              new_pin_set=["specs/protocol.md", "specs/spec.md",
                           "specs/extra.md"],
              added_pin_hashes={"specs/extra.md": _xs})
        _rf2 = do_freeze(tS)
        _ci2 = tS / "runs/T-001/plan-review/cycle-02/codex-input.md"
        if _rf2.returncode != 0:
            failures.append(f"fixture: cycle 02 would not freeze with a "
                            f"legitimate added spec\n{_rf2.stderr}{_rf2.stdout}")
        elif not _ci2.is_file():
            failures.append("cycle 02 froze but wrote no codex-input.md")
        else:
            _body = _ci2.read_text(encoding="utf-8")
            _tgt2 = json.loads(
                (tS / "runs/T-001/plan-review/cycle-02/target.json")
                .read_text(encoding="utf-8"))
            if "specs/extra.md" not in _tgt2.get("governing_pins", []):
                failures.append("fixture: the amendment did not put the added "
                                "spec in the governing set, so this control "
                                "cannot show anything")
            elif UNIQUE not in _body:
                failures.append(
                    "the added spec is in governing_pins and hashed into the "
                    "target, but its text is absent from the review input. The "
                    "reviewer is asked to judge against a document it was "
                    "never given, which is B01-F04 unrepaired.")
            else:
                print("  [ok] a spec added by amendment appears in the "
                      "composed input")
    amend_refuses("an amendment adding a pin with no hash",
                  "without binding them to their bytes",
                  affected_artifacts=["specs/extra.md"],
                  new_pin_set=["specs/protocol.md", "specs/spec.md",
                               "specs/extra.md"])
    amend_refuses("an amendment adding a pin with something other than a sha256",
                  "other than a sha256",
                  affected_artifacts=["specs/extra.md"],
                  new_pin_set=["specs/protocol.md", "specs/spec.md",
                               "specs/extra.md"],
                  added_pin_hashes={"specs/extra.md": "not-a-hash"})

    # An added pin, properly bound, must then actually be checked. Codex's
    # finding was that the pin check walked run.json's original entries only,
    # so a newly declared governing artifact was never hashed at all.
    tx = make_repo(); made.append(tx)
    do_init(tx); do_freeze(tx)
    write_lf(tx / "runs/T-001/plan-review/cycle-01/codex-output-raw.md", "x\n")
    write_lf(tx / "specs" / "extra.md", "an added governing artifact\n")
    extra_hash = hashlib.sha256(
        (tx / "specs" / "extra.md").read_bytes()).hexdigest()
    amend(tx, affected_artifacts=["specs/extra.md"],
          new_pin_set=["specs/protocol.md", "specs/spec.md", "specs/extra.md"],
          added_pin_hashes={"specs/extra.md": extra_hash})
    p_extra = tx / "specs" / "extra.md"
    p_extra.write_text(p_extra.read_text(encoding="utf-8") + "edited\n",
                       encoding="utf-8")
    r = do_freeze(tx)
    if r.returncode == 0:
        failures.append("an amendment-added governing artifact was edited and "
                        "the freeze accepted it; added pins are declared but "
                        "not checked")
    elif "governing artifact changed" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the added pin's drift\n"
                        f"{r.stdout}{r.stderr}")
    else:
        print("  [ok] refused: an artifact added by amendment is checked like "
              "any other governing pin")
    amend_refuses("an amendment with nobody's name on it", "missing",
                  authorized_by="")
    amend_refuses("an amendment whose reason is a placeholder", "at least",
                  reason="because")
    amend_refuses("an amendment whose declared artifacts are not what changed",
                  "do not match what it changes",
                  affected_artifacts=["specs/protocol.md"])

    # And the amendment actually releases the pin, or the whole exercise is a
    # record of a change that did not take effect.
    # Cycle 01 is closed through the real record path rather than by writing raw
    # output by hand. A hand-written cycle has no findings.json, and the loop
    # controller then refuses to say whether another cycle is permitted, so
    # freeze would be blocked by B01-F02's check and this control would report a
    # pin failure that never happened. The finding is also raised in the ledger,
    # because the controller refuses when a recorded finding is unaccounted for,
    # and one open finding is what makes the loop CONTINUE rather than converge.
    tr = make_repo(); made.append(tr)
    do_init(tr); do_freeze(tr)
    write_lf(tr / "reply.md", with_target(tr, GOOD))
    rec = runner(tr, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
                 "--output", "reply.md", "--invocation", "manual")
    if rec.returncode != 0:
        failures.append(f"fixture: could not record cycle 01\n{rec.stdout}{rec.stderr}")
    rl = sh(sys.executable, str(tr / "scripts" / "ledger.py"), "raise",
            "--review", "runs/T-001/plan-review", "--cycle", "1",
            "--id", "C01-F01", "--class", "UNTESTED RULE",
            "--source", "CODEX_REVIEW", cwd=tr)
    if rl.returncode != 0:
        failures.append(f"fixture: could not raise the finding\n{rl.stdout}{rl.stderr}")
    spec_p = tr / "specs" / "spec.md"
    spec_p.write_text(spec_p.read_text(encoding="utf-8") + "\nrepaired\n",
                      encoding="utf-8")
    r = do_freeze(tr)
    if r.returncode == 0:
        failures.append("cycle 02 froze with the pinned spec edited and no "
                        "amendment recorded")
    elif "run pins no longer hold" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the pin drift\n{r.stdout}{r.stderr}")
    else:
        print("  [ok] editing a pinned spec still blocks the next cycle")

    amend(tr)
    r = do_freeze(tr)
    if r.returncode != 0:
        failures.append("the recorded amendment did not release the pin, so the "
                        f"loop is still deadlocked\n{r.stdout}{r.stderr}")
    elif not (tr / "runs/T-001/plan-review/cycle-02").is_dir():
        failures.append("freeze reported success but opened no cycle 02")
    else:
        print("  [ok] a recorded amendment releases the pin from cycle 02 onward")

    # ---- B02-F06: an amendment cannot rewrite a completed cycle ----
    # Codex: "An amendment appended after review can retroactively change what
    # governed an already completed cycle." The old forward-only control only
    # showed that effective_cycle=2 gave different answers for cycles 1 and 2.
    # It never appended a backdated amendment after a cycle existed.
    tb = make_repo(); made.append(tb)
    do_init(tb); do_freeze(tb)
    tgt1 = json.loads((tb / "runs/T-001/plan-review/cycle-01/target.json")
                      .read_text(encoding="utf-8"))
    if "governing_pins" not in tgt1:
        failures.append("the frozen cycle does not record what governed it, so "
                        "nothing can be checked against it")
    else:
        print(f"  [ok] a frozen cycle records its governing pin set "
              f"({len(tgt1['governing_pins'])} artifacts)")
        write_lf(tb / "runs/T-001/plan-review/cycle-01/codex-output-raw.md", "x\n")
        # Effective at cycle 1, which already exists and recorded both pins.
        amend(tb, effective_cycle=1)
        r = do_freeze(tb)
        if r.returncode == 0:
            failures.append("a backdated amendment was accepted after the cycle "
                            "it affects had already been frozen")
        elif "already happened" not in (r.stdout + r.stderr):
            failures.append(f"refused, but not for the retroactive change\n"
                            f"{r.stdout}{r.stderr}")
        else:
            print("  [ok] refused: an amendment that would change what a "
                  "completed cycle ran under")

    # Cycle 01 must still be checked against what it was conducted under. An
    # amendment that reached backwards would rewrite the conditions of a review
    # that already happened.
    import importlib.util as _ilu
    _s = _ilu.spec_from_file_location("_rp", tr / "scripts" / "run_pins.py")
    _m = _ilu.module_from_spec(_s); _s.loader.exec_module(_m)
    run_obj = json.loads((tr / "runs/T-001/run.json").read_text(encoding="utf-8"))
    items = _m.load_amendments(tr / "runs" / "T-001")
    at1 = _m.pins_for_cycle(run_obj, items, 1)
    at2 = _m.pins_for_cycle(run_obj, items, 2)
    if "specs/spec.md" not in at1:
        failures.append("the amendment reached back into cycle 01, rewriting the "
                        f"conditions of a review that already happened: {at1}")
    elif "specs/spec.md" in at2:
        failures.append(f"the amendment did not take effect at cycle 02: {at2}")
    else:
        print("  [ok] the amendment applies forward only; cycle 01 keeps its own "
              "pins")

    # ---- B02-F06, the half cycle 03 found still open: the other loop ----
    # The check took a single review directory and freeze handed it the one it
    # was working in, while the amendment history belongs to the whole run.
    # Codex froze a plan cycle under protocol plus spec, backdated an amendment
    # to cycle 1 removing the spec, froze the implementation cycle, and the
    # implementation freeze exited 0. The plan cycle's record was never read.
    tx = make_repo(); made.append(tx)
    do_init(tx); do_freeze(tx)
    amend(tx, effective_cycle=1)
    r = runner(tx, "freeze", "--run", "T-001", "--type", "implementation",
               "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
    blob = r.stdout + r.stderr
    if r.returncode == 0:
        failures.append("the implementation loop froze against an amendment "
                        "backdated past a completed plan cycle; the other "
                        "review directory was never examined")
    elif "plan-review/cycle-01" not in blob:
        failures.append("the implementation freeze refused, but not for the "
                        f"plan cycle its history contradicts\n{blob[:300]}")
    else:
        print("  [ok] refused: one loop freezing against history that "
              "contradicts the other loop's completed cycle")

    # The other half: same paths, different bytes. frozen_assignments kept only
    # governing_pins and the comparison dropped governing_pin_hashes, so a
    # changed digest with unchanged membership was invisible. run.json is an
    # ordinary file under CONVENTION_ONLY; editing the version it records for a
    # retained pin changes what replay says governed cycle 01 without changing
    # which paths did.
    th = make_repo(); made.append(th)
    do_init(th); do_freeze(th)
    rp = th / "runs" / "T-001" / "run.json"
    run_h = json.loads(rp.read_text(encoding="utf-8"))
    tgt_h = json.loads((th / "runs/T-001/plan-review/cycle-01/target.json")
                       .read_text(encoding="utf-8"))
    if "governing_pin_hashes" not in tgt_h:
        failures.append("the frozen cycle records its governing paths but not "
                        "their versions, so nothing can be compared against")
    else:
        run_h["spec_files"][0]["sha256"] = "b" * 64
        write_lf(rp, json.dumps(run_h, indent=2) + "\n")
        r = do_freeze(th)
        blob = r.stdout + r.stderr
        if r.returncode == 0:
            failures.append("a governing artifact's recorded version changed "
                            "under a completed cycle and freeze accepted it; "
                            "only the path list was compared")
        elif "governing paths but not its versions" not in blob:
            failures.append("refused, but not for the version change; the "
                            f"membership check is doing the work\n{blob[:300]}")
        else:
            print("  [ok] refused: same governing paths under a completed "
                  "cycle, different versions")

    # ---- B01-F08: the gate must hold at freeze, not only at init ----
    # A run can sit for days between init and its first cycle, and every cycle is
    # where the tooling is actually relied upon. Checking only at init let a
    # component change in between and a cycle freeze against tooling whose
    # approval no longer covered it.
    t4 = make_repo(); made.append(t4)
    if approve_bootstrap(t4).returncode != 0 or real_init(t4).returncode != 0:
        failures.append("could not reach an approved real run for the freeze-time "
                        "bootstrap control")
    else:
        vc = t4 / "scripts" / "validate_cycle.py"
        vc.write_text(vc.read_text(encoding="utf-8") + "\n# edited after init\n",
                      encoding="utf-8")
        r = runner(t4, "freeze", "--run", "A1E-001", "--type", "plan",
                   "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
        blob = (r.stdout + r.stderr).lower()
        if r.returncode == 0:
            failures.append("a cycle froze against tooling whose bootstrap "
                            "approval no longer covers it; the gate was checked "
                            "at init and never again")
        elif "no longer holds" not in blob:
            failures.append("freeze refused after the component changed, but not "
                            f"on the bootstrap gate:\n  {blob.strip()[:220]}")
        else:
            print("  [ok] refused: freezing a cycle after a covered component changed")

    # An exempt run must stay exempt at freeze too, or development evidence
    # becomes impossible to produce the moment any component is edited.
    t5 = make_repo(); made.append(t5)
    do_init(t5)
    vc = t5 / "scripts" / "validate_cycle.py"
    vc.write_text(vc.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    if do_freeze(t5).returncode != 0:
        failures.append("an exempt run was blocked by the bootstrap gate at "
                        "freeze; exempt means exempt at every step or the flag "
                        "does not do what it says")
    else:
        print("  [ok] an exempt run still freezes after a component changes")

    # And the exempt path must label itself, or it is a silent bypass.
    t3 = make_repo(); made.append(t3)
    do_init(t3)
    exempt = json.loads((t3 / "runs" / "T-001" / "run.json").read_text(encoding="utf-8"))
    if "NOT_A_PROTOCOL_CYCLE" not in exempt.get("bootstrap_review", ""):
        failures.append("--bootstrap-exempt does not label the run as development "
                        "evidence, so an exempt run and a real one are "
                        "indistinguishable in the record")
    else:
        print("  [ok] --bootstrap-exempt labels the run NOT_A_PROTOCOL_CYCLE")

    # ---- B01-F14: a run unfit to be concluded cannot be concluded ----
    # The runner refused a missing or unrecognised mc1_enforcement at freeze.
    # The controller read the same run.json for its own purposes and asked
    # nothing about it, so a protocol run could lose the field after freezing
    # and still be handed an unqualified LOOP_STATUS. Codex reproduced exactly
    # that and got "CONVERGED".
    #
    # A real run, not an exempt one: the finding is about authoritative outcomes,
    # and a development run's outcome already says it is not one.
    print()
    print("a protocol run must be fit to be concluded (B01-F14)")

    tM = make_repo(); made.append(tM)
    if approve_bootstrap(tM).returncode != 0:
        failures.append("fixture: could not approve the bootstrap for B01-F14")
    else:
        _ri = runner(tM, "init", "--run", "A1E-001", "--protocol",
                     "specs/protocol.md", "--spec", "specs/spec.md")
        _rf = runner(tM, "freeze", "--run", "A1E-001", "--type", "plan",
                     "--prompt", "specs/prompt.md", "--file", "plan/01-PLAN.md")
        revM = tM / "runs" / "A1E-001" / "plan-review"
        cM = revM / "cycle-01"
        if _ri.returncode != 0 or _rf.returncode != 0:
            failures.append(f"fixture: could not open a protocol cycle\n"
                            f"{_ri.stderr}{_rf.stderr}")
        else:
            thM = (cM / "target.sha256").read_text(encoding="utf-8").strip()
            write_lf(tM / "replyM.md",
                     f"TARGET_SHA256 {thM}\n\nNo findings in any category.\n")
            _rr = runner(tM, "record", "--cycle",
                         "runs/A1E-001/plan-review/cycle-01",
                         "--output", "replyM.md", "--invocation", "manual",
                         "--zero-findings")
            if _rr.returncode != 0:
                failures.append(f"fixture: could not record the protocol cycle\n"
                                f"{_rr.stderr}{_rr.stdout}")

            def controller(t: Path) -> subprocess.CompletedProcess:
                return sh(sys.executable, str(t / "scripts" / "loop_state.py"),
                          "--review", "runs/A1E-001/plan-review", "--quiet",
                          cwd=t)

            # The baseline. Without it the refusals below could be refusing for
            # any reason at all and the control would still look green.
            _b = controller(tM)
            if _b.returncode != 0 or "LOOP_STATUS" not in _b.stdout:
                failures.append(f"fixture: a healthy protocol run produced no "
                                f"loop status, so the refusals below establish "
                                f"nothing\n{_b.stderr}{_b.stdout}")
            else:
                print("  [ok] a protocol run recording its enforcement status "
                      "is concluded normally")

            rj = tM / "runs" / "A1E-001" / "run.json"
            healthy_run = rj.read_text(encoding="utf-8")

            # The third case is B01-F14's remaining half, found by cycle 04.
            # Removing the field refused; removing the whole file exited 0 with
            # an unqualified CONVERGED, because a missing run.json returned
            # classification UNKNOWN before the metadata check was reached.
            #
            # The two field controls sat here on their own and looked like
            # coverage. They tested the careful mistake and not the careless
            # one, which is the shape cycle 04 found in all five of its
            # findings. The deletion case belongs beside them, not in a file of
            # its own where nobody compares the two.
            def _lost() -> None:
                d = json.loads(healthy_run)
                d.pop("mc1_enforcement", None)
                write_lf(rj, json.dumps(d, indent=2) + "\n")

            def _nonsense() -> None:
                d = json.loads(healthy_run)
                d["mc1_enforcement"] = "FULLY_ENFORCED"
                write_lf(rj, json.dumps(d, indent=2) + "\n")

            def _gone() -> None:
                rj.unlink()

            for label, break_it, needle in (
                ("a protocol run that has lost its enforcement status",
                 _lost, "mc1_enforcement"),
                ("a protocol run claiming an enforcement status that means "
                 "nothing", _nonsense, "mc1_enforcement"),
                ("a run whose whole metadata record is gone",
                 _gone, "run.json"),
            ):
                break_it()
                res = controller(tM)
                out = res.stdout + res.stderr
                if res.returncode == 0:
                    failures.append(f"the controller concluded {label}")
                elif "LOOP_STATUS" in res.stdout:
                    failures.append(
                        f"the controller refused {label} but still printed a "
                        f"LOOP_STATUS line, which is the thing callers read\n"
                        f"      {res.stdout.strip()[:160]}")
                elif needle not in out:
                    failures.append(f"refused {label}, but not for that reason\n"
                                    f"      {out.strip()[:160]}")
                else:
                    print(f"  [ok] refused: {label}")

            write_lf(rj, healthy_run)

    # ---- B03-F01: nothing but a completed CONTINUE is permission ----
    # The check tested for controller exit code 2 and the four terminal
    # statuses, and permitted everything else. The replay added for B01-F11
    # raises UnknownEvent; loop_state caught only CannotCalculate; so an
    # unrecognised event exited 1 with a traceback and no LOOP_STATUS, and the
    # empty status fell straight through to permission. Codex reproduced it and
    # opened cycle-02 on a controller that had crashed.
    print()
    print("an undeterminable loop state is not permission (B03-F01)")

    tB = make_repo(); made.append(tB)
    do_init(tB); do_freeze(tB)
    write_lf(tB / "replyB.md",
             reply_for(tB, "Finding ID: C01-F01\nClass: UNTESTED RULE\n"
                           "Evidence: x\n"))
    _rb = runner(tB, "record", "--cycle", "runs/T-001/plan-review/cycle-01",
                 "--output", "replyB.md", "--invocation", "manual")
    if _rb.returncode != 0:
        failures.append(f"fixture: could not record cycle 01\n{_rb.stderr}{_rb.stdout}")
    _lb = sh(sys.executable, str(tB / "scripts" / "ledger.py"), "raise",
             "--review", "runs/T-001/plan-review", "--cycle", "1",
             "--id", "C01-F01", "--class", "UNTESTED RULE",
             "--source", "CODEX_REVIEW", cwd=tB)
    if _lb.returncode != 0:
        failures.append(f"fixture: could not raise the finding\n{_lb.stderr}{_lb.stdout}")

    cyc2 = tB / "runs" / "T-001" / "plan-review" / "cycle-02"

    # First that the next cycle opens at all. Without this every refusal below
    # could be refusing for some unrelated reason and the control would pass
    # while proving nothing, which is B01-F11's control exactly.
    if do_freeze(tB).returncode != 0:
        failures.append("fixture: cycle 02 would not open even with a healthy "
                        "ledger, so the refusals below establish nothing")
    else:
        shutil.rmtree(cyc2)
        print("  [ok] with a healthy ledger and CONTINUE, the next cycle opens")

    led = tB / "runs" / "T-001" / "plan-review" / "ledger.json"
    healthy = led.read_text(encoding="utf-8")

    # The reproduction: an event replay has no transition for.
    doc = json.loads(healthy)
    doc["findings"]["C01-F01"]["history"].append(
        {"at": "2026-09-14T00:00:00Z", "cycle": 1, "event": "BANANA",
         "note": "an event no version of replay knows", "state": "OPEN"})
    write_lf(led, json.dumps(doc, indent=2) + "\n")

    _rb2 = do_freeze(tB)
    if _rb2.returncode == 0:
        failures.append("an unrecognised ledger event stopped the controller "
                        "calculating and the runner opened the next cycle "
                        "anyway. B03-F01 unrepaired.")
        if cyc2.exists():
            shutil.rmtree(cyc2)
    elif cyc2.exists():
        failures.append("the freeze refused the unknown event but left a "
                        "cycle-02 directory behind")
    else:
        print("  [ok] refused: a controller that cannot calculate is not "
              "permission")

    write_lf(led, healthy)

    # The rest of the boundary, driven by stubbing the controller. The finding
    # is about what this runner accepts as an answer, so the cases worth testing
    # are the answers a controller can give, not only the one bug that exposed
    # them. Replacing a covered component is why the fixture is exempt.
    for label, body, expect in (
        ("a controller that exits non-zero saying nothing",
         "import sys\nsys.exit(3)\n", "exit 3"),
        # The decisive one. Every other non-zero case also trips the
        # missing-status check, so they would still refuse even if the exit code
        # were ignored, just for the wrong reason. This one says CONTINUE on its
        # way out: only a check that reads the exit code refuses it.
        ("a controller that says CONTINUE and then fails",
         "import sys\nprint('LOOP_STATUS: CONTINUE')\nsys.exit(1)\n", "exit 1"),
        ("a controller that exits 0 and reports no status",
         "print('all quiet')\n", "no LOOP_STATUS line"),
        ("a status this runner does not recognise",
         "print('LOOP_STATUS: BANANA')\n", "does not recognise"),
        ("two statuses in one run",
         "print('LOOP_STATUS: CONTINUE')\nprint('LOOP_STATUS: CONVERGED')\n",
         "2 LOOP_STATUS lines"),
    ):
        write_lf(tB / "scripts" / "loop_state.py", body)
        res = do_freeze(tB)
        out = res.stdout + res.stderr
        if res.returncode == 0:
            failures.append(f"the runner treated {label} as permission to open "
                            f"another cycle")
            if cyc2.exists():
                shutil.rmtree(cyc2)
        elif expect not in out:
            failures.append(f"refused {label}, but not for that reason:\n"
                            f"      {out.strip().splitlines()[:1]}")
        elif cyc2.exists():
            failures.append(f"refused {label} but left a cycle-02 directory")
        else:
            print(f"  [ok] refused: {label}")

    # ---- B03-F02: the controls are recorded beside the target, not in it ----
    # Cycle 03's prompt said "the suites are in the target". They were not, and
    # cycle 02 had already said so in prose that no Finding ID block carried, so
    # nothing transcribed it and the sentence survived into the next prompt.
    #
    # The repair records them instead of pretending they were reviewed. This
    # control exists to keep both halves true: the manifest is written and
    # accurate, and the suites still do not appear as target artifacts. A repair
    # that quietly added them to plan_files would satisfy the first half and
    # reintroduce the defect, so the second assertion is the load-bearing one.
    print()
    print("control suites are recorded, not targeted (B03-F02)")

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    tA = make_repo(); made.append(tA)
    # The fixture copies no suites, so plant two. Their names only have to match
    # the glob; their contents are never executed.
    write_lf(tA / "scripts" / "test_alpha.py", "# alpha\nprint('[ok] a')\n")
    write_lf(tA / "scripts" / "test_beta.py", "# beta\nprint('[ok] b')\n")
    sh("git", "add", "-A", cwd=tA)
    sh("git", "commit", "-qm", "suites", cwd=tA)
    do_init(tA); do_freeze(tA)

    cycA = tA / "runs/T-001/plan-review/cycle-01"
    amA = cycA / "auxiliary-evidence.json"
    tgtA = json.loads((cycA / "target.json").read_text(encoding="utf-8"))

    if not amA.is_file():
        failures.append("freeze wrote no auxiliary-evidence.json, so the "
                        "control versions behind the stated counts are not "
                        "recorded anywhere in the cycle")
    else:
        manA = json.loads(amA.read_text(encoding="utf-8"))
        listed = {s["path"]: s["sha256"] for s in manA["suites"]}
        want = {f"scripts/test_{n}.py": _sha(tA / "scripts" / f"test_{n}.py")
                for n in ("alpha", "beta")}
        if listed != want:
            failures.append(f"the manifest does not record the suites as they "
                            f"stood at freeze:\n    listed {listed}\n"
                            f"    actual {want}")
        else:
            print(f"  [ok] the manifest records every suite at freeze "
                  f"({len(listed)} of them)")

        if tgtA.get("auxiliary_evidence_sha256") != _sha(amA):
            failures.append("target.json does not record the manifest's digest, "
                            "so a later change to it would leave nothing to "
                            "compare against")
        else:
            print("  [ok] target.json records the manifest digest, and "
                  "target.sha256 covers target.json")

        # The whole point. Recording must not become membership.
        targeted = {r["path"] for r in tgtA.get("plan_files", [])}
        if targeted & set(listed):
            failures.append(
                "a control suite appears in plan_files. Recording the suites "
                "must not put them in the target: the gate refuses a target "
                "carrying artifacts outside its covered set, and the claim "
                "B03-F02 was raised about would be true again.")
        else:
            print("  [ok] no control suite appears in the review target")

        # The record is of freeze-time bytes. Later edits are ordinary work and
        # must not rewrite what the cycle says it measured.
        write_lf(tA / "scripts" / "test_alpha.py", "# alpha changed\n")
        after = json.loads(amA.read_text(encoding="utf-8"))
        if after != manA:
            failures.append("editing a suite after freeze changed the frozen "
                            "manifest")
        elif listed.get("scripts/test_alpha.py") == _sha(
                tA / "scripts" / "test_alpha.py"):
            failures.append("the manifest still matches the edited suite, so it "
                            "is not recording freeze-time bytes")
        else:
            print("  [ok] a later suite edit leaves the frozen record unchanged")

    for t in made:
        shutil.rmtree(t, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("all controls fired; every refusal is reachable and the happy path passes MC-2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
