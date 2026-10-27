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

# For _this_repository() only. The fixtures need to know which repository
# this checkout points at, so that the positive controls agree with it and
# the negative ones can disagree deliberately. Asked of the checker rather
# than written down here: a constant would be wrong in anybody else's clone,
# and the two would then disagree about the thing being tested.
sys.path.insert(0, str(SRC))
import exit_criteria  # noqa: E402

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
              digest: str | None = None,
              dev_run: bool = False,
              no_controller: bool = False) -> tuple[Path, str]:
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

        # SELF-F31. EC-4 now asks the controller whether the run a named
        # cycle belongs to is a protocol run, so the controller has to be
        # here for that question to be asked of the real rule rather than of
        # a stub written to match the matcher.
        #
        # Four files, which is loop_state.py and what it imports. None of
        # them is a test_*.py, so EC-2's glob is untouched and these fixtures
        # do not suddenly start running suites.
        if dev_run:
            if not no_controller:
                for mod in ("loop_state.py", "cycle_projection.py",
                            "run_pins.py", "authority.py"):
                    shutil.copy2(SRC / mod, t / "scripts" / mod)
            # A run marked exactly as the three real ones are, with one
            # cycle directory so the "names a cycle that does not exist"
            # check above it passes and this one is what the item reaches.
            _cyc = t / "runs" / "DEV-001" / "plan-review" / "cycle-01"
            _cyc.mkdir(parents=True)
            (_cyc / "codex-output-raw.md").write_text(
                "X01-F01 was examined here.\n", encoding="utf-8")
            (t / "runs" / "DEV-001" / "run.json").write_text(json.dumps({
                # A plain hyphen where the real records carry an em dash.
                # run_pins.run_kind reads the marker, not the punctuation,
                # and this suite configures no console, so a non-ASCII
                # literal here is a file that cannot print itself on a
                # Windows code page. test_encoding_discipline.py caught it
                # on the first push.
                "bootstrap_review": "EXEMPT - BOOTSTRAP / DEVELOPMENT "
                                    "EVIDENCE, NOT_A_PROTOCOL_CYCLE",
                "mc1_enforcement": "CONVENTION_ONLY",
                "max_cycles": 4,
            }, indent=2), encoding="utf-8")

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

        # An origin, because since 20 October EC-4 asks which repository a
        # run belongs to and answers it from this checkout's remote. A
        # fixture with no remote is a repository that cannot say who it is,
        # which is a real state and a different one from the state these
        # controls are about: every one of them reported "repository is not
        # established" and none reached the thing it was testing.
        #
        # The remote names the repository the fixtures claim to be, taken
        # from the real checkout rather than written down, so these controls
        # pass in anybody's clone and not only in this one.
        _origin = f"https://github.com/{exit_criteria._this_repository()}.git"
        for args in (("init", "-q"), ("config", "user.email", "t@t"),
                     ("config", "user.name", "t"),
                     ("remote", "add", "origin", _origin),
                     ("add", "-A"),
                     ("commit", "-qm", "fixture")):
            subprocess.run(["git", "-C", str(t), *args], capture_output=True)
        head = subprocess.run(["git", "-C", str(t), "rev-parse", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8").stdout.strip()
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
                           cwd=str(t), capture_output=True, text=True, encoding="utf-8")
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

    # SELF-F31, 27 October. The gap that made the four checks around this one
    # insufficient together.
    #
    # Every other test EC-4 applies to a named cycle is true of a development
    # cycle: the reference has the right shape, the directory exists, the
    # cycle passes MC-2 (all twelve real ones do, EC-3 reports it on every
    # run), and the preserved review names the item. So writing
    # "BOOTSTRAP-003/cycle-04" into the field would have moved this condition
    # to PASS on evidence Alex Zamurko ruled on 10 September can never count
    # as authoritative.
    #
    # Found by a reviewer pushing back on a claim rather than by anything
    # failing: the claim was that the field can only be filled by a protocol
    # cycle, and the honest answer was that nothing enforced it.
    t, _ = build(blocking=examined("DEV-001/cycle-01"), dev_run=True)
    refuses("a cycle from a run marked NOT_A_PROTOCOL_CYCLE is not an "
            "independent examination",
            run(t), "EC-4", "NOT_A_PROTOCOL_CYCLE")

    # The half the first version of that check got wrong, named by a
    # reviewer the same afternoon.
    #
    # Matching the controller's refusal text refuses a development run and
    # lets every other outcome through. Here the cycle directory exists and
    # the controller is absent, so there is no refusal to match and no
    # classification either. The old form read that as "not development" and
    # carried on; a condition about independent verification must treat not
    # established as not acceptable.
    t, _ = build(blocking=examined("DEV-001/cycle-01"), dev_run=True,
                 no_controller=True)
    refuses("a cycle whose run classification cannot be established is "
            "refused, not waved through",
            run(t), "EC-4", "not established as a protocol cycle")

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
                 api_sha: str = "", api_conclusion: str = "",
                 api_job: str = "sweep",
                 # The repository, on both sides, so a control can make the
                 # record and GitHub's reply disagree about whose run it was,
                 # and another can make them agree on a repository that is
                 # not this one.
                 repo: str = "", api_repo: str = "") -> None:
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

        # The repository this checkout actually points at, so the positive
        # controls pass for the reason they claim rather than because the
        # check was not reached. Read from git rather than written in, since
        # a constant here would be wrong in anybody else's clone.
        _mine = exit_criteria._this_repository() or "owner/repo"
        _r = _raw("run", {"head_sha": api_sha or commit,
                          "html_url": "https://example.invalid",
                          "repository": {"full_name": api_repo or repo
                                         or _mine},
                          "status": "completed", "conclusion": "success"})
        # api_job exists so a control can make the reply contain a different
        # job from the one the record names. The record always says "sweep";
        # changing what GitHub replied is the only way to test that half.
        _j = _raw("jobs", {"jobs": [{"name": api_job,
                                     "conclusion": api_conclusion
                                     or "success"}]})
        (d / "execution-evidence.json").write_text(json.dumps({
            "schema": "execution-evidence/2",
            "runs": [{
                "run_id": "99", "url": "https://example.invalid",
                "commit": commit, "job": "sweep", "conclusion": "success",
            "repository": repo or _mine,
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

    # The other side of the same refusal, and the one it got wrong. SELF-F29.
    #
    # A sweep exercises far more than the blocking list: run 40112505177 names
    # 87 repairs, of which five are blocking. Declaring one of the other 82 is
    # a true claim its output plainly supports. The refusal was computed by
    # subtracting the blocking-filtered set, so every one of those was
    # reported as coverage the output does not support, and the report would
    # have been read as a problem with the run. Without this control the
    # refusal above is satisfied by a check that rejects any claim outside the
    # blocking list, which is not what it is named for.
    t, head = build()
    evidence(t, head, ["X01-F01", "Z09-F02"],
             body="  [caught] X01-F01  a repair\n"
                  "  [caught] Z09-F02  a repair nobody classified as blocking\n")
    out = block(run(t), "EC-4")
    # The identifier carries the mutation's expected text. SELF-F15b: 86 of
    # the 87 entries match on prose, so an edit to a message that reads badly
    # silently stops a repair being watched. This one matches on a token that
    # exists for no other purpose and that nobody will reword.
    if "declared coverage its output does not support" in out:
        failures.append("[EC4-COVERAGE] a declared finding the output names "
                        "was reported as unsupported\nbecause it is not on "
                        "the blocking list. The output is what the message "
                        "is about:\n" + out)
    elif "were exercised by" not in out:
        failures.append("[EC4-COVERAGE] declaring a non-blocking finding the "
                        "output names stopped the\nblocking item from being "
                        "counted:\n" + out)
    else:
        ok("a declared finding the output names is supported, whether or not "
           "it is blocking")

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

    # ---- Alex Zamurko, 16 October 2026 ----
    #
    # He listed the negative cases EC-4 should have by name: wrong repository,
    # wrong commit, wrong job, wrong conclusion, missing or altered log, and
    # coverage the output does not support. Five of those were above already.
    #
    # This is the sixth. The refusal for it was written on 15 October and
    # nothing ever exercised it, so whether it fires was an argument from
    # reading the source. A record naming a job that is not in the reply is
    # how a green run from a different workflow gets cited for a repair that
    # workflow never touched.
    t, head = build()
    evidence(t, head, ["X01-F01"], api_job="docker")
    refuses("a record naming a job GitHub's reply does not contain",
            run(t), "EC-4", "contains no job named")

    # ---- the wrong repository, which is the last of the six he named ----
    #
    # Alex Zamurko, 16 October 2026, listing what EC-4 should refuse: "wrong
    # repository, wrong commit, wrong job, wrong conclusion, missing or
    # altered log, unsupported finding coverage." Five were written then and
    # this was not, for four days, while the condition reported PASS.
    #
    # Two ways it goes wrong and they are different. The record and the reply
    # can disagree about whose run it was, which is a record describing
    # something that did not happen. Or they can agree perfectly on a
    # repository that is not this one, which is a real run, genuinely green,
    # independently executed, belonging to somebody else.
    t, head = build()
    evidence(t, head, ["X01-F01"], api_repo="someone-else/their-fork")
    refuses("a record whose repository GitHub's own reply contradicts",
            run(t), "EC-4", "GitHub's own reply says")

    # The second is the dangerous one. A fork shares commits, so the commit
    # matches. Workflows get copied, so the job name matches. The conclusion
    # is genuine because the run genuinely succeeded. Every other check in
    # EC-4 passes on it.
    t, head = build()
    evidence(t, head, ["X01-F01"], repo="someone-else/their-fork",
             api_repo="someone-else/their-fork")
    refuses("a genuine green run in somebody else's repository",
            run(t), "EC-4", "A fork shares")

    # SELF-F30. The same comparison has a second cause, and until today the
    # message named only the first.
    #
    # Transferring this repository to an organisation moves the remote while
    # GitHub's preserved replies go on naming the owner at the time of the
    # run. Every record in the history then disagrees with the checkout at
    # once, EC-4 falls to no usable evidence, and the only explanation
    # offered is a fork. The fixture is the same one as above, because the
    # two situations are the same comparison; what this asks is whether the
    # refusal tells a reader which of them they are in and what to do.
    t, head = build()
    evidence(t, head, ["X01-F01"], repo="someone-else/their-fork",
             api_repo="someone-else/their-fork")
    refuses("a repository that moved reads as a fork unless the refusal "
            "says otherwise",
            run(t), "EC-4", "transferred or renamed")

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
                           capture_output=True, text=True, encoding="utf-8").stdout.strip()
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
