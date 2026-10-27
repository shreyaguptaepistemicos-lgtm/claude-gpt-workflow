#!/usr/bin/env python3
"""Controls for the blocking-defect reconciler.

    python scripts/test_reconcile_blocking.py

Exit 0 = every control fired.

The property that matters here is a refusal, so most of these check that
something does NOT happen. That shape needs care: a program that crashed on
startup would also fail to write a file, and would satisfy a careless version
of the first control below. So each refusal is paired with evidence that the
program got far enough to have refused on purpose.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.error  # noqa: F401  (kept parallel with the other suites)
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parent
REPO = SRC.parent
sys.path.insert(0, str(SRC))

import reconcile_blocking as rb  # noqa: E402

CLASSIFICATION = REPO / "specs" / "blocking-defects.json"

# Issue 8. specs/FIXTURE-SOURCES.md for the rule and why the absent case has
# to be stated.
FIXTURE_SOURCES = {
    # specs/ is not a RECORD_ROOT, so nothing required this to be declared,
    # and the absent case is exactly the one that bit: the export carried
    # the suite and not the file, and the first run was a traceback.
    # Declared anyway. A rule that only covers four directories does not
    # make the fifth case stop existing.
    "specs": "record: specs/blocking-defects.json is read to take its digest "
             "before and after a --write run, which is how the refusal is "
             "shown to be a refusal rather than a crash. The real file, "
             "because a copy would prove nothing about the file the tool "
             "actually opens. absent: reports CANNOT_ESTABLISH naming the "
             "path and returns 1. It does not pass for the absence, because "
             "a control whose subject is gone has not run",
    "runs": "record: the control for a failed controller names a review "
            "path under runs/ that deliberately does not exist, to check "
            "that the failure is reported with the controller's own reason "
            "rather than as an absence. Nothing is read from a real run; "
            "the path is constructed so it cannot be. absent: the control "
            "wants the path missing and would be testing the same thing if "
            "runs/ were gone entirely, so this suite neither needs the "
            "directory nor passes because of it. The controls that do read "
            "real records go through reconcile_blocking.py itself, which "
            "refuses rather than passing when a review cannot be walked",
}


def main() -> int:
    failures: list[str] = []
    seen: set[str] = set()

    def ok(msg: str) -> None:
        print(f"  [ok] {msg}")

    def fail(cid: str, msg: str) -> None:
        if cid in seen:
            failures.append(f"[RB-DUP] {cid} is used by two controls")
        seen.add(cid)
        failures.append(f"[{cid}] {msg}")

    print("blocking-defect reconciler")

    # ---- the refusal, and that it is a refusal rather than a crash ----
    #
    # Run against the real repository on purpose. The whole claim is that
    # --write cannot alter the classification file, and the only way to check
    # that honestly is to give it the real file and the real flag. If this
    # control ever fails, it fails loudly and git restores the file.
    # The classification file may genuinely not be there. The review-workflow
    # export carried everything this suite needs except this, and the first
    # run in the export died on read_bytes with a traceback: no [ok] lines,
    # no FAIL lines, and a suite that reads as broken machinery rather than
    # as one whose subject is absent. That is the shape issue 8 is about, and
    # it arrived in the suite whose declaration claims to have thought about
    # it. Found 27 October by running the export rather than by building it.
    if not CLASSIFICATION.is_file():
        print("  [CANNOT_ESTABLISH] there is no "
              "specs/blocking-defects.json here, so the")
        print("  refusal this suite exists to check cannot be exercised.")
        print("  Not a pass: the control did not run.")
        return 1
    before = hashlib.sha256(CLASSIFICATION.read_bytes()).hexdigest()
    r = subprocess.run([sys.executable, str(SRC / "reconcile_blocking.py"),
                        "--write"],
                       capture_output=True, text=True, encoding="utf-8",
                       cwd=str(REPO))
    after = hashlib.sha256(CLASSIFICATION.read_bytes()).hexdigest()
    out = (r.stdout or "") + (r.stderr or "")

    seen.add("RB-NOWRITE")
    if after != before:
        failures.append("[RB-NOWRITE] --write altered "
                        "specs/blocking-defects.json. It must not: the field "
                        "it would\n      fill is read by EC-1 and EC-4, and "
                        "everything this program can see is\n      "
                        "development evidence. Restore the file from git.")
    elif "--write refused" not in out:
        # The pairing that makes the digest check mean something. A program
        # that died at import would leave the file untouched too.
        failures.append("[RB-NOWRITE] the file is unchanged and the program "
                        "never said it refused, so\n      this control "
                        "cannot tell a deliberate refusal from a crash:\n"
                        + "\n".join(out.strip().splitlines()[-6:]))
    elif r.returncode == 0:
        failures.append("[RB-NOWRITE] it refused and exited 0. A refusal that "
                        "reports success is how a\n      caller carries on as "
                        "though the work was done.")
    else:
        ok("--write refuses, says so, and exits non-zero")

    # ---- the refusal names the ruling it rests on ----
    #
    # Without this the message could become "not supported yet", which reads
    # as a missing feature rather than a decision, and somebody would
    # implement it.
    seen.add("RB-WHY")
    if "NOT_A_PROTOCOL_CYCLE" not in out:
        failures.append("[RB-WHY] the refusal does not name the marking it "
                        "rests on, so a reader cannot\n      tell a ruling "
                        "from an unimplemented feature")
    # Whitespace-normalised before matching. The first version looked for the
    # contiguous string and failed on output that wrapped "a protocol" and
    # "cycle" onto separate lines, which is a control failing for a reason
    # other than the one it is named for, in a suite about exactly that.
    elif "protocol cycle" not in " ".join(out.lower().split()):
        failures.append("[RB-WHY] the refusal does not say what WOULD close "
                        "these items, which is the\n      one thing the "
                        "reader needs next")
    else:
        ok("the refusal names the ruling and what would actually close them")

    # ---- it got an answer at all, which means it passed --development ----
    #
    # The controller refuses these runs outright without that flag, and the
    # first version of this program did not pass it and reported seven
    # identical "printed nothing" lines.
    seen.add("RB-WALKED")
    if "development evidence:" not in out:
        failures.append("[RB-WALKED] no walk was reported. Without "
                        "--development the controller refuses\n      these "
                        "runs and this program has nothing to say")
    else:
        ok("all three reviews were walked as development evidence")

    # ---- a controller that fails is reported with its reason ----
    #
    # The bug this replaced: walk() read stdout, ignored stderr, and reported
    # "printed nothing (exit 2)" seven times while the controller had written
    # exactly why on the stream nobody looked at.
    seen.add("RB-STDERR")
    _d, _err = rb.walk(REPO / "runs" / "does-not-exist" / "plan-review")
    if _d is not None:
        failures.append("[RB-STDERR] a review that does not exist produced a "
                        "walk")
    elif "and said nothing" in _err or len(_err) < 40:
        failures.append(f"[RB-STDERR] the failure was reported without the "
                        f"controller's own reason: {_err!r}")
    else:
        ok("a failed controller is reported with what it actually said")

    # ---- demonstrated_in is restricted to the walk's valid cycles ----
    #
    # The reason loop_state.py gained a valid_cycles key. A DEMONSTRATED in
    # an invalid cycle is exactly what cycle_projection exists to discount,
    # and reading the history without the restriction would hand back the
    # number the walk had already rejected.
    led = {"findings": {"X-01": {"history": [
        {"event": "DEMONSTRATED", "cycle": 2},
        {"event": "DEMONSTRATED", "cycle": 5},
        {"event": "ACCEPT", "cycle": 6},
    ]}}}
    seen.add("RB-VALID")
    if rb.demonstrated_in(led, "X-01", [1, 2, 3]) != 2:
        failures.append("[RB-VALID] the latest DEMONSTRATED inside the valid "
                        "set was not returned")
    elif rb.demonstrated_in(led, "X-01", [1, 3]) is not None:
        failures.append("[RB-VALID] a DEMONSTRATED in a cycle the walk did "
                        "not accept was returned anyway")
    elif rb.demonstrated_in(led, "X-01", [1, 2, 3, 5]) != 5:
        failures.append("[RB-VALID] with both cycles valid the later one was "
                        "not taken")
    elif rb.demonstrated_in(led, "nope", [1, 2]) is not None:
        failures.append("[RB-VALID] a finding not in the ledger produced a "
                        "cycle")
    else:
        ok("a demonstration is read only from cycles the walk accepted")

    # ---- an ACCEPT is not a demonstration ----
    #
    # Cheap to get wrong by scanning history for "the last event in a valid
    # cycle", and an ACCEPT means the reviewer agreed the finding is real,
    # which is the opposite end of the lifecycle from the repair holding.
    seen.add("RB-ACCEPT")
    only_accept = {"findings": {"Y-01": {"history": [
        {"event": "RAISED", "cycle": 1}, {"event": "ACCEPT", "cycle": 1}]}}}
    if rb.demonstrated_in(only_accept, "Y-01", [1, 2, 3]) is not None:
        failures.append("[RB-ACCEPT] an ACCEPT was read as a demonstration")
    else:
        ok("an ACCEPT is not a demonstration")

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        print(f"\n{len(failures)} failure(s)")
        return 1
    print(f"all {len(seen)} control(s) fired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
