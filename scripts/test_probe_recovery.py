#!/usr/bin/env python3
"""Controls for the mutation probe's crash recovery.

    python scripts/test_probe_recovery.py

Exit 0 = every control fired.

Why this file exists
--------------------
SELF-F02 claimed that a probe run killed mid-mutation is restored from HEAD on
the next run. BOOTSTRAP-003's reviewer showed the claim was false: the recovery
ran `git checkout -- <path>`, which restores from the INDEX, and in a fixture
with different bytes staged it wrote those staged bytes and reported that it
had restored from HEAD.

The repair was mine and so was the defect, and the reason it survived is that
the probe had no controls at all. It is an instrument, preserved in cycle
evidence and read by reviewers, and until now nothing tested it.

The fixture is a throwaway git repository with its own `_probe/`, so the real
repository is never written to.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
REPO = SRC.parent
PROBE = REPO / "_probe" / "mutate_repairs.py"

HEAD_BYTES = b"# committed\nVALUE = 1\n"
STAGED_BYTES = b"# staged, and not what HEAD holds\nVALUE = 2\n"
MUTATED_BYTES = b"# mutated by a run that was killed\nVALUE = 999\n"


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def ok(m: str) -> None:
        print(f"  [ok] {m}")

    print("probe crash recovery")

    def build() -> Path:
        t = Path(tempfile.mkdtemp(prefix="probe-")).resolve()
        made.append(t)
        (t / "scripts").mkdir()
        (t / "_probe").mkdir()
        shutil.copy(PROBE, t / "_probe" / "mutate_repairs.py")
        sh("git", "init", "-q", cwd=t)
        sh("git", "config", "user.email", "t@example.com", cwd=t)
        sh("git", "config", "user.name", "t", cwd=t)
        (t / "scripts" / "subject.py").write_bytes(HEAD_BYTES)
        sh("git", "add", "-A", cwd=t)
        sh("git", "commit", "-qm", "the committed state", cwd=t)
        return t

    def sentinel(t: Path, mutated: bytes) -> None:
        head = sh("git", "rev-parse", "HEAD", cwd=t).stdout.strip()
        (t / "_probe" / ".active-mutation.json").write_text(json.dumps({
            "finding": "a killed run",
            "path": "scripts/subject.py",
            "head": head,
            "mutated": hashlib.sha256(mutated).hexdigest(),
        }, indent=2) + "\n", encoding="utf-8")

    def run_probe(t: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(t / "_probe" / "mutate_repairs.py"),
             "NO-SUCH-FINDING"],
            cwd=str(t), env=env, capture_output=True, text=True)

    # ---- the reviewer's case: different bytes staged ----
    #
    # HEAD holds one thing, the index holds another, the working tree holds the
    # mutation. Recovery must write HEAD's bytes. `git checkout -- <path>`
    # wrote the index's, which is the defect this control exists for.
    t = build()
    (t / "scripts" / "subject.py").write_bytes(STAGED_BYTES)
    sh("git", "add", "scripts/subject.py", cwd=t)
    (t / "scripts" / "subject.py").write_bytes(MUTATED_BYTES)
    sentinel(t, MUTATED_BYTES)

    r = run_probe(t)
    after = (t / "scripts" / "subject.py").read_bytes()
    blob = r.stdout + r.stderr
    if after == STAGED_BYTES:
        failures.append(
            "recovery restored the STAGED bytes while reporting HEAD. That is "
            "the defect BOOTSTRAP-003 reported: `git checkout -- <path>` reads "
            "the index, and the index is not the repaired source.")
    elif after != HEAD_BYTES:
        failures.append(
            f"recovery left the file as neither HEAD nor the index: "
            f"{after!r}")
    elif "recovered" not in blob:
        failures.append(f"the file was restored and nothing said so\n{blob[:300]}")
    else:
        ok("a killed run is restored from HEAD, not from the index")

    if (t / "_probe" / ".active-mutation.json").exists():
        failures.append("the sentinel survived a successful recovery, so the "
                        "next run would try to recover a file already restored")
    else:
        ok("the sentinel is removed once the file is back")

    # ---- the index is not this probe's to revert ----
    staged_now = sh("git", "show", ":scripts/subject.py", cwd=t).stdout.encode()
    if staged_now != STAGED_BYTES:
        failures.append(
            "recovery rewrote the index. Someone else's staged work is not "
            "this probe's to discard, and restoring the file does not require "
            "touching it.")
    else:
        ok("the index is left exactly as it was")

    # ---- it refuses rather than guessing when HEAD has moved ----
    t2 = build()
    (t2 / "scripts" / "subject.py").write_bytes(MUTATED_BYTES)
    sentinel(t2, MUTATED_BYTES)
    rec = json.loads((t2 / "_probe" / ".active-mutation.json")
                     .read_text(encoding="utf-8"))
    rec["head"] = "0" * 40
    (t2 / "_probe" / ".active-mutation.json").write_text(
        json.dumps(rec, indent=2) + "\n", encoding="utf-8")

    r2 = run_probe(t2)
    blob2 = r2.stdout + r2.stderr
    if (t2 / "scripts" / "subject.py").read_bytes() != MUTATED_BYTES:
        failures.append(
            "recovery restored a file although HEAD had moved since the "
            "mutation. A recovery that guesses is worse than one that refuses.")
    # The refusal's own words, not the bare phrase `CANNOT RUN`. The first
    # version of this control looked for that phrase and got it from the
    # argument filter, which prints it too — so it passed while recovery was
    # never reached at all. A control satisfied by the wrong message is the
    # defect this whole probe exists to find.
    elif "has moved since" not in blob2:
        failures.append(f"HEAD had moved and nothing refused for that reason\n"
                        f"{blob2[:300]}")
    else:
        ok("a moved HEAD refuses rather than restoring from the wrong commit")

    # ---- and it does nothing at all when there is no sentinel ----
    t3 = build()
    r3 = run_probe(t3)
    if "recovered" in (r3.stdout + r3.stderr):
        failures.append("recovery reported restoring something with no "
                        "sentinel present")
    elif (t3 / "scripts" / "subject.py").read_bytes() != HEAD_BYTES:
        failures.append("a run with no sentinel rewrote the subject anyway")
    else:
        ok("no sentinel, nothing recovered, nothing written")

    # ---- SELF-F05: the state that actually happened ----
    #
    # 8 October, close to one in the morning. A run was killed between
    # truncating scripts/loop_state.py and writing the mutation into it, and
    # the tree was left holding an empty 1163-line covered component. Recovery
    # compared the empty file against the digest of what it had meant to write,
    # found no match, and refused. Every guard behaved as designed and the
    # repository stayed broken until someone read `git status` by hand.
    #
    # The sentinel here names a mutation that never landed, which is the whole
    # point: on disk there is neither the original nor the mutation.
    t4 = build()
    (t4 / "scripts" / "subject.py").write_bytes(b"")
    sentinel(t4, MUTATED_BYTES)

    r4 = run_probe(t4)
    after4 = (t4 / "scripts" / "subject.py").read_bytes()
    blob4 = r4.stdout + r4.stderr
    if after4 == b"":
        failures.append(
            "an empty source file with a live sentinel was left empty. "
            "Refusing is the right instinct everywhere else here, and it is "
            "wrong in this one case: nobody edits a file down to zero bytes, "
            "so there is no human work being protected by the refusal.")
    elif after4 != HEAD_BYTES:
        failures.append(f"the empty file was rewritten with something that is "
                        f"not HEAD: {after4[:80]!r}")
    elif "empty" not in blob4:
        failures.append(f"the file was restored without saying it had been "
                        f"found empty, so a reader cannot tell this from an "
                        f"ordinary recovery\n{blob4[:300]}")
    elif (t4 / "_probe" / ".active-mutation.json").exists():
        failures.append("the sentinel survived recovery from the empty case")
    else:
        ok("an empty file left by a kill mid-write is restored, and says so")

    # The other half, and the one that stops the case above from arising. A
    # write that fails partway must leave the original untouched rather than a
    # truncated file. os.fsync is made to raise, which is the closest a test
    # can get to the process dying with the file open.
    t5 = build()
    subj = t5 / "scripts" / "subject.py"
    sys.path.insert(0, str(t5 / "_probe"))
    for _m in ("mutate_repairs",):
        sys.modules.pop(_m, None)
    import mutate_repairs as _mr  # noqa: E402

    _real_fsync = os.fsync
    os.fsync = lambda fd: (_ for _ in ()).throw(OSError("simulated kill"))
    try:
        _mr.write_atomic(subj, "this text must never reach the file\n")
    except OSError:
        pass
    finally:
        os.fsync = _real_fsync
    # Both branches below are the same violation, so both say so in the same
    # words. The first version named only the empty case, and when the probe
    # mutated this repair the other branch fired instead: the write landed and
    # fsync raised after it, leaving the target holding the new text. The
    # control was right and its wording was too narrow to recognise itself,
    # which is a smaller copy of the defect class this whole layer chases.
    if subj.read_bytes() == b"":
        failures.append(
            "a write that did not complete emptied the target. write_text "
            "truncates before it fills, and this repair exists so the target "
            "is never left half written.")
    elif subj.read_bytes() != HEAD_BYTES:
        failures.append(
            f"a write that did not complete changed the target anyway: "
            f"{subj.read_bytes()[:80]!r}. The new content must not be visible "
            f"until the whole of it is on disk.")
    else:
        ok("a write that does not complete leaves the original intact")
    sys.path.remove(str(t5 / "_probe"))

    # ---- Alex Zamurko, 9 October 2026, required action 1 ----
    #
    #   "Implement isolated mutation testing and prove the original repository
    #    stays unchanged, including after interrupted runs."
    #
    # The first half was demonstrated by running the probe and seeing a clean
    # tree. The second half is the one that has cost us two days, and it is a
    # claim about what happens when the process dies, so it is tested by
    # killing one rather than by reasoning about it.
    #
    # Run in a full clone rather than against this repository. If the claim is
    # false the damage lands in a directory this test deletes, which is the
    # same principle the probe itself now follows. Testing an isolation claim
    # by risking the thing it is supposed to isolate would be its own joke.
    clone = Path(tempfile.mkdtemp(prefix="probe-kill-")).resolve()
    made.append(clone)
    target = clone / "repo"
    c = subprocess.run(["git", "clone", "--quiet", "--local",
                        "--no-hardlinks", str(REPO), str(target)],
                       capture_output=True, text=True)
    if c.returncode != 0:
        failures.append(
            "could not clone the repository to test the interrupted-run "
            "claim, so it is untested rather than established:\n"
            + (c.stderr or c.stdout).strip()[:300])
    else:
        # The clone carries HEAD, so without this the control tests the
        # committed probe rather than the one about to be committed. That is
        # AR-6 arriving where it was least expected: on 10 October this
        # control reported an abandoned checkout surviving, and the reason
        # was that every fix for it was still uncommitted, so the clone was
        # faithfully reproducing yesterday's defect.
        #
        # The working-tree probe is copied in and committed inside the clone,
        # which also satisfies the probe's own refusal to run against a dirty
        # tree. Only this file is replaced: the rest of the clone stays at
        # HEAD, so the control still runs against a real repository rather
        # than a construction.
        shutil.copy2(PROBE, target / "_probe" / "mutate_repairs.py")
        for cfg in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(target), "config", *cfg],
                           capture_output=True, text=True)
        subprocess.run(["git", "-C", str(target), "add", "-A"],
                       capture_output=True, text=True)
        subprocess.run(["git", "-C", str(target), "commit", "-qm",
                        "the working-tree probe, which is what is under test"],
                       capture_output=True, text=True)

        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(target / "_probe" / "mutate_repairs.py"),
             "C01-F01"],
            cwd=str(target), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # Long enough to be inside a mutation, short enough that the run has
        # not finished. The tree assertion below does not depend on hitting
        # that window precisely: if the run completed, the tree is clean
        # because it finished properly, and if it did not, the tree is clean
        # because of the isolation. Either way a dirty tree is a failure.
        #
        # The sweep assertion does depend on it, and says so when it misses
        # rather than quietly passing. Twenty seconds because the first clone
        # of this repository is slow and eight was landing before the probe
        # had created anything to abandon.
        try:
            proc.wait(timeout=20)
            killed = False
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
            killed = True

        st = subprocess.run(["git", "-C", str(target), "status", "--porcelain"],
                            capture_output=True, text=True)
        dirty = [ln[3:].strip() for ln in st.stdout.splitlines()
                 if ln.strip() and not ln.strip().startswith("??")]
        if dirty:
            failures.append(
                "a probe run that was killed left the repository modified, so "
                "the isolation does not hold:\n    " + "\n    ".join(dirty) +
                "\n  This is the claim Alex asked to have proved, and it is "
                "the one that emptied\n  a covered component on 8 October.")
        else:
            how = "killed mid-run" if killed else "allowed to finish"
            ok(f"a probe run {how} leaves the repository untouched")

        # The abandoned checkout is the expected residue, and the next run
        # removing it is what makes that acceptable rather than a new leak.
        wt = subprocess.run(["git", "-C", str(target), "worktree", "list",
                             "--porcelain"], capture_output=True, text=True)
        before = [l for l in wt.stdout.splitlines()
                  if l.startswith("worktree ") and "epistemicos-probe-" in l]

        # SELF-F06 changed what happens next, and the cost is real enough to
        # be tested rather than glossed. A killed run leaves its lock behind,
        # so the run after it refuses instead of sweeping. That is deliberate:
        # the alternative is this process deciding the other one is dead, and
        # deciding that wrongly means deleting a live run's working copy,
        # which is the defect the lock exists to prevent.
        #
        # So the sequence is three steps, not two, and the middle one needs a
        # person. Tested here because a cost nobody has written down is a cost
        # somebody discovers at a bad moment.
        _lock = target / "_probe" / ".probe-lock.json"
        if not _lock.is_file():
            failures.append(
                "a killed run left no lock, so nothing stops the next run "
                "sweeping a\n  checkout that another process may still be "
                "using. That is SELF-F06.")
        refused = subprocess.run(
            [sys.executable, str(target / "_probe" / "mutate_repairs.py"),
             "NO-SUCH-FINDING"],
            cwd=str(target), env=env, capture_output=True, text=True)
        _said = refused.stdout + refused.stderr
        if refused.returncode == 0 or "another run holds" not in _said:
            failures.append(
                "a run started while a lock was held did not refuse for that "
                "reason:\n  " + _said.strip()[:300])
        elif str(_lock) not in _said:
            failures.append(
                "the refusal did not say which file to remove, so clearing a "
                "stale lock is\n  guesswork")
        else:
            ok("a second run refuses while another holds the lock, and says "
               "how to clear it")

        # And it must not tidy up on its way out. The first version of the
        # lock released it in a finally with no record of who had taken it,
        # so the refusing run deleted the holder's claim as it exited. That
        # is SELF-F06 again in one move: a process removing another's lock
        # because it checked the file existed rather than whose it was. It
        # was caught before it shipped, by reading, which is not a method
        # that scales, hence this.
        if not _lock.is_file():
            failures.append(
                "the run that refused deleted a lock it did not take. The "
                "next run would then\n  sweep a checkout the holder is still "
                "using, which is the defect the lock\n  exists to prevent.")
        else:
            ok("the refusing run leaves the lock alone, having not taken it")

        # Alex Zamurko asked the exact question this answers, on 14 October
        # 2026: "Has SELF-F06 been independently verified to ensure that the
        # three parallel sweeps cannot interfere with each other or delete
        # another run's active worktree?"
        #
        # The answer we had was that the lock is taken before anything touches
        # a sandbox directory, so a refused run never reaches the cleanup. That
        # is an argument from the order of the source, and an argument is not a
        # demonstration. This is the demonstration. The checkout the killed run
        # left behind stands in for a live run's working copy: another run has
        # just refused, and that checkout must still be there.
        #
        # The emptiness check first, because a control that protects nothing
        # passes for free. If the fixture left no checkout, this proves the
        # absence of a hazard rather than the presence of a guard.
        if not before:
            failures.append(
                "the killed run left no checkout, so the control below has "
                "nothing to protect\n  and would pass whatever the probe did. "
                "The fixture is not exercising what\n  it claims.")
        else:
            wt2 = subprocess.run(["git", "-C", str(target), "worktree", "list",
                                  "--porcelain"], capture_output=True,
                                 text=True)
            after = [l for l in wt2.stdout.splitlines()
                     if l.startswith("worktree ") and "epistemicos-probe-" in l]
            gone = [l.split(" ", 1)[1] for l in before if l not in after]
            still = [p for p in (Path(l.split(" ", 1)[1]) for l in before)
                     if p.exists()]
            if gone:
                failures.append(
                    "the refusing run leaves another run's checkout alone: it "
                    "did not. These were\n  deregistered by a run that did "
                    "not make them:\n    " + "\n    ".join(gone) +
                    "\n  If the holder were alive rather than killed, that is "
                    "its working copy\n  taken out from under it. This is the "
                    "question Alex Zamurko asked about\n  SELF-F06.")
            elif len(still) != len(before):
                failures.append(
                    "the refusing run leaves another run's checkout alone: a "
                    "checkout is still\n  registered with git and its folder "
                    "is gone, so the contents were deleted\n  and the record "
                    "left behind.")
            else:
                ok(f"the refusing run leaves another run's checkout alone, "
                   f"registered and on disk ({len(before)} checked)")

        # The person's step, and then the sweep it was holding up.
        #
        # missing_ok because the control above can legitimately find the lock
        # already gone: that is the failure it reports. Without it the suite
        # raised FileNotFoundError here and the probe reported a crash rather
        # than a failing control, which says nothing about which controls
        # hold. A test that cannot survive its own failure case reports the
        # wrong thing at exactly the moment it matters.
        _lock.unlink(missing_ok=True)
        second = subprocess.run(
            [sys.executable, str(target / "_probe" / "mutate_repairs.py"),
             "NO-SUCH-FINDING"],
            cwd=str(target), env=env, capture_output=True, text=True)
        wt2 = subprocess.run(["git", "-C", str(target), "worktree", "list",
                              "--porcelain"], capture_output=True, text=True)
        after = [l for l in wt2.stdout.splitlines()
                 if l.startswith("worktree ") and "epistemicos-probe-" in l]
        _said = second.stdout + second.stderr
        if not killed:
            ok("no checkout was abandoned, because the run finished cleanly")
        elif not before:
            # Reported, not passed. The first version treated this as the
            # sweep working, then failed on the absence of a message about
            # nothing. A control that stops exercising anything should say so
            # rather than go quiet, which is this whole layer's one rule.
            failures.append(
                "the run was killed before it had made a checkout, so the "
                "sweep was never\n  exercised. Nothing is established about "
                "it either way. Give the run longer\n  before killing it.")
        elif after:
            failures.append(
                "an abandoned checkout survived the next run, so they "
                "accumulate rather than being swept\n"
                "    before: " + "; ".join(before) + "\n"
                "    after:  " + "; ".join(after) + "\n"
                "    the sweeping run said:\n      "
                + "\n      ".join(_said.strip().splitlines()[:8]))
        elif "cleaned" not in _said:
            failures.append(
                "the abandoned checkout was removed without saying so. "
                "Cleaning up\n  silently is how a reader stops knowing a run "
                "was interrupted at all.\n"
                "    before: " + "; ".join(before) + "\n"
                "    the sweeping run said:\n      "
                + ("\n      ".join(_said.strip().splitlines()[:10])
                   or "(nothing at all)"))
        else:
            ok("the next run removes the abandoned checkout and reports it")

    # ---- the probe's own source, loaded and called ----
    #
    # Added 12 October, after a full sweep died on `NameError: name 're' is
    # not defined` inside outside_own_table(). That function was written the
    # same day to stop a self-aimed mutation colliding with the table entry
    # that quotes it, and it had never once executed: every run between
    # writing it and the sweep selected mutations aimed at other files, so the
    # branch that calls it was never taken. Seven green probe runs and
    # fourteen green suites, none of which touched the new code.
    #
    # Importing the module is the point. The controls above all run the probe
    # as a subprocess against a fixture, which exercises whichever paths that
    # fixture happens to reach, and a function nothing reaches is a function
    # nothing tests. These three call it directly.
    sys.path.insert(0, str(REPO / "_probe"))
    try:
        import mutate_repairs as probe
    except Exception as e:
        failures.append(f"the probe's own source imports, so every name it "
                        f"uses resolves: it does not, {e!r}")
        probe = None

    # Each failure below repeats the words of its own tick. The probe matches
    # the text a control is expected to produce against the RED output, so a
    # phrase that appears only in the green message identifies nothing: the
    # suite goes red, the probe cannot tell which control did it, and reports
    # [WRONG CONTROL]. That is what happened on the first run of SELF-F09,
    # and it is the same defect in miniature as everything else here, a check
    # that fires for a reason it cannot name.
    if probe is not None:
        ok("the probe's own source imports, so every name it uses resolves")

        _sample = ('import os\n'
                   'def f():\n'
                   '    return 1\n'
                   '\n'
                   'MUTATIONS = [\n'
                   '    ("A  a line", "x.py", "    return 1", "    return 2",\n'
                   '     "test_x.py", "something"),\n'
                   ']\n'
                   '\n'
                   'def g():\n'
                   '    return 1\n')
        _masked = probe.outside_own_table(_sample)

        # Offsets have to survive, because the replacement is applied to the
        # real text at a position found in the masked copy. A mask that
        # shortened the string would write into the wrong place.
        if len(_masked) != len(_sample):
            failures.append(
                f"masking the table preserves length and line structure: it "
                f"changed the length, {len(_sample)} to {len(_masked)}, so "
                f"every position found in the masked copy points somewhere "
                f"else in the real one")
        elif _masked.count("\n") != _sample.count("\n"):
            failures.append("masking the table preserves length and line "
                            "structure: the line count changed")
        else:
            ok("masking the table preserves length and line structure")

        # And it has to actually mask. One occurrence left, in the code.
        if _masked.count("    return 1") != 2:
            failures.append(
                f"an anchor quoted by its own table entry is found once in "
                f"the code, not twice: it appears "
                f"{_masked.count('    return 1')} time(s) in the masked copy, "
                f"expected 2, the two real definitions and not the entry that "
                f"quotes one of them")
        else:
            ok("an anchor quoted by its own table entry is found once in the "
               "code, not twice")

    # ---- two live runs at once ----
    #
    # Alex Zamurko, 15 October 2026, accepting the lock and asking for one
    # thing more: "The reported test kills the first process and checks that a
    # second process refuses to clean its worktree. This demonstrates
    # protection against an interrupted run, but does not directly test two
    # simultaneously active processes. Add one live-concurrency test: start
    # two probes sharing the same sandbox environment, verify that the second
    # refuses, and confirm the first completes without its worktree being
    # modified or deleted."
    #
    # He is right that the stale-lock case is the easier one. A dead holder
    # cannot be harmed by a mistake; a live one can.
    #
    # Making this real needs the first run to be genuinely busy rather than
    # merely holding a file, so the fixture carries its own one-line mutation
    # table pointing at a test that sleeps. The probe then does everything it
    # normally does, over several seconds, while the second run arrives in the
    # middle of it.
    def live_fixture() -> Path:
        t = build()
        (t / "scripts" / "subject.py").write_text(
            "def f():\n    return 1\n", encoding="utf-8", newline="\n")
        (t / "scripts" / "test_subject.py").write_text(
            "import sys, time\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parent))\n"
            "import subject\n"
            "time.sleep(4)\n"
            "if subject.f() != 1:\n"
            "    print('FAIL: subject returns one, and it does not')\n"
            "    sys.exit(1)\n"
            "print('[ok] subject returns one')\n",
            encoding="utf-8", newline="\n")
        # One entry, aimed at this fixture. Swapped in rather than appended,
        # so the run cannot wander into the real table's targets, none of
        # which exist here.
        src = (t / "_probe" / "mutate_repairs.py").read_text(encoding="utf-8")
        i, j = src.index("\nMUTATIONS = ["), src.index("\n]\n",
                                                      src.index("\nMUTATIONS = ["))
        (t / "_probe" / "mutate_repairs.py").write_text(
            src[:i] + '\nMUTATIONS = [\n'
            '    ("LIVE  the fixture\'s one repair",\n'
            '     "subject.py",\n'
            '     "    return 1",\n'
            '     "    return 2",\n'
            '     "test_subject.py",\n'
            '     "subject returns one"),\n' + src[j:],
            encoding="utf-8", newline="\n")
        sh("git", "add", "-A", cwd=t)
        sh("git", "commit", "-qm", "a fixture with one real repair", cwd=t)
        return t

    _env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    _t = live_fixture()
    _probe_py = str(_t / "_probe" / "mutate_repairs.py")
    _lockf = _t / "_probe" / ".probe-lock.json"
    first = subprocess.Popen([sys.executable, "-u", _probe_py],
                             cwd=str(_t), env=_env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
    try:
        # Wait for it to be genuinely under way: holding the lock and having
        # made its checkout. Starting the second run before that would be
        # testing nothing, and the control says so rather than passing.
        held = None
        for _ in range(200):
            if _lockf.is_file() and list(
                    (_t / ".probe-sandboxes").glob("epistemicos-probe-*")):
                held = sorted((_t / ".probe-sandboxes").glob(
                    "epistemicos-probe-*"))
                break
            time.sleep(0.05)

        if held is None:
            failures.append(
                "the first run never took the lock and made a checkout, so "
                "the second run\n  below did not overlap with anything. This "
                "control establishes nothing in\n  that state rather than "
                "passing quietly.")
            second = None
        else:
            second = subprocess.run([sys.executable, "-u", _probe_py],
                                    cwd=str(_t), env=_env,
                                    capture_output=True, text=True)
            _said = second.stdout + second.stderr
            _after = sorted((_t / ".probe-sandboxes").glob(
                "epistemicos-probe-*"))
            if second.returncode == 0 or "another run holds" not in _said:
                failures.append(
                    "a second probe started while the first was actively "
                    "running did not\n  refuse for that reason:\n  "
                    + _said.strip()[:300])
            elif [p.name for p in _after] != [p.name for p in held]:
                failures.append(
                    "the second run removed the live run's checkout while it "
                    "was still using\n  it. That is SELF-F06 with a live "
                    "holder rather than a dead one, which is\n  the case Alex "
                    "Zamurko asked to have tested:\n  before "
                    f"{[p.name for p in held]}\n  after  "
                    f"{[p.name for p in _after]}")
            else:
                ok(f"a second probe refuses while the first is actively "
                   f"running, and leaves its checkout alone "
                   f"({held[0].name})")
    finally:
        _out = first.communicate(timeout=180)[0] or ""

    if second is not None:
        if first.returncode != 0:
            failures.append(
                "the first run did not finish cleanly while a second was "
                "refused alongside\n  it, so the refusal protected nothing:\n  "
                + _out.strip()[-300:])
        elif "[caught]" not in _out:
            failures.append(
                "the first run finished without catching its one repair, so "
                "it was not doing\n  real work while the second was refused:\n"
                "  " + _out.strip()[-300:])
        else:
            ok("the first run completes its work uninterrupted, with the "
               "second refused mid-flight")

        _dirty = sh("git", "status", "--porcelain", cwd=_t).stdout.strip()
        _left = list((_t / ".probe-sandboxes").glob("epistemicos-probe-*"))
        if _dirty:
            failures.append(f"two runs at once left the repository modified:"
                            f"\n  {_dirty[:200]}")
        elif _left:
            failures.append(f"the finished run left its checkout behind: "
                            f"{[p.name for p in _left]}")
        else:
            ok("after both, the repository is unmodified and no checkout "
               "remains")

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("  the probe's recovery names its source and leaves the rest alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
