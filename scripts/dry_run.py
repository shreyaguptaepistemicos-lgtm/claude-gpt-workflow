#!/usr/bin/env python3
"""A full rehearsal of the protocol, end to end, in a throwaway repository.

    python scripts/dry_run.py
    python scripts/dry_run.py --keep        # leave the directory to inspect

Exit 0 = every step did what the protocol says it should.
Exit 1 = a step did not; the transcript says which and what it printed.

What this is, and what it is not
--------------------------------
Alex Zamurko's sequence puts a full dry run before the first real A.1-E cycle.
This is that: the real commands, in the documented order, against a repository
built for the purpose, printing what an operator would see.

It is not a test suite. The suites ask whether each component refuses what it
should; this asks whether the components compose — whether the thing the runner
freezes is the thing the gate accepts, whether what the ledger records is what
the controller reads, whether the sequence an operator is told to follow gets
from an empty directory to a decision.

**It cannot rehearse the review.** The one step that needs a reviewer is
performed here with a fixture reply written in advance. Every other step is
real. So a clean run says the machinery composes; it says nothing whatever
about whether a review would find anything, and the transcript repeats that at
the end rather than leaving a green result to be read as more than it is.

Nothing outside the temporary directory is touched. It refuses to start if the
path it is given is inside this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent
REPO = SRC.parent

# SELF-F16. This prints box-drawing characters in its section headers, and a
# Windows console is cp1252 by default, which has no character for them. The
# whole rehearsal therefore died with UnicodeEncodeError before its first step,
# on the most common desktop platform, and the only reason it had never been
# seen here is that every shell this was run in had PYTHONUTF8 typed into it.
#
# Found on 16 October while checking the review-workflow export, where this is
# the first command the README tells a reader to run. We would have shipped a
# repository whose headline demonstration crashes on sight.
#
# This is SELF-F12 one layer out. That one was about reading files at the
# locale's mercy; this is about writing to a console at it. The scan written
# for the first covers reads and writes of files and says nothing about stdout,
# which is a limit worth knowing rather than a hole worth hiding.
#
# Guarded because reconfigure is absent on some streams and raises on others,
# and a rehearsal that cannot start because of its own encoding fix would be
# the joke writing itself.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass

COMPONENTS = ("run_review.py", "validate_cycle.py", "bootstrap_gate.py",
              "ledger.py", "loop_state.py", "findings_format.py",
              "cycle_projection.py", "authority.py", "run_pins.py",
              "approval_package.py")

PROTOCOL_BODY = """Rehearsal protocol
Codex uses the following closed finding vocabulary:
MISSING REQUIREMENT
WRONG OWNERSHIP
NONDETERMINISTIC WHERE D POSSIBLE
SEMANTIC STEP TOO BROAD
UNTESTED RULE
CONTRADICTORY IMPLEMENTATION MAPPING

Every finding receives exactly one class.
"""

SPEC_BODY = "Rehearsal specification\n\nR-1 the thing must do the thing\n"

PROMPT_BODY = """# Rehearsal prompt

Review the artifact below and report findings in the §4 block format.

Finding ID: C01-F01
Class: UNTESTED RULE
Requirement ID: R-1
Evidence: ...
Finding: ...
Required correction: ...
"""

# The one step that cannot be real. Written before the run, so that nothing
# here is a reviewer reacting to what it was given.
FIXTURE_REVIEW = """The target hash is {target}.

Finding ID: C01-F01
Class: UNTESTED RULE
Requirement ID: R-1
Evidence: plan/01-PLAN.md states the rule and no control exercises it.
Finding: the rule is asserted and never tested.
Required correction: add a control that fails when the rule is removed.
"""

# A demonstrated repair is reported by absence. There is no "REPAIR
# DEMONSTRATED" status: the only status a review may report against a persistent
# identifier is "REPAIR NOT DEMONSTRATED", so a reviewer that is satisfied
# simply does not raise the finding again.
#
# The first version of this rehearsal wrote "Status: REPAIR DEMONSTRATED" and
# the runner refused it, which is the rehearsal doing its job: the protocol was
# not what the author of this file assumed, and the machinery said so instead of
# accepting it. Left recorded here because the assumption is an easy one.
#
# Note also what must NOT appear below. The runner refuses --zero-findings over
# text carrying finding-ID signals, on the grounds that zero cannot be asserted
# over a review the parser may have failed to read. So a clean review may not
# mention an identifier even in passing.
FIXTURE_REVIEW_2 = """The target hash is {target}.

The plan states the rule and the control that exercises it. Removing the rule
fails that control. Nothing further to report for this cycle.

This review makes no claim that the plan has converged.
"""


# A register built for the rehearsal, not the real one.
#
# SELF-F13 reached here and nothing said so. From 14 October the approval
# package exits non-zero when the implementer-disclosed register cannot be
# read, on Alex Zamurko's ruling that a failed dependency must prevent
# approval. The test fixtures were given a register that day; this rehearsal
# was not, so step 13 began failing and the rehearsal reported the whole
# protocol as broken.
#
# CI runs this on every push and should have caught it within the hour. It did
# not, because CI had been red for the corpus tripwire since the same day, and
# a job that is always red hides whatever breaks next. That is SELF-F10's
# argument arriving a second time, against us.
#
# The first repair copied the live register in from this repository. That made
# the rehearsal pass for a reason it is not entitled to: a rehearsal that
# builds an empty directory and then reaches outside it for a production file
# is no longer rehearsing an empty directory, and it fails the moment the
# repository around it does not happen to carry that file. It did, immediately,
# in a copy of this tree that excludes the registers directory.
#
# So the rehearsal builds its own, as it builds its own protocol, spec, plan and
# reviewer replies. A dict rather than a string of JSON, because a string can be
# malformed and a dict cannot. Two entries rather than none, because the section
# has two branches and a register with no entries exercises neither: one live, so
# the outstanding-disclosure path runs, and one RESOLVED with history, so the
# resolved-tail path runs. The states glossary is present because the package
# reads its definitions from the register rather than restating them, and a
# fixture missing it would exercise a lookup that always misses.
REGISTER_FIXTURE = {
    "schema": "implementer-disclosed/1",
    "purpose": "A fixture register for the rehearsal. Not a record of anything. "
               "The entries below are invented to exercise the approval "
               "package's disclosure section, and name no real defect.",
    "states": {
        "OPEN": "disclosed, not repaired",
        "REPAIRED_UNREVIEWED": "a repair has landed with controls behind it, "
                               "and nobody independent has examined it",
        "REVIEWER_CONFIRMED": "an independent review examined the entry and "
                              "agreed it was a defect",
        "UNVERIFIED": "an independent review examined the repair by reading it "
                      "and did not execute it, so the behaviour it claims is "
                      "supported but not established",
        "RESOLVED": "an independent review examined the repair in a later "
                    "target and found it held",
    },
    "obligation": "Every entry not in RESOLVED must be put to the next "
                  "independent review explicitly, and must appear in any "
                  "approval package built while it is in that state.",
    "entries": {
        "REHEARSAL-SELF-01": {
            "description": "Invented for the rehearsal. A disclosure in a live "
                           "state, present so the approval package's "
                           "outstanding section has something to render.",
            "discovery_source": "Fixture. No reviewer and no agent found this; "
                                "scripts/dry_run.py wrote it.",
            "affected_component": "none, this is a fixture",
            "severity": "none, this is a fixture",
            "state": "REPAIRED_UNREVIEWED",
            "review_cycle": None,
            "proposed_repair": "none required, this is a fixture",
            "required_of_next_review": True,
            "history": [],
        },
        "REHEARSAL-SELF-02": {
            "description": "Invented for the rehearsal. A disclosure in "
                           "RESOLVED, present so the package's resolved tail "
                           "has something to render.",
            "discovery_source": "Fixture. No reviewer and no agent found this; "
                                "scripts/dry_run.py wrote it.",
            "affected_component": "none, this is a fixture",
            "severity": "none, this is a fixture",
            "state": "RESOLVED",
            "review_cycle": None,
            "proposed_repair": "none required, this is a fixture",
            "required_of_next_review": False,
            "history": [
                {
                    "at": "2026-01-01T00:00:00+00:00",
                    "state": "RESOLVED",
                    "by": "rehearsal fixture reviewer",
                    "note": "Not a real ruling by a real reviewer.",
                }
            ],
        },
    },
}


class Failed(Exception):
    pass


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")


def build_repo(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    for n in COMPONENTS:
        shutil.copy2(SRC / n, root / "scripts" / n)
    (root / "specs").mkdir()
    shutil.copy2(REPO / "specs" / "evidence-schema-v1.0.md",
                 root / "specs" / "evidence-schema-v1.0.md")
    for name, body in (("protocol.md", PROTOCOL_BODY), ("spec.md", SPEC_BODY),
                       ("prompt.md", PROMPT_BODY)):
        (root / "specs" / name).write_text(body, encoding="utf-8", newline="\n")
    # See REGISTER_FIXTURE above for why this is built rather than copied.
    (root / "registers").mkdir()
    (root / "registers" / "implementer-disclosed.json").write_text(
        json.dumps(REGISTER_FIXTURE, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (root / "plan").mkdir()
    (root / "plan" / "01-PLAN.md").write_text(
        "# plan\n\nR-1 is implemented in thing.py and tested in test_thing.py\n",
        encoding="utf-8", newline="\n")
    sh("git", "init", "-q", cwd=root)
    sh("git", "config", "user.email", "rehearsal@local", cwd=root)
    sh("git", "config", "user.name", "rehearsal", cwd=root)
    sh("git", "add", "-A", cwd=root)
    sh("git", "commit", "-qm", "rehearsal fixture", cwd=root)


class Transcript:
    def __init__(self) -> None:
        self.n = 0
        self.failed: list[str] = []

    def step(self, title: str) -> None:
        self.n += 1
        print(f"\n─── {self.n}. {title}")

    def ran(self, root: Path, *args: str, expect: int = 0,
            must_say: str = "") -> str:
        cmd = [sys.executable, str(root / "scripts" / args[0]), *args[1:]]
        shown = " ".join(["python", f"scripts/{args[0]}", *args[1:]])
        # Absolute temp paths are noise in a transcript meant to be read as the
        # sequence an operator follows.
        print(f"    $ {shown.replace(str(root) + '/', '').replace(str(root), '.')}")
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8")
        out = (r.stdout + r.stderr).rstrip()
        for line in out.splitlines()[:14]:
            print(f"      {line}")
        if len(out.splitlines()) > 14:
            print(f"      … {len(out.splitlines()) - 14} more lines")
        if r.returncode != expect:
            self.failed.append(
                f"step {self.n} ({shown}) exited {r.returncode}, expected "
                f"{expect}")
        elif must_say and must_say not in out:
            self.failed.append(
                f"step {self.n} ({shown}) exited {expect} but never said "
                f"{must_say!r}")
        return out


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="dry_run.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true",
                    help="leave the rehearsal directory in place")
    a = ap.parse_args()

    root = Path(tempfile.mkdtemp(prefix="dry-run-")).resolve()
    # Refusing rather than trusting the caller: a rehearsal that wrote into the
    # real runs/ tree would put fixture evidence beside real evidence, and the
    # two are indistinguishable once written.
    if REPO in root.parents or root == REPO:
        raise Failed(f"refusing to rehearse inside the repository: {root}")

    print("PROTOCOL REHEARSAL")
    print(f"  directory   {root}")
    print("  everything below runs the real commands against a repository "
          "built for this")
    print("  purpose. Nothing in this repository is touched.")

    t = Transcript()
    try:
        build_repo(root)

        t.step("The gate refuses a real run before any bootstrap review")
        t.ran(root, "bootstrap_gate.py", "check", expect=1,
              must_say="no bootstrap review on record")
        print("      ↑ this is the state the real repository is in today")

        t.step("Initialise a run under the bootstrap exception")
        t.ran(root, "run_review.py", "init", "--run", "REHEARSAL-001",
              "--bootstrap-exempt", "--protocol", "specs/protocol.md",
              "--spec", "specs/spec.md", must_say="initialised")

        t.step("Freeze cycle 01: the runner composes the reviewer's input")
        out = t.ran(root, "run_review.py", "freeze", "--run", "REHEARSAL-001",
                    "--type", "plan", "--prompt", "specs/prompt.md",
                    "--file", "plan/01-PLAN.md", must_say="froze")
        target = ""
        for line in out.splitlines():
            if "target.sha256" in line:
                target = line.split()[-1]
        if not target:
            t.failed.append("step 3 printed no target digest")

        cyc = "runs/REHEARSAL-001/plan-review/cycle-01"
        inp = (root / cyc / "codex-input.md").read_text(encoding="utf-8")
        t.step("The composed input carries the target digest, per V34")
        if target and target in inp:
            print(f"      yes: {target[:16]}… appears in codex-input.md")
        else:
            t.failed.append("step 4: the composed input does not carry the "
                            "target digest")

        t.step("Record the review  [FIXTURE — the only unreal step]")
        print("      The reply below was written before this run. Every other")
        print("      step is the real command.")
        (root / "reply.md").write_text(FIXTURE_REVIEW.format(target=target),
                                       encoding="utf-8", newline="\n")
        t.ran(root, "run_review.py", "record", "--cycle", cyc,
              "--output", "reply.md", "--invocation", "manual")

        t.step("MC-2 gate over the frozen cycle")
        t.ran(root, "validate_cycle.py", cyc, must_say="MC2_CONFORMANCE: PASS")

        review = "runs/REHEARSAL-001/plan-review"
        t.step("Ledger: the finding is raised, accepted, and stays OPEN (§5)")
        t.ran(root, "ledger.py", "raise", "--review", review, "--cycle", "1",
              "--id", "C01-F01", "--class", "UNTESTED RULE",
              "--requirement", "R-1", "--source", "CODEX_REVIEW")
        t.ran(root, "ledger.py", "respond", "--review", review, "--cycle", "1",
              "--id", "C01-F01", "--disposition", "ACCEPT",
              "--note", "will add the control", must_say="still OPEN")
        print("      ↑ ACCEPT does not resolve. §5 gives RESOLVED only once the")
        print("        repair is demonstrated in the NEXT review target.")

        t.step("Controller: one finding open, so the loop continues")
        t.ran(root, "loop_state.py", "--review", review, "--development",
              must_say="CONTINUE")

        t.step("Freeze cycle 02 against the repaired plan")
        (root / "plan" / "01-PLAN.md").write_text(
            "# plan\n\nR-1 is implemented in thing.py and tested in "
            "test_thing.py\nthe control fails when the rule is removed\n",
            encoding="utf-8", newline="\n")
        sh("git", "add", "-A", cwd=root)
        sh("git", "commit", "-qm", "repair", cwd=root)
        out = t.ran(root, "run_review.py", "freeze", "--run", "REHEARSAL-001",
                    "--type", "plan", "--prompt", "specs/prompt.md",
                    "--file", "plan/01-PLAN.md", must_say="froze")
        target2 = ""
        for line in out.splitlines():
            if "target.sha256" in line:
                target2 = line.split()[-1]
        if target and target2 and target == target2:
            t.failed.append("step 9: cycle 02 froze the same digest as cycle "
                            "01, so the repair never reached the target")
        else:
            print(f"      a different target: {target2[:16]}… — V28, every "
                  f"cycle has its own")

        cyc2 = "runs/REHEARSAL-001/plan-review/cycle-02"
        t.step("Record cycle 02  [FIXTURE]")
        (root / "reply2.md").write_text(FIXTURE_REVIEW_2.format(target=target2),
                                        encoding="utf-8", newline="\n")
        t.ran(root, "run_review.py", "record", "--cycle", cyc2,
              "--output", "reply2.md", "--invocation", "manual",
              "--zero-findings")
        print("      ↑ --zero-findings is required: absence has to be asserted,")
        print("        never inferred from a parser that found nothing.")
        t.ran(root, "validate_cycle.py", cyc2, must_say="MC2_CONFORMANCE: PASS")

        t.step("Now the repair can resolve — demonstrated in a later cycle")
        t.ran(root, "ledger.py", "resolve", "--review", review, "--cycle", "2",
              "--id", "C01-F01", "--evidence", "the control exists",
              must_say="RESOLVED")

        t.step("Controller: nothing open, the loop converges")
        t.ran(root, "loop_state.py", "--review", review, "--development",
              must_say="CONVERGED")

        t.step("The §7 package: what a human is asked to decide from")
        t.ran(root, "approval_package.py", "--run", "REHEARSAL-001",
              "--type", "plan", must_say="§7 items present")

        t.step("The gate still refuses, because nobody has approved anything")
        t.ran(root, "bootstrap_gate.py", "check", expect=1,
              must_say="no bootstrap review on record")
        print("      ↑ a full clean loop does not approve itself. The decision")
        print("        is a separate act by a person.")

    finally:
        print()
        if t.failed:
            print(f"REHEARSAL FAILED — {len(t.failed)} step(s)")
            for f in t.failed:
                print(f"  {f}")
        else:
            print("REHEARSAL COMPLETE — the components compose, empty "
                  "directory to decision.")
            print()
            print("  What this did NOT rehearse: the review. Both reviewer "
                  "replies were fixtures")
            print("  written before the run. This says the machinery holds "
                  "together. It says nothing")
            print("  about whether a real review would find anything, and a "
                  "green result here is not")
            print("  evidence that the layer is correct.")
        if a.keep:
            print(f"\n  kept: {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)

    return 1 if t.failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failed as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        sys.exit(1)
