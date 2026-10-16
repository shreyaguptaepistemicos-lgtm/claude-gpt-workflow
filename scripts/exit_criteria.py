#!/usr/bin/env python3
"""The machine-checkable half of the bootstrap exit criteria.

    python scripts/exit_criteria.py

Exit 0 = every check that ran, passed. 1 = at least one failed. 2 = at least
one could not be run, which is neither.

Three answers, not two
----------------------
PASS, FAIL and CANNOT_ESTABLISH. The third exists because this whole layer
keeps finding the same defect in itself: a check that passes for a reason other
than the one it is named for. A check that could not run has established
nothing, and reporting that as a pass is exactly how a review full of findings
reaches CONVERGED.

What this does not do
---------------------
It does not say whether the bootstrap phase can exit. Each condition in
specs/BOOTSTRAP-EXIT-CRITERIA.md has a judgement reserved to Alex Zamurko, and
those judgements are not derivable from anything here: which open defects are
critical, whether the mutation set covers what matters, whether a record is
true rather than merely present, and whether a reviewer's evidence is adequate.
This prints the mechanical half and says plainly that the other half is
missing. A tool that totalled these into a verdict would be making his
decisions quietly, which is the thing the whole protocol is built to prevent.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
SPECS = REPO / "specs"
PROBE = REPO / "_probe"

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "CANNOT_ESTABLISH"


def runs() -> list[Path]:
    base = REPO / "runs"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir()
                  if (p / "plan-review").is_dir())


def tool(*args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *args], cwd=str(REPO),
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class Condition:
    def __init__(self, cid: str, claim: str, judgement: str):
        self.cid = cid
        self.claim = claim
        self.judgement = judgement
        self.results: list[tuple[str, str, str]] = []

    def check(self, state: str, name: str, detail: str = "") -> None:
        self.results.append((state, name, detail))

    @property
    def verdict(self) -> str:
        states = {s for s, _, _ in self.results}
        if not self.results:
            return UNKNOWN
        if FAIL in states:
            return FAIL
        if UNKNOWN in states:
            return UNKNOWN
        return PASS

    def report(self) -> None:
        print(f"\n{self.cid}  {self.claim}")
        print(f"  machine checks: {self.verdict}")
        for state, name, detail in self.results:
            mark = {PASS: "ok  ", FAIL: "FAIL", UNKNOWN: "?   "}[state]
            print(f"    [{mark}] {name}")
            if detail:
                for line in detail.splitlines():
                    print(f"           {line}")
        print(f"  judgement reserved to Alex Zamurko: {self.judgement}")


# ---------------------------------------------------------------- EC-1
def ec1() -> Condition:
    c = Condition(
        "EC-1", "no critical open defect",
        "which open defects are critical")

    # A run that says CONVERGED while findings are open at its governing
    # boundary is the failure this condition exists for. A run that refuses to
    # compute a state is not a failure of this condition: refusing is the
    # correct behaviour and EC-3 is where an unreadable record is judged.
    for run in runs():
        rel = f"runs/{run.name}/plan-review"
        rc, out = tool(str(SCRIPTS / "loop_state.py"), "--review", rel,
                       "--development", "--json")
        if rc != 0:
            c.check(UNKNOWN, f"{run.name}: controller refuses, so convergence "
                             f"cannot be judged here",
                    out.strip().splitlines()[0] if out.strip() else "")
            continue
        try:
            proj = json.loads(out)
        except json.JSONDecodeError:
            c.check(UNKNOWN, f"{run.name}: the controller's JSON could not be "
                             f"read")
            continue
        if not proj.get("sets_established"):
            c.check(UNKNOWN, f"{run.name}: no finding sets were established")
            continue
        open_ids = proj.get("open", [])
        if proj.get("status") == "CONVERGED" and open_ids:
            c.check(FAIL, f"{run.name}: CONVERGED with findings open",
                    "open: " + ", ".join(open_ids))
        else:
            c.check(PASS, f"{run.name}: {proj.get('status')} with "
                          f"{len(open_ids)} open at n="
                          f"{proj.get('governing_boundary')}")

    # Every blocking item must be classified, and the classification file must
    # name the condition it blocks. An unclassified finding is not a pass and
    # not a failure: it is a judgement nobody has made yet.
    bf = SPECS / "blocking-defects.json"
    if not bf.is_file():
        c.check(UNKNOWN, "no blocking-defect classification exists",
                "EC-1 cannot be evaluated without it. See "
                "specs/BOOTSTRAP-EXIT-CRITERIA.md.")
    else:
        try:
            blocking = json.loads(bf.read_text(encoding="utf-8")).get(
                "blocking", {})
        except json.JSONDecodeError as e:
            c.check(UNKNOWN, f"the blocking-defect classification is not valid "
                             f"JSON: {e}")
            return c

        # The first version of this counted the blocking defects and called
        # that a pass. It reported EC-1 PASS on 10 October with all four of
        # them open, because counting a list is not asking whether anything on
        # it is closed. A condition named "no critical open defect" that never
        # looks at whether the critical defects are open is a check passing
        # for a reason other than the one it is named for, which is the defect
        # class this entire document exists to prevent, written into the
        # document itself.
        #
        # A defect is closed here when a reviewer has examined its repair,
        # which is EC-4's bar and Alex Zamurko's: "Behavioural claims require
        # independent execution." So EC-1 and EC-4 move together, and that is
        # correct rather than redundant: EC-4 asks whether the evidence
        # exists, EC-1 asks whether anything critical is still open. Today the
        # answer to both is no and they should not disagree.
        _open = sorted(k for k, v in blocking.items()
                       if not v.get("independently_examined_in_cycle"))
        if not blocking:
            c.check(UNKNOWN, "nothing is classified as blocking",
                    "An empty list is not the same as nothing being critical. "
                    "Either no\nfinding has been classified yet, or the file "
                    "is wrong.")
        elif _open:
            c.check(FAIL, f"{len(_open)} of {len(blocking)} blocking "
                          f"defect(s) are still open",
                    ", ".join(_open) + "\nEach has a repair that no reviewer "
                    "has examined. Until one has, this\ncondition is not met.")
        else:
            c.check(PASS, f"all {len(blocking)} blocking defect(s) closed")

        # SELF-F07: "The checker also does not detect newly unclassified
        # findings." The criterion says this condition cannot be evaluated
        # while any finding is unclassified, and nothing was looking.
        _classified = set(blocking) | set(
            json.loads(bf.read_text(encoding="utf-8")).get("not_blocking", {}))
        #
        # Narrowed to findings that are OPEN at the governing boundary. The
        # first version asked about every finding in every ledger and reported
        # fifty-three, which is true and useless: this condition is about open
        # defects, and a finding resolved in a closed run is not one. Asking a
        # wider question than the criterion poses produces noise that buries
        # the answer, which is its own way of reporting nothing.
        #
        # Open states come from the controller rather than the ledger's cached
        # fields, for the same reason everything else here does.
        _unclassified = []
        for run in runs():
            rc, out = tool(str(SCRIPTS / "loop_state.py"), "--review",
                           f"runs/{run.name}/plan-review", "--development",
                           "--json")
            if rc != 0:
                continue
            try:
                _proj = json.loads(out)
            except json.JSONDecodeError:
                continue
            _unclassified += [f"{run.name}: {k}"
                              for k in sorted(_proj.get("open", []))
                              if k not in _classified]
        if _unclassified:
            c.check(UNKNOWN, f"{len(_unclassified)} finding(s) are classified "
                             f"neither blocking nor not",
                    ", ".join(_unclassified[:8]) +
                    "\nSilence is not a classification, and this condition "
                    "cannot be evaluated\nwhile one is outstanding.")
        else:
            c.check(PASS, "every finding in every ledger is classified")

    # The criterion's second check: the package refuses rather than printing
    # an empty category when the controller cannot establish the sets. This
    # script cannot construct that situation without a fixture, and building
    # one here would be a second implementation of the thing being tested.
    # What it can do is require that the control which does establish it
    # exists and passed, by name. A named control that has stopped existing
    # is then a failure here rather than a silence.
    #
    # These two names were wrong when first written, and this check caught it
    # within a minute of existing. One of them named a control that had been
    # replaced on 10 October, when the guard it tested turned out to be
    # unreachable. The criterion was resting on a name that was gone, and
    # nothing would have said so.
    #
    # Names rather than counts, deliberately. A count stays satisfied while
    # the controls behind it are swapped for weaker ones.
    _want = ("refused, not crashed: a frozen cycle whose record cannot be "
             "read produces a stated reason",
             "refused: a readable ledger that holds none of what the review "
             "reported",
             "an invalidated demonstration is reported as unresolved")
    rc, out = tool(str(SCRIPTS / "test_approval_package.py"))
    _absent = [w for w in _want if w not in out]
    if rc != 0:
        c.check(FAIL, "the suite holding the package's refusal controls does "
                      "not pass", out.strip()[-300:])
    elif _absent:
        c.check(FAIL, "a named refusal control is no longer reported",
                "\n".join(_absent) +
                "\nThe criterion rests on these. A control that has been "
                "renamed or removed\nleaves the condition resting on nothing.")
    else:
        c.check(PASS, "the package's refusal controls exist and pass, by name")

    # The criterion's third check: every mutation bearing on convergence or
    # reporting goes red in a control that names it. Read from the recorded
    # sweep, and refusing rather than guessing when there is not one.
    _rules = ("exit A", "exit B", "exit C", "SELF-F01", "SELF-F04",
              "C01-F02", "C01-F06")
    sweep = PROBE / "full-sweep.txt"
    if not sweep.is_file() or not sweep.read_text(
            encoding="utf-8", errors="replace").strip():
        c.check(UNKNOWN, "no recorded sweep, so the convergence and reporting "
                         "mutations are unestablished")
    else:
        _text = sweep.read_text(encoding="utf-8", errors="replace")
        _missing = [r for r in _rules
                    if f"[caught] {r}" not in _text]
        if _missing:
            c.check(UNKNOWN, f"{len(_missing)} convergence or reporting "
                             f"mutation(s) not reported caught",
                    ", ".join(_missing) +
                    "\nAbsent from the recorded sweep is not the same as "
                    "failing, and it is not\nthe same as passing either.")
        else:
            c.check(PASS, f"all {len(_rules)} convergence and reporting "
                          f"mutations go red when removed")
    return c


# ---------------------------------------------------------------- EC-2
def ec2() -> Condition:
    c = Condition(
        "EC-2", "reliable verification",
        "whether the mutation set covers the repairs that matter")

    suites = sorted(SCRIPTS.glob("test_*.py"))
    red = []
    for s in suites:
        rc, _ = tool(str(s))
        if rc != 0:
            red.append(s.name)
    if red:
        c.check(FAIL, f"{len(red)} of {len(suites)} suite(s) red",
                ", ".join(red))
    else:
        c.check(PASS, f"all {len(suites)} suites pass")

    # The sweep is not run here: it takes hours and this script is meant to be
    # runnable on demand. Its recorded result is read instead, with the one
    # guard that makes a recorded result worth anything, which is that it must
    # be newer than the code it claims to cover. A sweep from before the last
    # change to scripts/ says nothing about what is there now.
    sweep = PROBE / "full-sweep.txt"
    if not sweep.is_file():
        c.check(UNKNOWN, "no recorded mutation sweep",
                "run `python _probe/mutate_repairs.py > _probe/full-sweep.txt`")
    else:
        r = subprocess.run(["git", "-C", str(REPO), "log", "-1",
                            "--format=%ct", "--", "scripts", "_probe"],
                           capture_output=True, text=True)
        try:
            newest_code = int(r.stdout.strip())
        except ValueError:
            newest_code = None
        # SELF-F11. Until 14 October this read the file with
        # errors="replace" and asked no questions. Every local sweep log was
        # written by PowerShell's `>` redirect, which emits UTF-16LE with a
        # byte-order mark, so the words arrived as replacement characters and
        # none of the checks below could find `swept commit` or `[caught]` in
        # a sweep that had neither failed nor been interrupted. The condition
        # reported that the log said nothing, which was true of what it could
        # read and false of what was in the file.
        #
        # errors="replace" is what made it quiet. A reader that cannot decode
        # its evidence has not found an empty result; it has found an answer
        # it cannot read, and those are different things.
        _raw = sweep.read_bytes()
        _unreadable = ""
        if _raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            _unreadable = ("it is UTF-16, which is what PowerShell's `>` "
                           "redirect writes.\nRe-run with "
                           "`python -u _probe/mutate_repairs.py "
                           "--out=_probe/full-sweep.txt`, which makes the "
                           "probe\nwrite its own log in UTF-8 rather than "
                           "letting the shell choose.")
            text = ""
        else:
            try:
                text = _raw.decode("utf-8-sig")
            except UnicodeDecodeError as e:
                _unreadable = f"it is not valid UTF-8: {e}"
                text = ""
        stale = (newest_code is not None
                 and sweep.stat().st_mtime < newest_code)

        # SELF-F07. A timestamp says when a file was written, not what it
        # describes. The sweep now states the commit it examined and the size
        # of the set it was drawn from, so this can ask the two questions
        # that matter: is this about the code in front of us, and did it get
        # all the way through.
        _swept = re.search(r"swept commit ([0-9a-f]{7,40})", text)
        _held = re.search(r"mutation set holds (\d+); this run looked at "
                          r"(\d+)", text)
        # The same circularity Alex Zamurko found in EC-4 lives here, and it
        # has already been paid for: on 12 October a sweep ran for two and a
        # half hours, a one-line commit afterwards moved HEAD, and this check
        # correctly reported the log as describing a different commit. The
        # sweep was not wrong. Binding evidence to HEAD means committing the
        # evidence destroys it. He named it about EC-4; it is the same defect
        # and this is the same fix.
        _at, _at_src = candidate()

        if _unreadable:
            c.check(UNKNOWN, "the recorded sweep cannot be read",
                    f"The file is there and {_unreadable}\n\nA log this check "
                    f"cannot decode is not an empty result and not a clean "
                    f"one.\nIt is an answer nobody here can read.")
        elif stale:
            c.check(UNKNOWN, "the recorded sweep predates the last change to "
                             "the code it covers",
                    "It is not evidence about the current source. Re-run it.")
        elif not text.strip():
            c.check(UNKNOWN, "the recorded sweep is empty")
        elif not _swept or not _held:
            c.check(UNKNOWN, "the recorded sweep does not say which commit it "
                             "examined",
                    "Written before the probe reported that, so it cannot be "
                    "bound to a\ncommit or shown to be complete. Re-run it.")
        elif not _at:
            c.check(UNKNOWN, "no commit could be established to tie the sweep "
                             "to", _at_src)
        elif not _at.startswith(_swept.group(1)):
            c.check(UNKNOWN, "the recorded sweep examined a different commit",
                    f"swept {_swept.group(1)[:12]}, {_at_src} is "
                    f"{_at[:12]}")
        elif _held.group(1) != _held.group(2):
            c.check(UNKNOWN, f"the recorded sweep looked at "
                             f"{_held.group(2)} of {_held.group(1)} mutations",
                    "A filtered or interrupted run establishes nothing about "
                    "the ones it\nskipped, and a count of caught lines cannot "
                    "tell the two apart.")
        else:
            bad = [ln.strip() for ln in text.splitlines()
                   if any(k in ln for k in ("[BROKEN PROBE]", "[MISSED]",
                                            "[WRONG CONTROL]", "[CRASHED]",
                                            "[COULD NOT RUN]", "[ESCAPED]"))]
            if bad:
                c.check(FAIL, f"{len(bad)} repair(s) not demonstrably watched",
                        "\n".join(bad[:6]))
            elif "[caught]" not in text:
                c.check(UNKNOWN, "the recorded sweep reports nothing caught",
                        "An empty result is not a clean one.")
            else:
                n = text.count("[caught]")
                c.check(PASS, f"{n} repair(s) go red when removed, each in a "
                              f"control that names it")

    # The tool must leave the repository as it found it. Since 9 October the
    # probe works in a disposable checkout, so this is an assertion that the
    # isolation held rather than that a restore succeeded.
    r = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain",
                        "--", "scripts", "_probe"],
                       capture_output=True, text=True)
    dirty = [ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()
             and not ln.strip().endswith("full-sweep.txt")]
    if dirty:
        # Said as what it is rather than as the worst thing it could be. The
        # first wording was "source differs from HEAD after testing", which
        # reads as the probe having escaped its sandbox, and on 10 October it
        # fired because the implementing agent had edited a file and not
        # committed it. Two causes, one message, and it named the alarming
        # one. The probe has its own check for escape and says both
        # possibilities out loud; this one is about something narrower.
        c.check(FAIL, "the source on disk is not the source any sweep "
                      "describes",
                ", ".join(dirty) +
                "\nThese differ from HEAD, and a recorded sweep describes a "
                "commit. Either\ncommit them and re-sweep, or discard them. "
                "This is not evidence of the probe\nreaching the real tree; "
                "the probe checks that itself and reports it separately.")
    else:
        c.check(PASS, "the working tree matches HEAD, so a sweep of HEAD "
                      "describes what is here")

    # SELF-F07: "its cleanup check lists registered worktrees, while the probe
    # expressly handles directories whose worktree registration has
    # disappeared. Such residue can escape the exit check."
    #
    # So both: what git remembers, and what is on disk. The probe sweeps by
    # reading the directory precisely because a registration can be gone while
    # the folder remains, and a check that only asks git inherits the blind
    # spot the sweep was built to avoid.
    r = subprocess.run(["git", "-C", str(REPO), "worktree", "list",
                        "--porcelain"], capture_output=True, text=True)
    if r.returncode != 0:
        c.check(UNKNOWN, "git could not list worktrees, so leftover checkouts "
                         "are unestablished",
                r.stderr.strip()[:200] or "(no error text)")
        left = []
    else:
        left = [ln[len("worktree "):].strip() for ln in r.stdout.splitlines()
                if ln.startswith("worktree ")
                and "epistemicos-probe-" in ln]
    _root = REPO / ".probe-sandboxes"
    if _root.is_dir():
        left += [str(p) for p in sorted(_root.iterdir())
                 if p.name.startswith("epistemicos-probe-")
                 and str(p) not in left]
    if left:
        c.check(FAIL, f"{len(left)} disposable checkout(s) left behind",
                "\n".join(left) +
                "\n(Each path ends in the pid of the run that made it. If a "
                "sweep is running\nright now, this is that run's checkout and "
                "not a leftover: finish it and re-run.)")
    else:
        c.check(PASS, "no disposable checkout remains")
    return c


# ---------------------------------------------------------------- EC-3
def ec3() -> Condition:
    c = Condition(
        "EC-3", "complete audit records",
        "whether a record is true, as distinct from present")

    # The gate is run now rather than quoted. A recorded PASS is a claim about
    # the past; this asks the gate what it says today.
    cycles, failed = 0, []
    for run in runs():
        for cyc in sorted((run / "plan-review").glob("cycle-*")):
            if not cyc.is_dir():
                continue
            cycles += 1
            rc, out = tool(str(SCRIPTS / "validate_cycle.py"), str(cyc))
            if rc != 0 or "MC2_CONFORMANCE: PASS" not in out:
                failed.append(f"{run.name}/{cyc.name}")
    if not cycles:
        c.check(UNKNOWN, "no frozen cycles found to check")
    elif failed:
        c.check(FAIL, f"{len(failed)} of {cycles} frozen cycle(s) fail MC-2 "
                      f"today", ", ".join(failed))
    else:
        c.check(PASS, f"all {cycles} frozen cycle(s) pass MC-2 when run now")

    # Every superseded capture needs an approval bound by hash, and the
    # displaced capture must still be there. The recorder enforces this at the
    # moment of supersession; this asks whether it is still true afterwards.
    sup, bad = 0, []
    for run in runs():
        for cyc in sorted((run / "plan-review").glob("cycle-*")):
            log = cyc / "capture-log.json"
            if not log.is_file():
                continue
            try:
                d = json.loads(log.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                bad.append(f"{cyc.name}: capture log is not valid JSON")
                continue
            displaced = [a for a in d.get("invalidated", [])
                         if a.get("superseded_by")]
            if not displaced:
                continue
            sup += 1
            ap = cyc / "capture-supersession-approval.json"
            if not ap.is_file():
                bad.append(f"{cyc.name}: a capture was superseded with no "
                           f"approval record")
                continue
            try:
                rec = json.loads(ap.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                bad.append(f"{cyc.name}: the approval is not valid JSON")
                continue
            missing = [k for k in ("authorized_by", "reason", "at",
                                   "superseded_sha256", "superseding_sha256")
                       if not str(rec.get(k, "")).strip()]
            if missing:
                bad.append(f"{cyc.name}: approval missing "
                           f"{', '.join(missing)}")
                continue

            # SELF-F07, raised by the BOOTSTRAP-003 cycle 04 reviewer:
            # "Supersession approval hashes need only be present; this check
            # does not compare them with the displaced and replacement bytes.
            # Preserved raw capture files need only exist."
            #
            # Correct, and the gap mattered. An approval is supposed to bind
            # to the exact bytes it approved, which is what stops one being
            # lifted and reused for a different supersession. Checking that
            # the field is filled in establishes that somebody typed sixty-four
            # characters, and nothing else. The bytes are right here.
            for a in displaced:
                n = a.get("attempt")
                kept = cyc / "captures" / f"attempt-{n:02d}" / "raw.md"
                if not kept.is_file():
                    bad.append(f"{cyc.name}: the displaced capture "
                               f"attempt-{n} was not kept")
                    continue
                got = hashlib.sha256(kept.read_bytes()).hexdigest()
                if got != rec.get("superseded_sha256"):
                    bad.append(
                        f"{cyc.name}: the approval names superseded bytes "
                        f"{str(rec.get('superseded_sha256'))[:12]}..., and the "
                        f"preserved attempt-{n} hashes to {got[:12]}.... The "
                        f"approval does not describe the capture it displaced.")

            live = cyc / "codex-output-raw.md"
            if not live.is_file():
                bad.append(f"{cyc.name}: no authoritative capture on disk to "
                           f"compare the approval against")
            else:
                got = hashlib.sha256(live.read_bytes()).hexdigest()
                if got != rec.get("superseding_sha256"):
                    bad.append(
                        f"{cyc.name}: the approval names superseding bytes "
                        f"{str(rec.get('superseding_sha256'))[:12]}..., and "
                        f"the capture now in place hashes to {got[:12]}.... "
                        f"The approval authorised different bytes from the "
                        f"ones that governed.")
    if bad:
        c.check(FAIL, "supersession records are incomplete", "\n".join(bad))
    elif sup:
        c.check(PASS, f"{sup} supersession(s), each approved and each keeping "
                      f"the capture it displaced")
    else:
        c.check(PASS, "no capture has been superseded")

    # The register's own obligation, checked rather than trusted.
    reg = REPO / "registers" / "implementer-disclosed.json"
    required = ("description", "discovery_source", "affected_component",
                "severity", "state", "proposed_repair", "evidence")
    if not reg.is_file():
        c.check(UNKNOWN, "the implementer-disclosed register is missing")
    else:
        try:
            rg = json.loads(reg.read_text(encoding="utf-8"))
            thin = [f"{k}.{f}" for k, v in rg.get("entries", {}).items()
                    for f in required if not v.get(f)]
            if thin:
                c.check(FAIL, "register entries missing required fields",
                        ", ".join(thin))
            else:
                c.check(PASS, f"{len(rg.get('entries', {}))} register "
                              f"entries, each complete")
        except json.JSONDecodeError as e:
            c.check(UNKNOWN, f"the register is not valid JSON: {e}")

    # The criterion names five checks and this file implemented three. The
    # two below were promised in the frozen document and absent from the code,
    # which is the gap SELF-F07 is about: a condition is only as good as the
    # checks under it, and a check that was never written reads exactly like
    # one that passed.
    #
    # Four: every finding a review reported appears in the ledger and has a
    # state the controller can reconstruct. The controller refuses outright
    # when that is false, so this asks it and reports the refusal rather than
    # reimplementing the rule and risking a second opinion that disagrees.
    for run in runs():
        rel = f"runs/{run.name}/plan-review"
        rc, out = tool(str(SCRIPTS / "loop_state.py"), "--review", rel,
                       "--development", "--json")
        if rc == 0:
            c.check(PASS, f"{run.name}: every reported finding is in the "
                          f"ledger with a reconstructable state")
        else:
            _why = next((l.strip() for l in out.splitlines() if l.strip()),
                        "(no reason given)")
            c.check(FAIL, f"{run.name}: the controller cannot account for its "
                          f"own findings", _why)

    # Five: an approval package can be produced for each run, or the run says
    # why it cannot. A refusal here is not a failure of this condition: the
    # package refusing with a stated reason is the behaviour EC-1 requires of
    # it. What would fail is a package that could be produced and was not, or
    # one that fell over without saying anything.
    for run in runs():
        _out = REPO / "_tmp" / f"ec3-{run.name}.md"
        _out.parent.mkdir(parents=True, exist_ok=True)
        rc, out = tool(str(SCRIPTS / "approval_package.py"), "--run", run.name,
                       "--type", "plan", "--out", str(_out))
        if rc == 0:
            c.check(PASS, f"{run.name}: an approval package can be produced")
        elif "CANNOT_ESTABLISH" in out:
            c.check(PASS, f"{run.name}: no package, and the run says why",
                    next((l.strip() for l in out.splitlines()
                          if "CANNOT_ESTABLISH" in l), ""))
        else:
            c.check(FAIL, f"{run.name}: no package and no stated reason",
                    out.strip()[-300:] or "(no output at all)")
        _out.unlink(missing_ok=True)
    return c


# ---------------------------------------------------------------- EC-4
def ec4() -> Condition:
    c = Condition(
        "EC-4", "independent verification of blocking repairs",
        "whether each reviewer's evidence is adequate for a blocking item")

    bf = SPECS / "blocking-defects.json"
    if not bf.is_file():
        c.check(UNKNOWN, "no blocking-defect classification to check against")
        return c
    try:
        blocking = json.loads(bf.read_text(encoding="utf-8")).get("blocking", {})
    except json.JSONDecodeError as e:
        c.check(UNKNOWN, f"the classification is not valid JSON: {e}")
        return c

    # SELF-F07, the row the reviewer was bluntest about: "Any nonempty cycle
    # reference passes. This function neither validates the referenced cycle
    # nor checks the reviewer quotation, stated limits, conclusion, or
    # independent execution."
    #
    # All true. The criterion promises three things and the code did one of
    # them, and the one it did was the weakest: that somebody had typed
    # something into a field. A reference to a cycle that does not exist, or
    # that failed its own conformance gate, or whose preserved review never
    # mentions the item, all passed.
    #
    # The reference is expected as RUN/cycle-NN, naming where the examination
    # is recorded, so that it can be followed rather than taken on trust.
    for name, item in sorted(blocking.items()):
        cyc = item.get("independently_examined_in_cycle")
        if not cyc:
            # `.get(key, default)` returns the default only when the key is
            # absent, so a JSON null arrived here as the word None and the
            # line read "Its repair landed on None, after the last frozen
            # cycle", which is both ugly and a claim. Six entries written on
            # 13 October carry null deliberately, because their repair dates
            # have not been reconciled from the ledger yet. D04-F01 is this
            # same mistake one file over, and is why authority.text() exists.
            _landed = item.get("repair_landed")
            _landed = _landed.strip() if isinstance(_landed, str) else ""
            c.check(UNKNOWN, f"{name}: no reviewer has examined its repair",
                    f"Its repair landed on {_landed}, after the last frozen "
                    f"cycle." if _landed else
                    "No repair date is recorded for it either, so this says "
                    "only that no\nexamination has been recorded, and not "
                    "that a repair is waiting for one.")
            continue

        _parts = str(cyc).split("/")
        if len(_parts) != 2 or not _parts[1].startswith("cycle-"):
            c.check(FAIL, f"{name}: the examination reference is not a cycle",
                    f"got {cyc!r}, expected RUN/cycle-NN. A reference nobody "
                    f"can follow is\nnot a reference.")
            continue

        _dir = REPO / "runs" / _parts[0] / "plan-review" / _parts[1]
        if not _dir.is_dir():
            c.check(FAIL, f"{name}: names a cycle that does not exist",
                    str(cyc))
            continue

        # Named is not the same as valid. A cycle that fails its own
        # conformance gate cannot support an authoritative anything, so an
        # examination recorded against one establishes nothing.
        rc, out = tool(str(SCRIPTS / "validate_cycle.py"), str(_dir))
        if rc != 0 or "MC2_CONFORMANCE: PASS" not in out:
            c.check(FAIL, f"{name}: the cycle it names does not pass MC-2",
                    f"{cyc} cannot support an authoritative finding, so an "
                    f"examination\nrecorded against it establishes nothing.")
            continue

        # And the reviewer's own preserved words must actually mention it.
        # Without this, any valid cycle could be named for any item.
        _raw = _dir / "codex-output-raw.md"
        if not _raw.is_file():
            c.check(FAIL, f"{name}: the cycle it names preserved no review",
                    str(cyc))
        elif name not in _raw.read_text(encoding="utf-8", errors="replace"):
            c.check(FAIL, f"{name}: the review in {cyc} never mentions it",
                    "The cycle is valid and its preserved output does not "
                    "name this item, so it\nis not what was examined there.")
        else:
            c.check(PASS, f"{name}: examined in {cyc}, which passes MC-2 and "
                          f"whose preserved review names it")

    # Execution, which is the half the ticks above cannot reach. The cycle
    # exists, it is valid, and the reviewer's preserved words name the item.
    # None of that establishes that anybody RAN anything, and that is Alex
    # Zamurko's standard for a behavioural claim.
    #
    # Until 14 October this said so and stopped, unconditionally. He named the
    # defect in that on 13 October: "The inspected implementation still adds
    # CANNOT_ESTABLISH for independent execution unconditionally. Replace this
    # with validation of actual GitHub execution evidence, linked to the exact
    # commit and reviewed finding."
    #
    # He is right, and it is the same shape as everything else here. A
    # condition that answers CANNOT_ESTABLISH whatever the evidence says
    # cannot be satisfied, and a check that can never pass is worth what one
    # that always passes is worth. It was honest about its ignorance and
    # incapable of ever stopping being ignorant.
    #
    # So this now reads the evidence and says which of four things is true for
    # each item: no evidence; evidence that does not cover it; evidence bound
    # to a different commit or whose preserved log no longer matches its
    # digest; or a run on this exact commit with its output preserved intact.
    # Only the last is a pass, and the pass is still only the mechanical half.
    # Whether a run is adequate for a blocking item stays in the line below,
    # which is his.
    c.check(*execution_evidence(blocking))
    return c


def _api_disagrees(r: dict) -> str:
    """Why this record does not match GitHub's own reply, or "" if it does.

    Alex Zamurko, 15 October 2026: "It does not independently verify that the
    claimed GitHub run, job, conclusion and coverage are genuine... A locally
    authored evidence record with a matching log digest can therefore satisfy
    the mechanical check without demonstrating that GitHub independently
    executed the named repair."

    The recorder now fetches the run and preserves GitHub's replies verbatim.
    This is the half that makes that worth doing: the entry's commit and
    conclusion are checked against those replies rather than read out of the
    entry. A record whose fields contradict the reply it was supposedly
    derived from is not weak evidence; it is a record of something that did
    not happen.

    It does not establish that the preserved reply is itself genuine. Nothing
    inside a repository can establish that about a file in the repository.
    The URL is recorded so a reviewer can re-fetch in thirty seconds, which is
    the one step no check here can take for them.
    """
    for key, want_sha, label in (("api_run", "head_sha", "commit"),
                                 ("api_jobs", None, "jobs")):
        meta = r.get(key) or {}
        p = REPO / str(meta.get("path", ""))
        if not meta.get("path"):
            return (f"it records no preserved GitHub reply ({key}), so "
                    f"nothing it says was\n      checked against GitHub")
        if not p.is_file():
            return f"its preserved GitHub reply is gone ({meta.get('path')})"
        if hashlib.sha256(p.read_bytes()).hexdigest() != meta.get("sha256"):
            return (f"its preserved GitHub reply no longer matches the digest "
                    f"recorded with it\n      ({meta.get('path')})")
        try:
            said = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return f"its preserved GitHub reply is not valid JSON: {e}"

        if want_sha:
            got = str(said.get(want_sha, "")).lower()
            if got != str(r.get("commit", "")).lower():
                return (f"the record says it examined "
                        f"{str(r.get('commit'))[:12]}, and GitHub's own reply "
                        f"says\n      {got[:12] or 'nothing'}")
        else:
            job = next((j for j in said.get("jobs", [])
                        if j.get("name") == r.get("job")), None)
            if job is None:
                return (f"GitHub's reply contains no job named "
                        f"{str(r.get('job'))!r}")
            if job.get("conclusion") != r.get("conclusion"):
                return (f"the record calls the job {str(r.get('conclusion'))!r} "
                        f"and GitHub's reply says\n      "
                        f"{str(job.get('conclusion'))!r}")
    return ""


def _is_demonstration(r: dict) -> bool:
    """A run recorded to show a failure, rather than to exercise a repair.

    Alex Zamurko, 15 October 2026: "Preserve failure-run evidence separately
    from successful repair-verification evidence." SELF-F08's red run proves
    the pipeline reports failure; it is not evidence that any repair holds,
    and pooling the two would let the thing built to prove failure count as
    proof of success.
    """
    return (str(r.get("purpose", "")) == "failure_demonstration"
            or r.get("conclusion") == "failure")


def execution_evidence(blocking: dict) -> tuple[str, str, str]:
    """What the recorded GitHub runs establish about the blocking items.

    Returns one (state, name, detail) for the condition, rather than one per
    item, because the question Alex Zamurko asked is about the set: has the
    work been independently executed, or has it not.
    """
    ev = REPO / "evidence" / "execution-evidence.json"
    if not ev.is_file():
        return (UNKNOWN, "no independent execution evidence has been recorded",
                "Nothing here has been shown to run anywhere but on the "
                "implementing agent's\nown machine, which is the one place "
                "Alex Zamurko's standard excludes.\n\n"
                "  Record a run with scripts/record_execution_evidence.py "
                "once a GitHub run\n  exists against the frozen commit.")
    try:
        runs = json.loads(ev.read_text(encoding="utf-8")).get("runs", [])
    except json.JSONDecodeError as e:
        return (UNKNOWN, "the execution evidence cannot be read",
                f"{ev.name} is not valid JSON: {e}\n\n  It is written by "
                f"scripts/record_execution_evidence.py and is not meant to be "
                f"edited\n  by hand. A record this condition cannot parse is "
                f"not weak evidence, it is\n  none.")

    at_head, _src = candidate()
    if not at_head:
        return (UNKNOWN, "no commit could be established to tie evidence to",
                _src)

    # A run is usable for an item when it names that item, ran against the
    # commit in front of us, and its preserved output still matches the digest
    # recorded when it was taken. The last of those is what stops this
    # becoming a URL somebody typed.
    # Coverage is read out of the preserved output, not out of the claim about
    # it. Alex Zamurko, 15 October 2026: "Verify the claimed finding coverage
    # against preserved execution results, not just the submitter's `covers`
    # field." Until then a finding was covered because somebody typed its name
    # into a JSON file, which is a check passing for a reason other than the
    # one it is named for, in the condition written to stop exactly that.
    #
    # The declared list is kept and reconciled rather than discarded: a run
    # claiming to cover something its output never mentions is itself worth
    # reporting, which is D02-F01's lesson in findings_format one layer up.
    #
    # A deliberately failing run is evidence of something else, so it is
    # counted separately and never toward a repair being exercised.
    usable, demos, problems = {}, {}, []
    for r in runs:
        rid = r.get("run_id", "?")
        if r.get("commit") != at_head:
            problems.append(f"run {rid} examined {str(r.get('commit'))[:12]}, "
                            f"the candidate is {at_head[:12]}")
            continue
        log = REPO / str(r.get("log", ""))
        if not log.is_file():
            problems.append(f"run {rid}: its preserved log is gone "
                            f"({r.get('log')})")
            continue
        raw = log.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r.get("log_sha256"):
            problems.append(f"run {rid}: the preserved log no longer matches "
                            f"the digest recorded with it")
            continue
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            problems.append(f"run {rid}: its preserved log cannot be decoded "
                            f"as UTF-8 ({e.reason}), so nothing can be read "
                            f"out of it")
            continue
        _no = _api_disagrees(r)
        if _no:
            problems.append(f"run {rid}: {_no}")
            continue

        declared = {str(x) for x in r.get("covers", [])}
        observed = {f for f in blocking if f in text}
        over = sorted(declared - observed)
        if over:
            problems.append(
                f"run {rid}: declared coverage its output does not support: "
                + ", ".join(over))
        into = demos if _is_demonstration(r) else usable
        for fid in sorted(observed):
            into.setdefault(fid, []).append(r)

    missing = sorted(k for k in blocking if k not in usable)
    detail = ""
    if problems:
        detail = ("Evidence present and not usable:\n    "
                  + "\n    ".join(problems[:6]) + "\n\n  ")

    if not blocking:
        return (UNKNOWN, "nothing is classified as blocking, so there is "
                         "nothing to find evidence for", detail)
    if missing:
        return (UNKNOWN, f"{len(missing)} of {len(blocking)} blocking item(s) "
                         f"have no usable execution evidence",
                detail + ", ".join(missing) +
                "\n\n  Recorded runs that name an item, ran against this "
                "exact commit, and whose\n  preserved output still matches "
                "its digest are the only ones counted. The\n  rest are listed "
                "above with the reason.")

    _shown = sorted({r["run_id"] for rs in usable.values() for r in rs})
    _demo = sorted({r["run_id"] for rs in demos.values() for r in rs})
    return (PASS, f"all {len(blocking)} blocking item(s) were exercised by "
                  f"{len(_shown)} run(s) on {_src}",
            detail + f"runs {', '.join(_shown)}, each against {at_head[:12]}, "
                     f"each with its output\n  preserved, matching the digest "
                     f"taken at the time, and naming the item itself"
                     + (f"\n\n  Kept separate: run(s) {', '.join(_demo)} "
                        f"demonstrate a failure rather than a\n  repair, and "
                        f"count toward neither." if _demo else "") +
            "\n\n  This establishes that the work ran on a machine the "
            "implementing agent does\n  not control, that the run named this "
            "exact commit, and that its preserved\n  output mentions the item."
            " It does not establish that the run is genuine:\n  nothing here "
            "contacts GitHub, so a locally written record with a matching\n  "
            "digest satisfies these checks. Re-fetching each URL is a "
            "reviewer's step and\n  is the reason the URL is recorded. "
            "Whether any of it is adequate for a\n  blocking item is the "
            "judgement below.")


def candidate() -> tuple[str, str]:
    """The commit the exit evidence is about, and where that came from.

    Returns (sha, source). An empty sha means neither could be established.

    Alex Zamurko, 15 October 2026: "Match evidence to an explicitly frozen
    candidate SHA, not indiscriminately to the latest repository HEAD...
    Committing evidence after the tested commit changes HEAD, potentially
    invalidating the evidence it records."

    Binding to HEAD is circular: recording the evidence moves the thing the
    evidence is compared against. It cost a two-and-a-half-hour sweep on 12
    October, when a one-line commit after the sweep made EC-2 correctly report
    that the log described a different commit.

    HEAD remains the fallback, because a repository with no frozen candidate
    is one where nobody has said which commit is under consideration, and
    comparing against HEAD is a better answer than refusing to say anything.
    Which of the two was used is returned, and reported, so a reader never has
    to guess which question was asked.
    """
    f = SPECS / "frozen-candidate.json"
    if f.is_file():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            sha = str(d.get("commit", "")).strip().lower()
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha, "the frozen candidate"
        except json.JSONDecodeError:
            pass
    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip(), "HEAD, because no candidate is frozen"
    return "", "neither a frozen candidate nor HEAD could be established"


def frozen_criteria() -> str | None:
    """Refuse everything if the criteria are not the ones that were frozen.

    A document that says "frozen" and is editable without consequence says
    nothing. This makes the word mean something: the digest recorded beside it
    is checked before any condition is reported, and a mismatch stops the run
    rather than producing a verdict against criteria nobody agreed to.

    It is not tamper-proofing. Anyone who can edit the document can edit the
    digest, which is AR-1 and is accepted for bootstrap. What it does is make
    a change to the bar a deliberate act with two files in the diff, rather
    than something that can drift under a decision while nobody is looking.
    """
    doc = SPECS / "BOOTSTRAP-EXIT-CRITERIA.md"
    rec = SPECS / "BOOTSTRAP-EXIT-CRITERIA.sha256"
    if not doc.is_file():
        return "the exit criteria document is missing"
    if not rec.is_file():
        return ("no recorded digest for the exit criteria, so there is "
                "nothing to say\n  which version this run is checking "
                "against")
    want = rec.read_text(encoding="utf-8").split()[0].strip()
    got = hashlib.sha256(doc.read_bytes()).hexdigest()
    if want != got:
        return ("the exit criteria have changed since they were frozen.\n"
                f"  frozen   {want}\n  on disk  {got}\n\n"
                "  Nothing is reported against criteria that are not the ones "
                "agreed. If the\n  change is intended, it takes a new version "
                "and a new digest, with the reason\n  recorded, rather than "
                "an edit. If it is not intended, find out what changed\n  "
                "before trusting anything else in this repository.")
    return None


def main() -> int:
    print("bootstrap exit criteria, machine-checkable half")
    print(f"  {REPO}")
    print("  specs/BOOTSTRAP-EXIT-CRITERIA.md holds the judgements this "
          "cannot make.")

    _bad = frozen_criteria()
    if _bad:
        print(f"\n  [CANNOT RUN] {_bad}")
        return 2
    print("  criteria digest matches the frozen record.")

    conditions = [ec1(), ec2(), ec3(), ec4()]
    for c in conditions:
        c.report()

    verdicts = [c.verdict for c in conditions]
    print("\n" + "-" * 68)
    for c in conditions:
        print(f"  {c.cid}  {c.verdict}")

    print("\n  NO OVERALL VERDICT IS PRINTED HERE, and that is deliberate.")
    print("  Each condition above has a judgement reserved to Alex Zamurko, "
          "and none of")
    print("  them is derivable from anything this script can read. Totalling "
          "the four")
    print("  into a yes would be this tool making his decision quietly, "
          "which is the")
    print("  behaviour the protocol exists to prevent.")

    if FAIL in verdicts:
        return 1
    if UNKNOWN in verdicts:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
