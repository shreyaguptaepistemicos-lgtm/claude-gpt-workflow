#!/usr/bin/env python3
"""Review cycle runner.

Composes review input, freezes the target, captures raw reviewer output, and
refuses to open a cycle whose preconditions do not hold.

    python scripts/run_review.py init   --run A1E-001 \
        --protocol specs/implementation-review-protocol-v1.1.md \
        --spec specs/gap/A1E_gap_object_schema_v1-4.md
    python scripts/run_review.py freeze --run A1E-001 --type plan \
        --prompt specs/prompts/plan-review.md --file runs/A1E-001/plan/01-PLAN.md
    python scripts/run_review.py record --cycle runs/A1E-001/plan-review/cycle-01 \
        --output raw.txt --invocation manual

Exit 0 = the step completed, 1 = refused, 2 = could not run.

MC-1 boundary, CONVENTION_ONLY on this environment
--------------------------------------------------
codex-input.md is composed here and never by the implementing agent. That
separation is a convention this script follows. It is not something the script
can enforce: the implementing agent holds write access to these paths. No claim
of technical protection may be made while MC1_ENFORCEMENT is CONVENTION_ONLY.

Write-once evidence
-------------------
target.json, target.sha256, codex-input.md and codex-output-raw.md are never
overwritten. A cycle that went wrong is repaired by opening a new cycle, not by
editing the old one. `freeze` refuses on an existing cycle directory; `record`
refuses when raw output is already present.

What this runner does not establish
-----------------------------------
It does not invoke the reviewer. It cannot show that codex-output-raw.md came
from the invocation codex-input.md describes; that binding rests on the operator
and is recorded, not proven, in invocation.json. This is the same limit stated
in specs/evidence-schema-v1.0.md, restated here so it is visible at the point of
use.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import authority  # noqa: E402
import run_pins  # noqa: E402

VALIDATOR = REPO / "scripts" / "validate_cycle.py"

MAX_CYCLES = 4
REVIEW_TYPES = ("plan", "implementation")

# §6's four exits. Named here rather than "not CONTINUE" so that a future status
# the controller learns to emit does not silently become permission to open
# another cycle.
TERMINAL_EXITS = ("CONVERGED", "HUMAN_ADJUDICATION_REQUIRED", "STALLED",
                  "MAX_4_REACHED")
INVOCATIONS = ("manual", "automated")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")

# MC-1 requires every run to record this. CONVENTION_ONLY here because the
# implementing agent and the review evidence share one write authority on a
# single-user machine; see specs/evidence-schema-v1.0.md. Upgrading it is a
# change to the environment, not to this constant.
MC1_ENFORCEMENT = "CONVENTION_ONLY"


class Refused(Exception):
    """A precondition did not hold. Exit 1, change nothing."""


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_lf(p: Path, text: str) -> None:
    """Write evidence with LF endings on every platform.

    Path.write_text translates \\n to the platform line ending, so the same
    target.json frozen on Windows and on Linux would hash differently while
    being self-consistent on each. MC-2 would pass on both and the divergence
    would only surface when someone tried to reproduce a freeze elsewhere and
    got a different TARGET_SHA256. Evidence hashes have to be a property of the
    content, not of the machine that wrote it.
    """
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def rel(p: Path) -> str:
    """Repo-relative with forward slashes, so evidence is platform-neutral."""
    return p.resolve().relative_to(REPO).as_posix()


def hashed_ref(p: Path) -> dict:
    return {"path": rel(p), "sha256": sha256_file(p)}


def spec_digest(entries: list[dict]) -> str:
    """One digest over the spec set.

    SHA-256 of "path:sha256\\n" lines, sorted by path. Defined here because it
    has to be reproducible by anyone auditing a run, not just by this script.
    """
    body = "".join(f"{e['path']}:{e['sha256']}\n" for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def git_head() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except FileNotFoundError:
        return None


def require_file(p: Path, what: str) -> Path:
    if not p.is_file():
        raise Refused(f"{what} not found: {p}")
    if p.stat().st_size == 0:
        raise Refused(f"{what} is empty: {p}")
    return p


# ---------------------------------------------------------------- init

def cmd_init(args: argparse.Namespace) -> int:
    run_dir = REPO / "runs" / args.run
    run_json = run_dir / "run.json"
    if run_json.exists():
        raise Refused(f"run.json already exists: {run_json}\n"
                      "A run's pins are fixed at creation. Use a new run id.")

    # The bootstrap gate, ruled mandatory 8 September 2026. This runner and the
    # MC-2 checker cannot pass through the process they enable, so a one-time
    # independent review stands in for it, and no real run starts without one.
    #
    # Enforced here rather than at freeze because init is where a run becomes a
    # thing that exists. A run created now and frozen later would otherwise carry
    # pins made before anyone had looked at the code doing the pinning.
    # Loaded by path rather than by name. `from bootstrap_gate import ...` works
    # only when the script's own directory happens to be on sys.path, which it is
    # when run directly and is not in several other cases. A gate that silently
    # becomes an ImportError is a gate that stops gating.
    gate = load_gate()

    if args.bootstrap_exempt:
        # Ruling 2, 9 September: the exception "ends immediately after the first
        # human approval of a runner". Before this, --bootstrap-exempt was a flag
        # with no expiry, so "bootstrap" could quietly become the permanent way
        # runs were created. The termination is now a question the gate answers
        # from the record rather than a date anyone has to remember.
        available, why = gate.bootstrap_exception_available(REPO)
        if not available:
            raise Refused(
                "--bootstrap-exempt is no longer available.\n  "
                + "\n  ".join(why) +
                "\n\n  Create the run without the flag. The components have an "
                "approved runner now,\n  so real protocol runs are the only kind "
                "left to make.")
    else:
        ok, reasons = gate.evaluate(REPO)
        if not ok:
            raise Refused(
                "BOOTSTRAP_REVIEW not satisfied, so no real protocol run may be "
                "created:\n  " + "\n  ".join(reasons) +
                "\n\n  This is the one declared exception to the protocol and it "
                "is not optional.\n  To produce development evidence instead, "
                "pass --bootstrap-exempt, which\n  labels the run "
                "BOOTSTRAP / DEVELOPMENT EVIDENCE — NOT_A_PROTOCOL_CYCLE.")

    protocol = require_file(Path(args.protocol).resolve(), "protocol file")
    specs = [hashed_ref(require_file(Path(s).resolve(), "spec file")) for s in args.spec]
    if not specs:
        raise Refused("a run needs at least one spec file; --spec is repeatable")

    head = git_head()
    if head is None:
        raise Refused("cannot resolve git HEAD; the run must pin a commit")

    run = {
        "run_id": args.run,
        "created_at": now(),
        "protocol_commit": head,
        "protocol": hashed_ref(protocol),
        "protocol_sha256": sha256_file(protocol),
        "spec_files": specs,
        "spec_sha256": spec_digest(specs),
        "max_cycles": MAX_CYCLES,
        # B01-F14. MC-1: "Each run records: MC1_ENFORCEMENT:". A statement in
        # repository documentation is not a record on the run, and a reader of
        # this run's evidence should not have to go looking elsewhere to learn
        # what the enforcement status was at the time it was created.
        "mc1_enforcement": MC1_ENFORCEMENT,
        # Recorded on the run, not just checked at init, so a reader of the
        # evidence can tell which kind of run this was without consulting
        # anything else.
        "bootstrap_review": ("EXEMPT — BOOTSTRAP / DEVELOPMENT EVIDENCE, "
                             "NOT_A_PROTOCOL_CYCLE"
                             if args.bootstrap_exempt else "APPROVED"),
        # Ruling 1: cycle 02 sits inside the exception because no approved runner
        # exists yet. Recorded on the run so a later reader can see which side of
        # the termination this run was created on, without reconstructing the
        # state of runner-approvals/ at the time.
        "runner_approval_chain": ("NOT_STARTED — no approved runner exists"
                                  if gate.bootstrap_exception_available(REPO)[0]
                                  else "ACTIVE — candidate runners are reviewed "
                                       "by the prior approved runner"),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    write_lf(run_json, json.dumps(run, indent=2) + "\n")

    print(f"initialised {rel(run_json)}")
    print(f"  protocol_commit  {head}")
    print(f"  protocol_sha256  {run['protocol_sha256']}")
    print(f"  spec_sha256      {run['spec_sha256']}  over {len(specs)} spec file(s)")
    return 0


# ---------------------------------------------------------------- freeze

def load_run(run_id: str) -> dict:
    run_json = REPO / "runs" / run_id / "run.json"
    if not run_json.is_file():
        raise Refused(f"no run.json for {run_id}; run `init` first")
    try:
        return json.loads(run_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"run.json is not valid JSON: {e}")


def check_pins_still_hold(run: dict, run_dir: Path | None = None,
                          cycle_n: int | None = None) -> None:
    """The governing artifacts must not have moved since init.

    A run whose spec changed underneath it is not four cycles against one spec;
    it is four cycles against whatever happened to be on disk each time. This is
    the check that makes the run.json pin mean something.

    Alex Zamurko's Run-Pin and Review-Target Separation Specification, 10
    September, narrows what belongs in that set: "A run-level pin may include
    only artifacts that are required to remain invariant for the entire run." An
    artifact under review is not one of those, and pinning one anyway is what
    stopped BOOTSTRAP-001 between cycles 01 and 02.

    So the set checked here is the one in force for the cycle being frozen,
    replayed from the amendment history, rather than whatever run.json listed at
    init. Cycle 01 is still checked against cycle 01's pins.
    """
    pins = None
    if run_dir is not None and cycle_n is not None:
        try:
            pins = set(run_pins.governing_pins(run, run_dir, cycle_n))
        except run_pins.PinError as e:
            raise Refused(f"the run's pin history cannot be read, so what "
                          f"governs this cycle is undeterminable:\n  {e}")

    drift: list[str] = []

    def still_pinned(rel_path: str) -> bool:
        return pins is None or rel_path in pins

    if still_pinned(run["protocol"]["path"]):
        proto = REPO / run["protocol"]["path"]
        if not proto.is_file():
            drift.append(f"protocol file is gone: {run['protocol']['path']}")
        elif sha256_file(proto) != run["protocol"]["sha256"]:
            drift.append(f"protocol changed since init: {run['protocol']['path']}\n"
                         f"    pinned {run['protocol']['sha256']}\n"
                         f"    actual {sha256_file(proto)}")

    for e in run["spec_files"]:
        if not still_pinned(e["path"]):
            continue
        p = REPO / e["path"]
        if not p.is_file():
            drift.append(f"spec file is gone: {e['path']}")
        elif sha256_file(p) != e["sha256"]:
            drift.append(f"spec changed since init: {e['path']}\n"
                         f"    pinned {e['sha256']}\n"
                         f"    actual {sha256_file(p)}")

    if drift:
        raise Refused("run pins no longer hold:\n  " + "\n  ".join(drift) +
                      "\n\nEither restore the pinned bytes or start a new run. "
                      "Continuing would produce cycles that cite a spec version "
                      "nobody reviewed.")


def check_pin_target_separation(run: dict, run_dir: Path, cycle_n: int,
                                target_paths: list[str]) -> None:
    """§2's governing invariant, refused rather than described.

    "No review process may require an artifact to remain byte-invariant for the
    duration of a run while simultaneously requiring that same artifact version
    to change in order to resolve review findings."

    Checked at freeze, where both sides are known for the first time: the pin set
    comes from the run and the target list from this cycle's arguments. Nothing
    checked it before, which is why the contradiction was only discovered by the
    loop deadlocking on it two cycles later.
    """
    try:
        pins = run_pins.governing_pins(run, run_dir, cycle_n)
    except run_pins.PinError as e:
        raise Refused(f"the run's pin history cannot be read:\n  {e}")
    clash = run_pins.separation_violations(pins, target_paths)
    if not clash:
        return
    raise Refused(
        "an artifact cannot be both a run-level governing pin and a review "
        "target:\n  " + "\n  ".join(clash) +
        "\n\n  It would have to stay byte-identical for the whole run and also "
        "change to\n  resolve any finding raised about it. The first repair "
        "would break the run's own\n  pin and stop the cycle that was meant to "
        "demonstrate the repair.\n\n"
        "  Alex Zamurko, 10 September: an artifact belongs to exactly one role, "
        "RUN-GOVERNING\n  or REVIEW-TARGET, unless explicit ACTIVE/CANDIDATE "
        "version separation is in place.\n"
        "  Amend the run's pin set, recording reason, affected artifacts, prior "
        "set, new set\n  and effective cycle in pin-amendments.json.")


def load_gate():
    """The bootstrap gate module, loaded by path.

    By path rather than by name: `from bootstrap_gate import ...` works only
    when the script's directory happens to be on sys.path, and a gate that
    silently becomes an ImportError is a gate that stops gating.
    """
    import importlib.util
    gate_py = Path(__file__).resolve().parent / "bootstrap_gate.py"
    if not gate_py.is_file():
        raise Refused(f"the bootstrap gate is missing: {gate_py}\n"
                      "  Refusing rather than proceeding. A missing gate is not "
                      "an absent requirement.")
    spec_ = importlib.util.spec_from_file_location("_bootstrap_gate", gate_py)
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    return mod


def check_bootstrap_still_holds(run: dict) -> None:
    """B01-F08: the gate has to hold now, not just when the run was created.

    Codex: "Bootstrap approval is evaluated only at initialization. A probe
    approved bootstrap, initialized a real run, changed validate_cycle.py, and
    successfully froze a cycle."

    I put the check at init and reasoned that init is where a run becomes a thing
    that exists. That was half right and wrong about the half that matters: a run
    can sit for days between init and its cycles, and every cycle is where the
    tooling is actually relied upon. So the gate is checked at both, and an
    exempt run stays exempt at both.
    """
    if str(run.get("bootstrap_review", "")).startswith("EXEMPT"):
        return
    ok, reasons = load_gate().evaluate(REPO)
    if not ok:
        raise Refused(
            "BOOTSTRAP_REVIEW no longer holds, so this cycle may not be "
            "frozen:\n  " + "\n  ".join(reasons) +
            "\n\n  The approval was valid when the run was created. Something "
            "covered by it has\n  changed since. Re-review, or revert the "
            "change.")


def next_cycle(review_dir: Path) -> int:
    if not review_dir.is_dir():
        return 1
    used = []
    for d in review_dir.iterdir():
        m = re.fullmatch(r"cycle-(\d{2})", d.name) if d.is_dir() else None
        if m:
            used.append(int(m.group(1)))
    return max(used) + 1 if used else 1


def check_previous_cycle_closed(review_dir: Path, n: int) -> None:
    if n <= 1:
        return
    prev = review_dir / f"cycle-{n - 1:02d}"
    raw = prev / "codex-output-raw.md"
    if not raw.is_file() or raw.stat().st_size == 0:
        raise Refused(f"cycle {n - 1:02d} has no recorded output at {rel(raw) if raw.exists() else raw}\n"
                      "Record the previous cycle's raw output before opening the next. "
                      "Two open cycles means the budget count is guesswork.")


def check_loop_not_terminated(review_dir: Path, n: int) -> None:
    """Refuse to open a cycle after the loop has already exited.

    B01-F02: "The runner checks previous output existence, not the previous loop
    exit." Existence is the wrong question. A cycle can be perfectly well closed
    and still be the cycle at which §6 required the loop to stop, and freezing
    the next one produced evidence under a loop that had already terminated.

    The controller now retains the first terminal outcome, so it will report that
    exit rather than being overwritten by whatever the new cycle does. This makes
    the runner refuse to create the situation in the first place, which is the
    half that keeps the unauthorized cycle from existing at all.

    An undeterminable loop state is a refusal too. If the controller cannot say
    whether the loop has exited, nobody can say whether another cycle is
    permitted, and guessing CONTINUE is the assumption that costs a cycle.
    """
    if n <= 1:
        return
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "loop_state.py"),
         "--review", str(review_dir), "--quiet"],
        capture_output=True, text=True)
    if r.returncode == 2:
        raise Refused(
            "the loop state cannot be determined, so whether another cycle is "
            "permitted cannot be\ndetermined either:\n  "
            + (r.stderr.strip().splitlines() or ["(no reason given)"])[0]
            + "\nRepair the evidence and rerun. Opening a cycle on an "
              "undeterminable loop is how a\nterminated loop keeps running.")
    status = ""
    for line in r.stdout.splitlines():
        if line.startswith("LOOP_STATUS:"):
            status = line.split(":", 1)[1].strip()
    if status in TERMINAL_EXITS:
        raise Refused(
            f"the loop has already exited: LOOP_STATUS is {status}.\n"
            f"Opening cycle {n:02d} would produce evidence under a loop that "
            "§6 had already stopped.\n"
            "If another loop was genuinely approved, record the human "
            "authorization in\n  "
            f"{rel(review_dir / 'loop-authorizations.json')}\n"
            "naming the boundary, the outcome it clears, who authorized it and "
            "why. Otherwise\ntake the outcome to human review.")


def compose_input(prompt: str, target_hash: str, run: dict, rtype: str,
                  cycle_n: int, artifacts: list[tuple[dict, str]],
                  protocol_text: str = "") -> str:
    """Everything the reviewer needs, in the file the target hash binds.

    The protocol text is included, not merely hashed. Every review is *against*
    the protocol, and an earlier version of this function named PROTOCOL_SHA256
    in the header and stopped there. A reviewer cannot read a hash, so it would
    have been asked to judge conformance to a document it had never seen and
    would have answered from memory or invention.

    That is the pilot's failure restated: recording an artifact's hash detects a
    later change to it, and says nothing about whether the reviewer read it.
    Here it was worse, because the reviewer could not have read it at all.

    It belongs in this file rather than being pasted alongside, because
    codex-input.md is what MC-2 check 10 binds to the frozen target. Anything
    supplied next to it is outside the evidence and cannot be shown to have been
    what the reviewer saw.
    """
    lines = [
        f"# Review input — {run['run_id']} / {rtype} review / cycle {cycle_n:02d}",
        "",
        "```text",
        f"TARGET_SHA256   {target_hash}",
        f"PROTOCOL_SHA256 {run['protocol_sha256']}",
        f"SPEC_SHA256     {run['spec_sha256']}",
        "```",
        "",
        "The target hash above is the binding between the frozen artifact and this",
        "input. Quote it in your response.",
        "",
        "---",
        "",
        prompt.rstrip(),
        "",
        "---",
        "",
    ]
    if protocol_text:
        lines += [
            "# The governing protocol",
            "",
            f"`{run['protocol']['path']}`, sha256 `{run['protocol_sha256']}`.",
            "",
            "This is the document the artifacts below are reviewed against. Where",
            "it and the review prompt disagree, this governs.",
            "",
            "```",
            protocol_text.rstrip("\n"),
            "```",
            "",
            "---",
            "",
        ]
    lines += [
        "# Artifacts under review",
        "",
    ]
    for ref, body in artifacts:
        lines += [f"## `{ref['path']}`", "", f"`sha256 {ref['sha256']}`", "",
                  "```", body.rstrip("\n"), "```", ""]
    return "\n".join(lines) + "\n"


def cmd_freeze(args: argparse.Namespace) -> int:
    if args.type not in REVIEW_TYPES:
        raise Refused(f"--type must be one of {REVIEW_TYPES}, got {args.type!r}")

    run = load_run(args.run)
    check_bootstrap_still_holds(run)

    prompt_path = require_file(Path(args.prompt).resolve(), "prompt file")
    prompt = prompt_path.read_text(encoding="utf-8")

    review_dir = REPO / "runs" / args.run / f"{args.type}-review"
    run_dir = REPO / "runs" / args.run
    n = next_cycle(review_dir)
    if n > MAX_CYCLES:
        raise Refused(f"cycle {n} would exceed the {MAX_CYCLES}-cycle budget for "
                      f"{args.run} {args.type} review.\n"
                      "MAX_4_REACHED is an exit, not an obstacle to route around. "
                      "Escalate to human review.")
    # After n is known, because the pin set in force is a property of the cycle
    # rather than of the run: an amendment effective at cycle k governs k onward
    # and leaves earlier cycles checked against what they were conducted under.
    check_pins_still_hold(run, run_dir, n)
    check_previous_cycle_closed(review_dir, n)
    check_loop_not_terminated(review_dir, n)

    cycle = review_dir / f"cycle-{n:02d}"
    if cycle.exists():
        raise Refused(f"cycle directory already exists: {rel(cycle)}\n"
                      "Frozen evidence is write-once.")

    target = {
        "review_type": args.type,
        "run_id": run["run_id"],
        "cycle": n,
        "protocol_commit": run["protocol_commit"],
        "protocol_sha256": run["protocol_sha256"],
        "spec_sha256": run["spec_sha256"],
        "frozen_at": now(),
    }

    artifacts: list[tuple[dict, str]] = []

    if args.type == "plan":
        if not args.file:
            raise Refused("plan review needs at least one --file")
        refs = [hashed_ref(require_file(Path(f).resolve(), "plan file")) for f in args.file]
        # Both sides are known for the first time here: the pin set from the run,
        # the target list from this cycle's arguments. Nothing compared them
        # before, which is why the contradiction surfaced only when the loop
        # deadlocked on it a cycle later.
        check_pin_target_separation(run, run_dir, n, [r["path"] for r in refs])
        target["plan_files"] = refs
        artifacts = [(r, (REPO / r["path"]).read_text(encoding="utf-8", errors="replace"))
                     for r in refs]
    else:
        # §10.1: "These fields are mandatory, not conditional."
        if not args.candidate_commit:
            raise Refused("implementation review requires --candidate-commit")
        r = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", f"{args.candidate_commit}^{{tree}}"],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise Refused(f"--candidate-commit does not resolve: {args.candidate_commit}")
        target["candidate_commit"] = args.candidate_commit
        # Derived, not supplied: a tree hash typed by hand is a tree hash that
        # can be typed to match whatever was recorded.
        target["candidate_tree_hash"] = r.stdout.strip()

        if not args.approved_plan_hash:
            raise Refused("implementation review requires --approved-plan-hash")
        if not HEX64.match(args.approved_plan_hash):
            raise Refused("--approved-plan-hash must be a lowercase 64-char hex digest")
        target["approved_plan_hash"] = args.approved_plan_hash

        for path_key, hash_key, arg, label in (
                ("diff_path", "diff_hash", args.diff, "diff"),
                ("test_result_path", "test_result_hash", args.test_results,
                 "test results")):
            if not arg:
                raise Refused(f"implementation review requires --{label.replace(' ', '-')}")
            ref = hashed_ref(require_file(Path(arg).resolve(), label))
            target[path_key] = ref["path"]
            target[hash_key] = ref["sha256"]
            artifacts.append((ref, (REPO / ref["path"]).read_text(encoding="utf-8",
                                                                 errors="replace")))

    cycle.mkdir(parents=True)

    # ---- snapshot the reviewed bytes ----
    # Alex Zamurko, 9 September 2026:
    #
    #     At freeze, snapshot the exact reviewed artifact bytes into the cycle
    #     evidence directory and validate those preserved copies, not the live
    #     working tree. A completed review cycle must remain valid after the
    #     implementation is repaired.
    #
    # Before this, freeze recorded a hash of a file that stayed mutable, and
    # check 9 re-hashed the live tree. So repairing the code a review asked for
    # invalidated the cycle that asked, the controller then ignored its events,
    # and eighteen findings vanished from loop state. Repair between cycles is
    # the entire design; it cannot be the thing that destroys the previous cycle.
    #
    # Every artifact bound to the target, and only those: not top-level files
    # alone, not the whole repository.
    snapshot = cycle / "artifacts"
    for ref, body in artifacts:
        dest = snapshot / ref["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((REPO / ref["path"]).read_bytes())
        if sha256_file(dest) != ref["sha256"]:
            raise Refused(f"snapshot of {ref['path']} does not match the hash "
                          "recorded for it; refusing to freeze a cycle whose "
                          "preserved copy already disagrees with its own record")

    tj = cycle / "target.json"
    write_lf(tj, json.dumps(target, indent=2) + "\n")
    digest = sha256_file(tj)
    write_lf(cycle / "target.sha256", digest + "\n")

    ci = cycle / "codex-input.md"
    # Read from the pinned path. check_pins_still_hold has already verified this
    # file hashes to run.json's protocol_sha256, so the text embedded below is
    # the text the header names rather than whatever is on disk under that name.
    protocol_text = (REPO / run["protocol"]["path"]).read_text(encoding="utf-8")
    write_lf(ci, compose_input(prompt, digest, run, args.type, n, artifacts,
                               protocol_text))

    # Self-checks, not assumptions, on what was just written.
    if digest not in ci.read_text(encoding="utf-8"):
        raise Refused("composed input does not contain the target hash; refusing to "
                      "leave a cycle that MC-2 would reject")
    if b"\r" in tj.read_bytes():
        raise Refused("target.json contains CR bytes; its hash would not reproduce "
                      "on another platform")

    print(f"froze {rel(cycle)}")
    print(f"  target.sha256  {digest}")
    print(f"  artifacts      {len(artifacts)}")
    print()
    print("Next: run the review on codex-input.md, save the reply verbatim, then")
    print(f"  python scripts/run_review.py record --cycle {rel(cycle)} \\")
    print("      --output <reply file> --invocation manual")
    return 0


# ---------------------------------------------------------------- findings

# The parser and the canonical Finding ID grammar live in one module, imported
# by this runner and by the MC-2 checker. Two implementations of a format is how
# the prompt, the ledger and the parser ended up each enforcing their own.
import findings_format

CLASSES = findings_format.CLASSES


def canonical_id_grammar():
    return findings_format.canonical_id_grammar()


def extract_findings(raw: str) -> tuple[list[dict], list[str]]:
    # A missing or unreadable schema is a refusal, not a traceback: the parser
    # cannot know the canonical grammar, so it cannot say anything about the
    # review, and saying nothing must not look like finding nothing.
    try:
        return findings_format.extract(raw)
    except findings_format.FormatError as e:
        raise Refused(str(e))


# ---------------------------------------------------------------- capture
#
# Alex Zamurko, 9 September 2026, issue 6. Before this, `record` refused if a
# capture already existed, so a failed capture killed the cycle. In practice
# that meant deleting evidence: the reply reached the file on the fourth
# attempt, two earlier attempts held seventy bytes of shell command and passed
# MC-2, and a better capture sat unnoticed in another directory. Nothing said
# which of them governed.
#
#     Use the rule that the first capture satisfying the predefined
#     capture-validity requirements becomes authoritative. Any replacement
#     requires explicit invalidation and preservation of both attempts.
#
# So attempts are numbered, all are kept, and one is designated. Nothing is
# deleted to tidy up, which is what happened three times in one afternoon.

CAPTURE_SCHEMA = "cycle-capture/1"


def capture_validity(raw_text: str, target_hash: str,
                     zero_asserted: bool) -> list[str]:
    """The predefined requirements. Empty list means this capture is valid.

    Fixed in advance rather than judged per case, because the point of a
    designation rule is that it does not depend on who is looking.
    """
    problems: list[str] = []
    if not raw_text.strip():
        problems.append("empty")
    if target_hash not in raw_text:
        problems.append(
            f"does not quote the target hash {target_hash[:16]}…; the review "
            "prompt requires the reviewer to, and without it this is not "
            "demonstrably a capture of this target")
    found, parse_problems = extract_findings(raw_text)
    problems += parse_problems
    if not found and not parse_problems and not zero_asserted:
        problems.append("no finding blocks, and zero was not asserted; pass "
                        "--zero-findings if the reviewer genuinely reported "
                        "none, since absence must never be read as zero")
    return problems


def next_attempt(cycle: Path) -> int:
    d = cycle / "captures"
    if not d.is_dir():
        return 1
    used = [int(m.group(1)) for p in d.iterdir()
            if (m := re.fullmatch(r"attempt-(\d{2})", p.name))]
    return max(used) + 1 if used else 1


def load_capture_log(cycle: Path) -> dict:
    p = cycle / "capture-log.json"
    if not p.is_file():
        return {"schema": CAPTURE_SCHEMA, "authoritative": None, "attempts": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"capture-log.json is not valid JSON: {e}")


def cmd_record(args: argparse.Namespace) -> int:
    if args.invocation not in INVOCATIONS:
        raise Refused(f"--invocation must be one of {INVOCATIONS}")

    cycle = Path(args.cycle).resolve()
    if not (cycle / "target.json").is_file():
        raise Refused(f"not a frozen cycle directory: {cycle}")

    log = load_capture_log(cycle)
    if log.get("authoritative") and not args.supersede_capture:
        raise Refused(
            f"attempt-{log['authoritative']:02d} is already the authoritative "
            "capture for this cycle.\n"
            "  The first capture meeting the validity requirements governs, and "
            "later ones do\n  not displace it silently. Replacing it takes both "
            "--supersede-capture with\n  --reason, and an approval recorded by "
            "someone other than the implementing\n  agent. Both captures are "
            "kept either way; only the designation would move.")
    if args.supersede_capture and not log.get("authoritative"):
        raise Refused("--supersede-capture passed but no authoritative capture "
                      "exists to supersede")
    if args.supersede_capture and not (args.reason or "").strip():
        raise Refused(
            "--supersede-capture requires --reason.\n"
            "  Replacing the capture that governs a review is a decision, and "
            "the record has\n  to say why it was made rather than leaving a "
            "silent substitution.")

    src = require_file(Path(args.output).resolve(), "reviewer output")
    body = src.read_text(encoding="utf-8", errors="replace")
    raw = cycle / "codex-output-raw.md"

    # Alex Zamurko, ruling 3, 9 September 2026: supersession needs "an authority
    # outside the implementer plus an auditable reason". --reason was neither. It
    # is a string I type, in a command I run, so the party the control constrains
    # was operating the control. Preserving every attempt does not help if the
    # same party still picks which one governs.
    #
    # Checked here, after the replacement's bytes are known and before anything
    # on disk moves, because the approval has to bind to those exact bytes.
    if args.supersede_capture:
        approval_path = cycle / "capture-supersession-approval.json"
        try:
            approval = authority.require_approval(
                approval_path, "capture-supersession",
                {"cycle": cycle.name,
                 "superseded_sha256": log["authoritative_sha256"],
                 "superseding_sha256": sha256_bytes(src.read_bytes())})
        except authority.NotAuthorized as e:
            raise Refused(f"supersession is not authorized.\n\n{e}")
        args._approval = approval

    # ---- preserve this attempt, whatever comes of it ----
    # Written before validity is judged, so a failed capture leaves a record
    # rather than nothing. Three attempts vanished today because the only way to
    # retry was to delete what was there.
    target_hash = (cycle / "target.sha256").read_text(encoding="utf-8").strip()
    n = next_attempt(cycle)
    adir = cycle / "captures" / f"attempt-{n:02d}"
    adir.mkdir(parents=True)
    (adir / "raw.md").write_bytes(src.read_bytes())

    invalid = capture_validity(body, target_hash, bool(args.zero_findings))
    entry = {
        "attempt": n,
        "recorded_at": now(),
        "source": str(src),
        "invocation": args.invocation,
        "note": args.note or "",
        "sha256": sha256_file(adir / "raw.md"),
        "bytes": (adir / "raw.md").stat().st_size,
        "valid": not invalid,
        "problems": invalid,
        "retry_reason": args.reason or "",
    }
    write_lf(adir / "capture.json", json.dumps(entry, indent=2) + "\n")
    log["attempts"].append(entry)

    if invalid:
        if args.supersede_capture:
            log["attempts"][-1]["superseded_nothing"] = True
        write_lf(cycle / "capture-log.json", json.dumps(log, indent=2) + "\n")
        raise Refused(
            f"attempt-{n:02d} does not meet the capture validity requirements:\n  "
            + "\n  ".join(invalid) +
            f"\n\n  The attempt is preserved at {rel(adir)} and recorded in "
            "capture-log.json.\n  Nothing was designated authoritative and the "
            "cycle is unchanged. Retry with a\n  better capture; failed attempts "
            "are kept rather than deleted.")

    if args.supersede_capture:
        prior = log["authoritative"]
        approval = getattr(args, "_approval", {})
        log.setdefault("invalidated", []).append({
            "attempt": prior,
            "invalidated_at": now(),
            "reason": args.reason,
            "superseded_by": n,
            # The authority is recorded alongside the act, not only in the
            # approval file, so removing that file later does not leave a
            # supersession in the log with nobody's name on it.
            "authorized_by": approval.get("authorized_by", ""),
            "authority_reason": approval.get("reason", ""),
            "authorized_at": approval.get("at", ""),
        })
        # The prior attempt stays on disk. Only the designation moves.
        raw.unlink(missing_ok=True)
        (cycle / "findings.json").unlink(missing_ok=True)

    log["authoritative"] = n
    log["authoritative_sha256"] = entry["sha256"]

    # ---- authoritative findings, extracted before anything is written ----
    # Alex Zamurko, 9 September 2026, issue 4:
    #
    #     Runner creates findings.json for every completed review. Explicitly
    #     represent zero findings; absence must never mean zero. Implementing
    #     agent must not manually create or overwrite authoritative findings.
    #
    # Extraction happens here rather than being left to whoever is present,
    # because the failure this closes is real findings never reaching the ledger
    # and the controller reading that silence as a clean review.
    found, problems = extract_findings(body)
    if problems:
        raise Refused(
            "the reviewer output does not parse as review evidence:\n  "
            + "\n  ".join(problems) +
            "\n\n  Nothing has been written. The raw output is captured only "
            "alongside an\n  authoritative findings record, so a cycle cannot "
            "exist with evidence nobody\n  could read.")

    # Zero has to be asserted, never inferred. "No blocks found" is equally
    # consistent with a clean review and with a capture that went wrong — which
    # happened four times before this cycle was recorded — so the operator
    # states which, and the record says a human said so.
    if not found and not args.zero_findings:
        raise Refused(
            "no finding blocks found in the reviewer output.\n"
            "  That is either a clean review or a capture that went wrong, and "
            "the two are\n  indistinguishable from here. If the reviewer "
            "genuinely reported none, pass\n  --zero-findings to assert it. "
            "Absence is not permitted to mean zero.")
    if found and args.zero_findings:
        raise Refused(
            f"--zero-findings was passed but {len(found)} finding block(s) are "
            "present:\n  " + ", ".join(f["id"] for f in found) +
            "\n  Nothing written.")

    # Bytes, not text. Whatever the reviewer returned is what gets stored.
    raw.write_bytes(src.read_bytes())

    write_lf(cycle / "findings.json", json.dumps({
        "schema": "cycle-findings/1",
        # Requirement 2: a review that cannot be parsed deterministically is
        # INVALID, and INVALID is not zero. Nothing reaches this line unless the
        # parse was clean, so the field is VALID here by construction — it is
        # recorded so a reader of the evidence sees the status rather than
        # inferring it from the file's existence.
        "review_result_status": "VALID",
        "raw_finding_count": len(found),
        "finding_id_grammar": canonical_id_grammar().pattern,
        "cycle": json.loads((cycle / "target.json").read_text(encoding="utf-8"))
                     .get("cycle"),
        "extracted_at": now(),
        # Binds this record to the exact capture it was read out of, so a later
        # recapture cannot leave a findings file describing different bytes.
        "source": f"captures/attempt-{n:02d}/raw.md",
        "source_attempt": n,
        "source_sha256": sha256_file(raw),
        "count": len(found),
        "zero_findings_asserted": bool(args.zero_findings),
        "findings": found,
    }, indent=2) + "\n")

    write_lf(cycle / "capture-log.json", json.dumps(log, indent=2) + "\n")

    write_lf(cycle / "invocation.json", json.dumps({
        "authoritative_attempt": n,
        "authoritative_sha256": entry["sha256"],
        "attempts_recorded": len(log["attempts"]),
        "invocation": args.invocation,
        "recorded_at": now(),
        "source": str(src),
        "note": args.note or "",
        "unproven": "This file records how the review was invoked. It does not "
                    "establish that codex-output-raw.md came from codex-input.md.",
    }, indent=2) + "\n")

    print(f"recorded {rel(raw)}  ({raw.stat().st_size} bytes, invocation={args.invocation})")
    if found:
        print(f"  findings.json  {len(found)} finding(s): "
              + ", ".join(f["id"] for f in found))
    else:
        print("  findings.json  zero findings, explicitly asserted")
    print()

    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle)],
                       capture_output=True, text=True)
    print(r.stdout.rstrip())
    if r.stderr.strip():
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode != 0:
        print()
        print("Cycle recorded but INVALID. It does not count toward the budget.")
    return 0 if r.returncode == 0 else 1


# ---------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_review.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create runs/<id>/run.json and pin protocol + specs")
    i.add_argument("--run", required=True)
    i.add_argument("--protocol", required=True)
    i.add_argument("--spec", action="append", default=[], required=True)
    i.add_argument("--bootstrap-exempt", action="store_true",
                   help="produce development evidence rather than a protocol "
                        "cycle; the run is labelled NOT_A_PROTOCOL_CYCLE and the "
                        "bootstrap gate is skipped. Not a way to start a real run "
                        "early.")
    i.set_defaults(fn=cmd_init)

    f = sub.add_parser("freeze", help="open the next cycle and compose reviewer input")
    f.add_argument("--run", required=True)
    f.add_argument("--type", required=True, choices=REVIEW_TYPES)
    f.add_argument("--prompt", required=True)
    f.add_argument("--file", action="append", default=[], help="plan review: repeatable")
    # §10.1 fields. candidate_tree_hash is derived from the commit, not passed.
    f.add_argument("--candidate-commit", dest="candidate_commit")
    f.add_argument("--approved-plan-hash", dest="approved_plan_hash")
    f.add_argument("--diff")
    f.add_argument("--test-results", dest="test_results")
    f.set_defaults(fn=cmd_freeze)

    r = sub.add_parser("record", help="store raw reviewer output and run the MC-2 gate")
    r.add_argument("--cycle", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--invocation", required=True, choices=INVOCATIONS)
    r.add_argument("--note", default="")
    r.add_argument("--supersede-capture", dest="supersede_capture",
                   action="store_true",
                   help="replace the authoritative capture. Requires --reason "
                        "AND an approval record from outside the implementing "
                        "agent at <cycle>/capture-supersession-approval.json, "
                        "bound by hash to both captures. Both attempts are "
                        "preserved; only the designation moves.")
    r.add_argument("--reason", default="",
                   help="why the current authoritative capture is being "
                        "invalidated, or why this attempt was retried.")
    r.add_argument("--zero-findings", dest="zero_findings", action="store_true",
                   help="assert that the reviewer reported no findings. "
                        "Required when the output contains no finding blocks: "
                        "absence must never be read as zero.")
    r.set_defaults(fn=cmd_record)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    try:
        return args.fn(args)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
