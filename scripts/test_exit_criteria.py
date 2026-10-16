#!/usr/bin/env python3
"""Controls for the exit-criteria checker.

    python scripts/test_exit_criteria.py

Exit 0 = thin evidence cannot produce a pass.

Why this file exists
--------------------
`scripts/exit_criteria.py` is the tool the bootstrap exit decision is read
from, and until today it had no controls at all. It was written on 10 October
and found two defects in itself on its first two runs, both of the kind it
exists to catch: one condition counted a list and called that a pass, another
named the alarming cause when it could not distinguish two.

BOOTSTRAP-003 cycle 04 found more, and Alex Zamurko set the requirement:

    "Each exit check must establish its stated requirements or return
     CANNOT_ESTABLISH. Negative tests must prove incomplete evidence cannot
     produce PASS. Preserve the frozen criteria."

The second sentence is what this file is. Every control below hands the
checker evidence that is incomplete in one particular way, and requires the
condition under test to report anything other than PASS.

What this file does NOT cover, said plainly
-------------------------------------------
EC-1's per-run convergence check and EC-3's cycle, ledger and package checks
lean on machinery that `test_ledger.py` and `test_approval_package.py` already
fixture in depth. Rebuilding that here would be a second implementation of the
same fixtures, free to drift from the first, and this layer has already
produced that defect twice elsewhere.

So the fixture below holds no runs. Those checks are skipped rather than
faked, and the coverage here is the three the cycle 04 reviewer called
weakest: the frozen-criteria guard, EC-2's reading of a sweep, and EC-4's
validation of an examination reference, plus EC-1's open-defect condition.

A control file that implies completeness it does not have is the same defect
as everything else we have been chasing.

A note on the fixture
---------------------
`exit_criteria.py` resolves the repository from its own location, not from the
working directory, so the script is copied into each fixture and run from
there. Running the real script with cwd set to a fixture reads the real
repository instead, which is the trap already recorded in
`test_approval_package.py`.
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

# One blocking item, so EC-1 and EC-4 have something to say. Each control
# overrides the part it is about.
BLOCKING = {
    "schema": "blocking-defects/1",
    "ruled_by": "fixture",
    "blocking": {
        "X01-F01": {
            "where": "fixture",
            "condition": "EC-1",
            "why": "fixture",
            "repair_landed": "2026-10-01",
            "independently_examined_in_cycle": None,
        }
    },
    "not_blocking": {},
}

REGISTER = {
    "schema": "implementer-disclosed/1",
    "purpose": "fixture",
    "states": {"OPEN": "disclosed, not repaired"},
    "entries": {},
}


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def ok(m: str) -> None:
        print(f"  [ok] {m}")

    def build(blocking: dict | None = None,
              digest: str | None = None) -> tuple[Path, str]:
        """A minimal repository the checker can run against.

        Returns the root and its HEAD commit. It is a real git repository
        because EC-2 binds a sweep to a commit; a fixture without one would
        exercise the "HEAD could not be resolved" path instead of the paths
        under test.
        """
        t = Path(tempfile.mkdtemp(prefix="exit-")).resolve()
        made.append(t)
        for d in ("scripts", "specs", "registers", "_probe"):
            (t / d).mkdir()

        shutil.copy2(SRC / "exit_criteria.py",
                     t / "scripts" / "exit_criteria.py")

        doc = t / "specs" / "BOOTSTRAP-EXIT-CRITERIA.md"
        doc.write_text("# fixture criteria\n", encoding="utf-8")
        real = hashlib.sha256(doc.read_bytes()).hexdigest()
        (t / "specs" / "BOOTSTRAP-EXIT-CRITERIA.sha256").write_text(
            f"{digest or real}  BOOTSTRAP-EXIT-CRITERIA.md\n",
            encoding="utf-8")

        (t / "specs" / "blocking-defects.json").write_text(
            json.dumps(blocking if blocking is not None else BLOCKING,
                       indent=2), encoding="utf-8")
        (t / "registers" / "implementer-disclosed.json").write_text(
            json.dumps(REGISTER, indent=2), encoding="utf-8")

        for args in (("init", "-q"), ("config", "user.email", "t@t"),
                     ("config", "user.name", "t"), ("add", "-A"),
                     ("commit", "-qm", "fixture")):
            subprocess.run(["git", "-C", str(t), *args], capture_output=True)
        head = subprocess.run(["git", "-C", str(t), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        return t, head

    def sweep(t: Path, text: str) -> None:
        """Write the sweep log after the commit, deliberately.

        EC-2 refuses a sweep older than the last change to the code it covers,
        and that check runs before the ones these controls are about. Writing
        the file after the commit keeps it fresh, so each control exercises
        the condition it names instead of the staleness guard.
        """
        (t / "_probe" / "full-sweep.txt").write_text(text, encoding="utf-8")

    def run(t: Path) -> str:
        r = subprocess.run([sys.executable,
                            str(t / "scripts" / "exit_criteria.py")],
                           cwd=str(t), capture_output=True, text=True)
        return r.stdout + r.stderr

    def block(out: str, cid: str) -> str:
        """The one condition's section of the report.

        Checked per condition rather than over the whole output, because
        another condition passing says nothing about this one.
        """
        keep, taking = [], False
        for ln in out.splitlines():
            if re.match(r"^EC-\d", ln):
                taking = ln.startswith(cid + " ")
            if taking:
                keep.append(ln)
        return "\n".join(keep)

    def tail(out: str, n: int = 10) -> str:
        return "\n".join(out.strip().splitlines()[-n:])

    def refuses(label: str, out: str, cid: str, needle: str) -> None:
        """The named condition must say this, and must not report PASS."""
        b = block(out, cid)
        if not b:
            failures.append(f"{label}: {cid} reported nothing at all:\n"
                            + tail(out))
        elif needle.lower() not in b.lower():
            failures.append(f"{label}: expected {cid} to say {needle!r}, "
                            f"got:\n{b}")
        elif "machine checks: PASS" in b:
            failures.append(f"{label}: {cid} reported PASS on evidence that "
                            f"is incomplete:\n{b}")
        else:
            ok(label)

    def halts(label: str, out: str, needle: str) -> None:
        """The run must stop before any condition is reported."""
        if needle.lower() not in out.lower():
            failures.append(f"{label}: expected {needle!r}, got:\n{tail(out)}")
        elif re.search(r"^EC-\d", out, re.M):
            failures.append(f"{label}: conditions were reported anyway, so "
                            f"the guard did not stop the run:\n{tail(out)}")
        else:
            ok(label)

    print("exit criteria, negative controls")

    # ---- the frozen criteria ----
    #
    # A document that says FROZEN and can be edited without consequence says
    # nothing. These two are what make the word mean something.
    t, _ = build(digest="0" * 64)
    halts("a changed criteria document stops the run entirely",
          run(t), "the exit criteria have changed since they were frozen")

    t, _ = build()
    (t / "specs" / "BOOTSTRAP-EXIT-CRITERIA.sha256").unlink()
    halts("no recorded digest stops the run entirely",
          run(t), "no recorded digest for the exit criteria")

    # ---- EC-1 ----
    #
    # The defect this checker shipped with on 10 October: the condition
    # counted the blocking defects and called that a pass, without asking
    # whether any of them were closed.
    t, _ = build()
    refuses("blocking defects nobody has examined cannot pass EC-1",
            run(t), "EC-1", "blocking defect(s) are still open")

    # ---- EC-2, the three the cycle 04 reviewer named ----
    #
    # "A recent log containing one [caught] and no recognized failure marker
    #  can pass the sweep check."
    t, head = build()
    sweep(t, "  [caught] A01-F01  something\n")
    refuses("a sweep that does not say which commit it examined",
            run(t), "EC-2", "does not say which commit it examined")

    t, head = build()
    sweep(t, "  [caught] A01-F01  something\n\n"
             f"  swept commit {'b' * 40}\n"
             "  mutation set holds 3; this run looked at 3\n")
    refuses("a sweep of a different commit is not evidence about this one",
            run(t), "EC-2", "examined a different commit")

    t, head = build()
    sweep(t, "  [caught] A01-F01  something\n\n"
             f"  swept commit {head}\n"
             "  mutation set holds 58; this run looked at 4\n")
    refuses("an interrupted sweep establishes nothing about what it skipped",
            run(t), "EC-2", "looked at 4 of 58")

    # The positive, without which the three above would be satisfied by a
    # checker that refused every sweep ever written.
    t, head = build()
    sweep(t, "  [caught] A01-F01  something\n\n"
             f"  swept commit {head}\n"
             "  mutation set holds 1; this run looked at 1\n")
    out = block(run(t), "EC-2")
    if "go red when removed" not in out:
        failures.append("a complete sweep of the current commit was not "
                        "accepted, so the three refusals above prove "
                        "nothing:\n" + out)
    else:
        ok("a complete sweep of this commit is accepted, so the refusals "
           "above are not refusing everything")

    # SELF-F11, and the sharpest of the sweep controls, because the content
    # below is perfect. The same bytes in UTF-8 produce a pass two controls
    # above. A reader that cannot decode its evidence has not found an empty
    # result; it has found an answer it cannot read.
    t, head = build()
    (t / "_probe" / "full-sweep.txt").write_text(
        "  [caught] A01-F01  something\n\n"
        f"  swept commit {head}\n"
        "  mutation set holds 1; this run looked at 1\n",
        encoding="utf-16")
    refuses("a sweep the checker cannot decode is unreadable, not empty",
            run(t), "EC-2", "the recorded sweep cannot be read")

    # ---- EC-4, the row the reviewer was bluntest about ----
    #
    # "Any nonempty cycle reference passes. This function neither validates
    #  the referenced cycle nor checks the reviewer quotation."
    def examined(ref) -> dict:
        b = json.loads(json.dumps(BLOCKING))
        b["blocking"]["X01-F01"]["independently_examined_in_cycle"] = ref
        return b

    t, _ = build(blocking=examined("yes, looked at it"))
    refuses("a reference that is not a cycle does not count as examined",
            run(t), "EC-4", "the examination reference is not a cycle")

    # The shape and the tail are two separate things to get wrong, and a
    # reference can have the right number of parts and still name no cycle.
    t, _ = build(blocking=examined("BOOTSTRAP-003/plan-review"))
    refuses("a reference of the right shape with the wrong tail",
            run(t), "EC-4", "the examination reference is not a cycle")

    t, _ = build(blocking=examined("BOOTSTRAP-009/cycle-07"))
    refuses("a reference to a cycle that does not exist",
            run(t), "EC-4", "names a cycle that does not exist")

    t, _ = build(blocking=examined(None))
    last = run(t)
    refuses("an unexamined item is reported, not quietly skipped",
            last, "EC-4", "no reviewer has examined its repair")

    # ---- EC-4's execution evidence ----
    #
    # Alex Zamurko, 13 October 2026: "The inspected implementation still adds
    # CANNOT_ESTABLISH for independent execution unconditionally. Replace this
    # with validation of actual GitHub execution evidence, linked to the exact
    # commit and reviewed finding."
    #
    # So the four controls below are the four answers it now has to tell
    # apart, and the fifth is the one that makes the other four worth having.
    refuses("no recorded evidence is said to be none, not weak",
            last, "EC-4", "no independent execution evidence has been recorded")

    def evidence(t: Path, commit: str, covers: list, body: str | None = None,
                 digest: str | None = None, write_log: bool = True,
                 purpose: str = "repair_verification",
                 api_sha: str = "", api_conclusion: str = "") -> None:
        # The log mentions what it covers by default, because since 15 October
        # coverage is read out of the preserved output rather than out of the
        # declaration. A body that named nothing would make every positive
        # control here fail for the right reason and the wrong one.
        if body is None:
            body = "".join(f"  [caught] {c}  a repair\n" for c in covers)
        d = t / "evidence"
        d.mkdir(exist_ok=True)
        # newline="\n" and the digest taken from the file rather than from the
        # string. write_text translates "\n" to "\r\n" on Windows, so the
        # first version of this hashed four bytes and wrote five, and the
        # positive control failed with "the preserved log no longer matches
        # the digest". That is the defect .gitattributes pins four directories
        # against, arriving in the fixture written to check for it.
        real = hashlib.sha256(body.encode()).hexdigest()
        if write_log:
            (d / "run.txt").write_text(body, encoding="utf-8", newline="\n")
            real = hashlib.sha256((d / "run.txt").read_bytes()).hexdigest()

        # GitHub's replies, preserved as the recorder preserves them. Since
        # 15 October EC-4 checks the entry against these rather than reading
        # the entry's own fields, so a fixture without them is testing the
        # previous design. api_sha and api_conclusion exist so a control can
        # make the record contradict the reply.
        def _raw(name: str, payload: dict) -> dict:
            p = d / f"99-{name}.json"
            p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
            return {"path": f"evidence/99-{name}.json",
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

        _r = _raw("run", {"head_sha": api_sha or commit,
                          "html_url": "https://example.invalid",
                          "status": "completed", "conclusion": "success"})
        _j = _raw("jobs", {"jobs": [{"name": "sweep",
                                     "conclusion": api_conclusion
                                     or "success"}]})
        (d / "execution-evidence.json").write_text(json.dumps({
            "schema": "execution-evidence/2",
            "runs": [{
                "run_id": "99", "url": "https://example.invalid",
                "commit": commit, "job": "sweep", "conclusion": "success",
                "log": "evidence/run.txt",
                "log_sha256": digest or real,
                "covers": covers,
                "purpose": purpose,
                "api_run": _r, "api_jobs": _j,
            }],
        }, indent=2), encoding="utf-8")

    t, head = build()
    evidence(t, "c" * 40, ["X01-F01"])
    refuses("evidence from a different commit is not evidence about this one",
            run(t), "EC-4", "have no usable execution evidence")

    t, head = build()
    evidence(t, head, ["SOMETHING-ELSE"])
    refuses("evidence that does not name the item does not cover it",
            run(t), "EC-4", "have no usable execution evidence")

    t, head = build()
    evidence(t, head, ["X01-F01"], write_log=False)
    refuses("a recorded run whose preserved log is gone",
            run(t), "EC-4", "have no usable execution evidence")

    t, head = build()
    evidence(t, head, ["X01-F01"], digest="0" * 64)
    refuses("a preserved log that no longer matches its digest",
            run(t), "EC-4", "have no usable execution evidence")

    # And the positive. Without it, every refusal above is satisfied by a
    # condition that refuses all evidence forever, which is the exact defect
    # Alex Zamurko asked to have removed.
    t, head = build()
    evidence(t, head, ["X01-F01"])
    out = block(run(t), "EC-4")
    if "were exercised by" not in out:
        failures.append("evidence naming the item, on this commit, with its "
                        "log intact was not\naccepted. The refusals above "
                        "then prove nothing, and the condition still\ncannot "
                        "be satisfied:\n" + out)
    elif "adequate for a blocking item" not in out:
        failures.append("EC-4 accepted the evidence without reserving the "
                        "adequacy judgement, which\nis the half that is not "
                        "the checker's to make")
    else:
        ok("evidence on this commit, naming the item, with its log intact is "
           "accepted, and the adequacy judgement is still reserved")

    # ---- Alex Zamurko's three amendments of 15 October ----
    #
    # "Verify the claimed finding coverage against preserved execution
    #  results, not just the submitter's `covers` field."
    #
    # The log here says nothing about the item. Before this, typing the name
    # into `covers` was the whole of the coverage check.
    t, head = build()
    evidence(t, head, ["X01-F01"], body="a sweep that mentions nothing\n")
    refuses("coverage claimed by the record and absent from its output",
            run(t), "EC-4", "declared coverage its output does not support")

    # "Preserve failure-run evidence separately from successful
    #  repair-verification evidence."
    #
    # SELF-F08's red run proves the pipeline reports failure. Letting it count
    # as a repair being exercised would make the thing built to demonstrate
    # failure into proof of success.
    t, head = build()
    evidence(t, head, ["X01-F01"], purpose="failure_demonstration")
    refuses("a deliberately failing run is not evidence that a repair holds",
            run(t), "EC-4", "have no usable execution evidence")

    # "It does not independently verify that the claimed GitHub run, job,
    #  conclusion and coverage are genuine... A locally authored evidence
    #  record with a matching log digest can therefore satisfy the mechanical
    #  check without demonstrating that GitHub independently executed the
    #  named repair."
    #
    # Both halves of that: a record claiming a commit GitHub's own reply
    # contradicts, and a record calling a job successful that GitHub's reply
    # calls failed. Each would have passed every check before 15 October.
    t, head = build()
    evidence(t, head, ["X01-F01"], api_sha="d" * 40)
    refuses("a record whose commit GitHub's own reply contradicts",
            run(t), "EC-4", "GitHub's own reply")

    t, head = build()
    evidence(t, head, ["X01-F01"], api_conclusion="failure")
    refuses("a record calling a job successful that GitHub calls failed",
            run(t), "EC-4", "GitHub's reply says")

    # "Match evidence to an explicitly frozen candidate SHA, not
    #  indiscriminately to the latest repository HEAD... Committing evidence
    #  after the tested commit changes HEAD, potentially invalidating the
    #  evidence it records."
    #
    # This is the circularity, reproduced. The evidence describes the frozen
    # candidate; a later commit moves HEAD; the evidence must survive it. The
    # same control run without the frozen-candidate file is the one two
    # controls above, which correctly refuses when HEAD has moved.
    t, head = build()
    evidence(t, head, ["X01-F01"])
    (t / "specs" / "frozen-candidate.json").write_text(json.dumps({
        "schema": "frozen-candidate/1", "commit": head}, indent=2),
        encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(t), "commit", "-qm", "record the "
                    "evidence, which moves HEAD"], capture_output=True)
    moved = subprocess.run(["git", "-C", str(t), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    out = block(run(t), "EC-4")
    if moved == head:
        failures.append("the fixture did not actually move HEAD, so the "
                        "circularity below is\nnot being exercised")
    elif "were exercised by" not in out:
        failures.append(
            "evidence about the frozen candidate stopped counting the moment "
            "it was\ncommitted, which is the circularity Alex Zamurko "
            "named: recording the\nevidence destroys it:\n" + out)
    else:
        ok("evidence survives the commit that records it, because it is bound "
           "to the frozen candidate and not to HEAD")

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("  incomplete evidence does not produce a pass, and complete "
          "evidence still does")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
