#!/usr/bin/env python3
"""Break each repair in turn. Does its control notice?

    python _probe\\mutate_repairs.py

Exit 0 = every repair has a control that goes red when the repair is removed.
Exit 1 = one does not, and it is named.
Exit 2 = could not run.

Why
---
Eight findings were repaired on 26 September and each commit claims a control
that holds it. A control written beside a repair, by the same hand, on the
same afternoon, is exactly the kind that passes because the repair happens to
be there rather than because it is checking for it. That is the defect class
this whole run keeps finding, and asserting it about my own work without
testing it would be the same mistake with a different subject.

So each repair is removed, one at a time, from the real file, and its suite is
run. The repair's control must go red, and the failure must mention something
specific to that repair rather than any failure at all: a suite that goes red
for an unrelated reason establishes nothing about the control named.

`mutate_citation_suite.py` does this for the extractor and has done since
September; the review layer, which is the more consequential of the two, has
had no equivalent. This is a start on that rather than the whole of it: one
mutation per repair as each is made, not a general mutation probe. A repair
that arrives without a line here has not been shown to be watched.

A crashed suite is refused rather than counted, for the reason
`vacuity_sweep.py` records at length: a traceback is the one signal a failing
control never produces, and reading a crash as a catch means the control was
never consulted.

The tree is checked before the first mutation and again after the last. An
earlier run of this probe left `run_review.py` mutated over a weekend, its
protocol-integrity check replaced with `if False:`. The restore runs in a
`finally`, which does not survive the process being killed, and nothing else
in the repository would have noticed a check that had been switched off.
Every suite run in that window passed for a reason other than the one it
names, which is precisely the defect this probe was written to find, arriving
by way of the probe. So a run refuses to start against a tree that is already
dirty, and says so loudly if it fails to leave one clean.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# The mutation currently applied, written before the file is touched and
# removed after it is put back.
#
# The `finally` below covers an exception and a Ctrl+C. It does not run when
# the process is killed outright, which is what closing a terminal window does.
# On 5 October that left `if False:` sitting in loop_state.py, with this probe
# reporting nothing at all because it never reached its own report. The start
# guard caught it at the next run, which is one run late: a commit in between
# would have carried a disabled check into the record, and the suites would all
# have passed.
#
# So the mutation in progress is recorded on disk and the next run puts it
# back. Untracked on purpose: a file that exists only while a mutation is
# applied has no business in the history.
ACTIVE = Path(__file__).resolve().parent / ".active-mutation.json"

# (finding, file, exact source to replace, replacement, suite, needle)
#
# The needle is matched against the suite's own failure text and has to be
# specific to the control the repair is supposed to have. "expected FAIL" or a
# bare non-zero exit would be satisfied by any breakage at all.
MUTATIONS = [
    ("C01-F01  the reopening guard in the shared evaluator",
     "cycle_projection.py",
     # Disambiguated when C02-F02 gave REJECT_WITH_REASON the same guard, at
     # which point this anchor matched two branches and the probe refused rather
     # than mutating an arbitrary one. The comment line below it belongs to the
     # ACCEPT branch alone.
     "            if self.reopened_at is not None and c < self.reopened_at:\n"
     "                # Insertion order says when a thing was written down.",
     "            if False:\n"
     "                # Insertion order says when a thing was written down.",
     "test_ledger.py",
     # "backdated" appears in the [ok] text and in comments, not in any
     # FAILURE message, so the first version of this needle reported WRONG
     # CONTROL about a control that was working. The failures say "predates
     # the reopening" and "dated before the reopening"; this matches both.
     "the reopening"),

    ("C01-F02  the ceiling binding at every boundary",
     "loop_state.py",
     "        if n >= MAX_VALID_CYCLES:\n"
     "            lines.append(f\"        {status} at n={n} was cleared, and the \"",
     "        if False:\n"
     "            lines.append(f\"        {status} at n={n} was cleared, and the \"",
     "test_ledger.py",
     "fifth cycle"),

    ("C01-F03  check 9 reading the governing artifacts",
     "validate_cycle.py",
     "    if bad:\n"
     "        return [\"the governing artifacts",
     "    if False:\n"
     "        return [\"the governing artifacts",
     "test_validate_cycle.py",
     "governing"),

    ("C01-F04  MC-2 validating the pin history before replaying it",
     "validate_cycle.py",
     "        expect = run_pins.governing_pin_hashes(run, run_dir,\n"
     "                                               int(target[\"cycle\"]))",
     "        expect = run_pins.pin_hashes_for_cycle(\n"
     "            run, run_pins.load_amendments(run_dir), int(target[\"cycle\"]))",
     "test_validate_cycle.py",
     "amendment history"),

    ("C01-F05  no default classification for a run",
     "loop_state.py",
     "    kind, problem = run_pins.run_kind(run)\n"
     "    if problem:",
     "    kind, problem = run_pins.run_kind(run)\n"
     "    problem = None\n"
     "    kind = kind or run_pins.PROTOCOL\n"
     "    if problem:",
     "test_ledger.py",
     "bootstrap_review"),

    ("C01-F06  a reported finding must have a state",
     "loop_state.py",
     "    if _stateless:\n"
     "        raise CannotCalculate(",
     "    if False:\n"
     "        raise CannotCalculate(",
     "test_ledger.py",
     "authoritative state"),

    ("C01-F07  cycle identity, not only uniqueness",
     "validate_cycle.py",
     "        ok7 = not clashes and not mismatch",
     "        ok7 = not clashes",
     "test_validate_cycle.py",
     "check 7"),

    ("C01-F08  the commit and the hash describing one document",
     "run_review.py",
     "    if _committed != sha256_file(protocol):",
     "    if False:",
     "test_run_review.py",
     "protocol"),

    ("C02-F03  the age exemption refused to evidence that is not old",
     "validate_cycle.py",
     "    if _gph is None and _gp is None:\n"
     "        if _modern:",
     "    if _gph is None and _gp is None:\n"
     "        if False:",
     "test_validate_cycle.py",
     "artifacts were preserved"),

    ("C02-F04  a recurrence must not stand against a RESOLVED entry",
     "loop_state.py",
     "            if state_after(f, upto) == RESOLVED:\n"
     "                _unreopened.append(",
     "            if False:\n"
     "                _unreopened.append(",
     "test_ledger.py",
     "a recurrence reported against a RESOLVED ledger entry"),

    ("C02-F07  the gate's evidence must name the target it decides about",
     "bootstrap_gate.py",
     "    if _tdigest not in _input:",
     "    if False:",
     "test_bootstrap_gate.py",
     "never names"),

    # The first version of this mutation removed the `n >= 1` guard and was
    # reported MISSED, correctly. cycle-00 parses as 0 either way and check 7
    # refuses it for mismatching a target that says cycle 1, so that control
    # passes whether the guard is there or not: it exercises the mismatch path,
    # not the rule. The rule this finding is about is the digit count, which is
    # what the checker and the controller disagreed on, so that is what gets
    # removed here. Putting it back to (\d+) makes cycle-1 and cycle-001 parse
    # as cycle 1 again and satisfy check 7, which is the defect exactly.
    ("C02-F05  one cycle-directory grammar, not two that disagree",
     "run_pins.py",
     "CYCLE_DIR = re.compile(r\"cycle-(\\d{2})\\Z\")",
     "CYCLE_DIR = re.compile(r\"cycle-(\\d+)\\Z\")",
     "test_validate_cycle.py",
     "cycle-1 passed MC-2"),

    # Not the function, the call. Deleting the body would also take the
    # damaged-generation refusal with it, and the control that then goes red is
    # about mismatched findings rather than about ownership. Removing the call
    # leaves exactly the pre-repair behaviour: recovery heals a designation that
    # exists and does nothing for one that was earned and never written.
    ("C02-F06  an interrupted designation is recovered before a new candidate",
     "run_review.py",
     "    _recovered = recover_pending_designation(cycle)",
     "    _recovered = None",
     "test_run_review.py",
     "designated after an interruption"),

    # The comparison, not the derivation. Removing the git call would make the
    # check fail to run, which goes red for the wrong reason: a checker that
    # cannot derive anything is not the same as one that derives and does not
    # look. This leaves the derivation in place and stops it mattering, which is
    # exactly the pre-repair behaviour where each hash was well formed on its own.
    ("C02-F08  the reviewed diff is the change between the target's commits",
     "validate_cycle.py",
     "                    if _actual != str(_recorded):",
     "                    if False:",
     "test_run_review.py",
     # The CONTROL's complaint, not the checker's refusal. Reported as a
     # [WRONG CONTROL] on the first run, correctly: with the comparison removed
     # nothing refuses, so the checker's message is exactly the text that cannot
     # appear. What appears is the control saying the swap was accepted.
     #
     # Reported [WRONG CONTROL] a second time too, and that one was not about
     # the needle. The control's fixture was being refused by check 10 over a
     # stale digest in codex-input.md, so it had never established anything
     # about check 14. Two probe runs, two different faults in my own work, both
     # of them invisible to a green suite.
     #
     # And a third time, after C02-F08's second pass added the blob comparison.
     # That check subsumes this one for a moved candidate, so the swap control
     # stopped isolating this rule: removing the digest comparison left the
     # scenario refused by the stronger check. The needle now points at the
     # control that tampers with the recorded digest alone, which is the only
     # case this rule answers for by itself.
     "recording a change set these commits do not produce"),

    # Three fallbacks, three mutations. One would leave the other two unwatched
    # while the line reported them as covered, which is the mistake C02-F02
    # already made once.
    ("C02-F09a  a declared artifact's snapshot is not optional",
     "validate_cycle.py",
     "    if strict_markers:",
     "    if False:",
     "test_run_review.py",
     "snapshot of the test results was deleted"),

    ("C02-F09b  the approval record's snapshot is not optional",
     "validate_cycle.py",
     "    elif _snap_approval is not None and not _snap_approval.is_file() and _mod13:",
     "    elif False:",
     "test_run_review.py",
     "snapshot of the approval record was deleted"),

    ("C02-F09c  the approved plan's snapshot is not optional",
     "validate_cycle.py",
     "                if _mod13 and not snap.is_file():",
     "                if False:",
     "test_run_review.py",
     "snapshot of the approved plan was deleted"),

    ("C02-F10a  the control sources are preserved, not only listed",
     "run_review.py",
     "        _dst.write_bytes((REPO / _e[\"path\"]).read_bytes())\n"
     "        if sha256_file(_dst) != _e[\"sha256\"]:",
     "        if False:",
     "test_run_review.py",
     "bytes were not preserved"),

    ("C02-F10b  a control suite that does not pass has to be named",
     "run_review.py",
     "    if _unexpected:",
     "    if False:",
     "test_run_review.py",
     "froze with a failing control suite and said nothing"),

    # C02-F03's second pass, raised again by cycle 03. Three rules: the format
    # dates the record, an unknown format is refused, and the marker list still
    # dates the targets frozen before the field existed.
    ("C02-F03b  a declared evidence format dates the record on its own",
     "validate_cycle.py",
     "    if fmt is not None:",
     "    if False:",
     "test_validate_cycle.py",
     "declaring an evidence format while omitting"),

    ("C02-F03c  an evidence format this gate does not know is refused",
     "validate_cycle.py",
     "    if _fmt is not None and _fmt not in run_pins.EVIDENCE_FORMATS:",
     "    if False:",
     "test_validate_cycle.py",
     "evidence format this gate does not know"),

    ("C02-F03d  the auxiliary manifest dates a record too",
     "validate_cycle.py",
     "    \"auxiliary_evidence_sha256\",      # B03-F02, the control manifest\n",
     "",
     "test_validate_cycle.py",
     "dated only by its auxiliary evidence manifest"),

    # C02-F04's second pass. Two rules: a transcription that disagrees with the
    # review is refused, and the classification every later check reads comes
    # from the review rather than from the transcription.
    ("C02-F04b  a restated classification is refused, not overruled quietly",
     "loop_state.py",
     "        if _mismatch:",
     "        if False:",
     "test_ledger.py",
     "recorded in findings.json as a new finding"),

    ("C02-F04c  the classification comes from the reparsed review",
     "loop_state.py",
     "            if f.get(\"id\") in raw_kinds:",
     "            if False:",
     "test_ledger.py",
     "carries no classification"),

    # C03-F02, Alex Zamurko's ruling of 2 October and its two corrections.
    # Three rules: nothing enters the scope by being imported without being
    # declared, the list must be what its own history produces, and a scope
    # change that exists only on disk is not a scope change.
    ("C03-F02a  an undeclared import is refused, not absorbed",
     "bootstrap_gate.py",
     "    if missed:",
     "    if False:",
     "test_bootstrap_gate.py",
     "imported a module the manifest does not declare"),

    ("C03-F02b  the manifest's list must be what its history produces",
     "bootstrap_gate.py",
     "    if sorted(replayed) != sorted(comps):",
     "    if False:",
     "test_bootstrap_gate.py",
     "not what its history produces"),

    # This line used to point at a `git status --porcelain` guard. Cycle 04's
    # repair replaced that query with a byte comparison against HEAD, so the
    # needle stopped existing and the probe reported itself broken rather than
    # reporting a catch. The rule is the same one; the line now names where it
    # actually lives.
    ("C03-F02c  a scope change that exists only on disk is refused",
     "bootstrap_gate.py",
     "    if committed(COVERED_MANIFEST) != _live:",
     "    if False:",
     "test_bootstrap_gate.py",
     "a scope change that was never committed"),

    # C02-F02's second pass. One rule, two guards, because §5 gives a finding
    # two dispositions and a guard on one of them is a guard on half the rule.
    # That is how this finding arrived twice.
    ("C02-F02d  an acceptance cannot predate the raise, in replay",
     "cycle_projection.py",
     "            if self.raised_at is not None and c < self.raised_at:\n"
     "                return False, _before_raise(self.raised_at, \"accepted\")",
     "            if False:\n                pass",
     "test_ledger.py",
     "dated before the finding was raised took effect"),

    ("C02-F02e  nor can a rejection, in replay",
     "cycle_projection.py",
     "            if self.raised_at is not None and c < self.raised_at:\n"
     "                return False, _before_raise(self.raised_at, \"rejected\")",
     "            if False:\n                pass",
     "test_ledger.py",
     "rejection dated before the raise took effect"),

    # Five lines, one anchor. The byte comparison replaced the header
    # comparison as the rule on 5 October, so there is now one rule where there
    # were four, and mutating the header comparison changes nothing: the bytes
    # still differ and the gate still refuses. Pointing all five at the rule and
    # keeping their separate needles asserts something the single line cannot,
    # that each control is still live and still goes red when the rule goes.
    ("C02-F08b  the preserved patch names the change's own objects",
     "validate_cycle.py",
     "                        elif _pbytes != _gen:",
     "                        elif False:",
     "test_run_review.py",
     "patch of an entirely different change"),

    # C02-F08's third pass. Cycle 04 named three ways past the comparison as it
    # stood, and one mutation removing the whole comparison would report all
    # three as watched while any one of them could be reintroduced alone. So
    # each hole is reopened on its own, in the shape it had before the repair.
    ("C02-F08c  paths and modes are part of what the patch must agree about",
     "validate_cycle.py",
     "                        elif _pbytes != _gen:",
     "                        elif False:",
     "test_run_review.py",
     "naming a file the change never touched"),

    ("C02-F08d  two files moving between the same objects are two entries",
     "validate_cycle.py",
     "                        elif _pbytes != _gen:",
     "                        elif False:",
     "test_run_review.py",
     "showing one of two identical changes"),

    ("C02-F08e  an empty change set is compared like any other",
     "validate_cycle.py",
     "                        elif _pbytes != _gen:",
     "                        elif False:",
     "test_run_review.py",
     "accepted any patch at all"),

    # The hunk bodies, which the header comparison could not reach and which I
    # had recorded as a known limit rather than closed.
    ("C02-F08f  the hunks are part of the patch, not only its headers",
     "validate_cycle.py",
     "                        elif _pbytes != _gen:",
     "                        elif False:",
     "test_run_review.py",
     "a line the candidate does not contain"),

    # D02-F01, BOOTSTRAP-003 cycle 02. The signal net back to "any canonical
    # identifier anywhere", which is what made a correct zero-finding review
    # unrecordable.
    # Anchor moved when the inline pattern became the shared DECLARATION
    # constant. The signal tuple is where the zero-finding case is decided, so
    # putting the bare identifier back there restores exactly the behaviour
    # that made a correct review unrecordable.
    ("D02-F01  a named earlier finding is a reference, not a declaration",
     "findings_format.py",
     "    DECLARATION,\n)",
     "    re.compile(r\"\\b[A-Z]{0,2}\\d{2}-F\\d{2,3}\\b\"),\n)",
     "test_run_review.py",
     "a zero-finding review that names a demonstrated repair"),

    # SELF-F01, third pass. The package back to the ledger's cached state.
    ("SELF-F01  the package reports the controller's state, not the cache",
     "approval_package.py",
     "        by_state: dict[str, list[str]] = {\n"
     "            \"OPEN\": list(_proj.get(\"open\", [])),\n"
     "            \"RESOLVED\": list(_proj.get(\"resolved\", [])),\n"
     "            \"DISPUTED\": list(_proj.get(\"disputed\", [])),\n"
     "        }",
     # The old behaviour exactly, including the three keys, so the mutation
     # reproduces the defect rather than crashing the tool. Its first version
     # left by_state without them and the package died on a KeyError, which
     # the probe correctly reported as the wrong control: a crash is not the
     # defect, and a control that fires on one establishes nothing about it.
     "        by_state = {\"OPEN\": [], \"RESOLVED\": [], \"DISPUTED\": []}\n"
     "        for _fid, _f in sorted(data.get(\"findings\", {}).items()):\n"
     "            by_state.setdefault(_f.get(\"state\", \"?\"), []).append(_fid)",
     "test_approval_package.py",
     "presenting a cleaner state than the authoritative one"),

    # D02-F01's second pass, BOOTSTRAP-003 cycle 03. Two rules again: quoted
    # material is not a declaration, and declarations are reconciled against
    # what parsed rather than consulted only when nothing did.
    ("D02-F01b  a fenced block is quoted material, not a declaration",
     "findings_format.py",
     "    text = mask_fences(raw)",
     "    text = raw",
     "test_run_review.py",
     "a finding block quoted inside a code fence is not a declaration"),

    ("D02-F01c  declarations are reconciled with what actually parsed",
     "findings_format.py",
     "    if _unaccounted:",
     "    if False:",
     "test_run_review.py",
     "a malformed declaration beside a finding that parses"),

    # SELF-F04, raised by the BOOTSTRAP-003 cycle 03 reviewer. Three lines
    # because the repair makes three separate claims, and a single mutation
    # would let two of them rot while the probe stayed green.
    #
    # First: the machine interface answers on the path where nothing was
    # computed. Falling through to the prose return is the defect exactly as
    # reported, prose under exit 0 to a caller that asked for JSON.
    ("SELF-F04  --json answers even when no boundary was walked",
     "loop_state.py",
     "        if getattr(a, \"as_json\", False):\n"
     "            print(json.dumps({\n"
     "                \"governing_boundary\": None,",
     "        if False:\n"
     "            print(json.dumps({\n"
     "                \"governing_boundary\": None,",
     "test_approval_package.py",
     "did not emit JSON"),

    # Second: the sets are omitted rather than emitted empty. This is the half
    # that matters most and is the easiest to lose, because emitting [] looks
    # tidier and passes any control that only checks the output is JSON.
    ("SELF-F04b  an unwalked boundary reports no sets, not empty ones",
     "loop_state.py",
     "                \"sets_established\": False,",
     "                \"sets_established\": False,\n"
     "                \"open\": [], \"resolved\": [], \"disputed\": [],",
     "test_approval_package.py",
     "a boundary it never walked"),

    # Third: the package states a reason instead of dying. Narrowing the except
    # to something that cannot be raised there lets CannotCalculate escape as a
    # traceback, which is the behaviour before the repair.
    ("SELF-F04c  an unreadable cycle record is refused, not crashed",
     "approval_package.py",
     "            except loop_state.CannotCalculate as e:",
     "            except ValueError as e:",
     "test_approval_package.py",
     "crashed rather than refusing"),

    # SELF-F06, both halves. The lock, and the record of who holds it.
    #
    # Without O_EXCL the open succeeds whether or not a lock is there, so two
    # runs proceed and delete each other's working copies, which is the
    # defect as reported.
    ("SELF-F06  one probe run at a time, refused rather than raced",
     "_probe/mutate_repairs.py",
     "        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)",
     "        fd = os.open(LOCK, os.O_CREAT | os.O_WRONLY)",
     "test_probe_recovery.py",
     "did not refuse for that reason"),

    # And releasing a lock this process never took, which is the same defect
    # in one move and was nearly shipped inside the repair for it.
    ("SELF-F06b  a run releases only a lock it took itself",
     "_probe/mutate_repairs.py",
     "    global _HELD\n"
     "    if _HELD:\n"
     "        LOCK.unlink(missing_ok=True)\n"
     "        _HELD = False",
     "    LOCK.unlink(missing_ok=True)",
     "test_probe_recovery.py",
     "deleted a lock it did not take"),

    # D02-F01, third pass. Back to comparing sets of identifiers, which is
    # what let a malformed declaration hide behind a valid one wearing the
    # same name for two cycles.
    ("D02-F01d  declarations are counted, not collapsed into a set",
     "findings_format.py",
     "    _unaccounted = sorted(i for i, n in _declared.items()\n"
     "                          if n > _parsed.get(i, 0))",
     "    _unaccounted = sorted(set(_declared) - set(_parsed))",
     "test_run_review.py",
     "a malformed duplicate of an identifier that also parses"),

    # D04-F01. Back to str(), where a JSON null becomes the four-character
    # string "None" and satisfies every check that exists to require a value.
    ("D04-F01  a present field is a string with something in it",
     "authority.py",
     "    v = obj.get(key)\n"
     "    return v.strip() if isinstance(v, str) and v.strip() else \"\"",
     "    return str(obj.get(key, \"\")).strip()",
     "test_run_review.py",
     # Was "source fields are null, not empty", which is a phrase no control
     # in that suite has ever printed. The line was unverifiable from the day
     # it was written and the first completed full sweep said so, on 15
     # October. It was then changed to "is null: accepted", which was worse
     # in a way nothing could see: six controls in that function end their
     # label that way, three source fields and three top-level fields, so the
     # mutation could be caught by a control it is not about and counted as a
     # pass.
     #
     # Alex Zamurko, 16 October 2026: "use a stable, identifiable failure
     # signal from its named test, preferably a specific test or assertion
     # identifier rather than fragile prose." This is that identifier. It is
     # assigned in the suite rather than derived from any wording, and the
     # suite refuses a duplicate, so this signal names one control and will
     # keep naming it through any rewording.
     "[AUTH-SRC-MEDIUM-NULL]"),

    # Alex Zamurko's fourth condition of 9 October: an authorisation has to be
    # verifiable rather than a name in a file. Two lines, because the source
    # block and the length of its quote fail differently: a missing source
    # leaves nothing to check at all, while a two-word quote leaves something
    # that cannot be matched against the message it came from.
    # Re-pointed on 10 October: the source check moved inside the `/2`
    # branch when approvals were versioned, so the anchor's indentation
    # changed and the mutation could no longer be applied. The probe said so
    # rather than counting it as a catch, which is the fifth time a line here
    # has followed its rule to a new address.
    ("EC-4a  an approval says where it was given",
     "authority.py",
     "        src = rec.get(\"source\")\n"
     "        if not isinstance(src, dict):",
     "        src = rec.get(\"source\") or {}\n"
     "        if False:",
     "test_run_review.py",
     "an approval with no source at all"),

    ("EC-4b  a quote has to be long enough to match",
     "authority.py",
     # Re-pointed 15 October. D04-F01's repair on 12 October replaced the
     # str().strip() expression here with authority.text(), and this anchor
     # was not moved with it, so the mutation could not be applied at all.
     # Nothing said so until a full sweep completed.
     "        if len(text(src, \"quote\")) < MIN_QUOTE:",
     "        if False:",
     "test_run_review.py",
     "quote is too short to match"),

    # SELF-F05, and the first two mutations this probe has ever aimed at its
    # own source. On 8 October it emptied a 1163-line covered component and
    # the tree stayed that way overnight, so these two lines are the reason to
    # believe it will not happen again rather than the hope that it will not.
    #
    # Writing into the real file instead of a temporary one restores the exact
    # defect: the target is truncated first and a failure partway leaves it
    # empty.
    ("SELF-F05  a mutation is written atomically, never half",
     "_probe/mutate_repairs.py",
     "    tmp = path.with_name(path.name + \".probe-tmp\")",
     "    tmp = path",
     "test_probe_recovery.py",
     # The property, not one of its symptoms. The first needle here said
     # "emptied the target", and when the mutation was applied the write
     # landed before fsync raised, so the control fired on its other branch
     # and the probe called it a wrong control. The control was right and the
     # needle was too narrow to recognise it.
     "a write that did not complete"),

    # And the recovery half: refusing the empty file is the behaviour that let
    # the broken tree survive until morning.
    ("SELF-F05b  an empty file is restored, not refused",
     "_probe/mutate_repairs.py",
     "    if not live.strip() and _head() == rec.get(\"head\"):",
     "    if False:",
     "test_probe_recovery.py",
     "was left empty"),

    # D01-F01, BOOTSTRAP-003 cycle 01. Two rules, two mutations: the replay is
    # limited to the cycles that had reported the finding, and the recorded
    # origin must agree with the event that records it. Each needs its own
    # line, because with the first in place removing the second changes nothing
    # any control could see, which is the shape this probe keeps finding.
    ("D01-F01a  a finding's state comes from the cycles that reported it",
     "loop_state.py",
     "        _through = {v for v in valid if v <= num}",
     "        _through = set(valid)",
     "test_ledger.py",
     # Two corrections to this one line, both reported by the probe rather than
     # noticed by me. First it pointed at the reviewer's own fixture and read
     # MISSED, because that fixture carries a contradictory origin as well and
     # the other rule refuses it first. Then it pointed at the right fixture's
     # SUCCESS text and read WRONG CONTROL, because what a failing control
     # prints is its failure message. This is that message.
     "raised consistently in cycle 2"),

    ("D01-F01b  a recorded origin must agree with its own history",
     "loop_state.py",
     "        if any(c != _declared for c in _events):",
     "        if False:",
     "test_ledger.py",
     "disagrees with its own RAISED event"),

    ("C03-F01  a finished review is reparsed with its own grammar",
     "loop_state.py",
     "        _grammar = structured.get(\"finding_id_grammar\")",
     "        _grammar = None",
     "test_ledger.py",
     "broke a completed cycle"),

    # C03-F02's second pass, raised by cycle 04. Two rules: the approval has to
    # be in the record, and a question the repository cannot answer is not a yes.
    ("C03-F02d  the approval itself must be in the repository record",
     "bootstrap_gate.py",
     "    if committed(_appr_rel) != appr.read_bytes():",
     "    if False:",
     "test_bootstrap_gate.py",
     "untracked and ignored"),

    ("C03-F02e  a provenance query that fails refuses rather than proceeds",
     "bootstrap_gate.py",
     "        if r.returncode != 0:",
     "        if False:",
     "test_bootstrap_gate.py",
     "cannot be read at all: refused for the wrong reason"),


    # C02-F02 is three rules, so three mutations. One would leave the other two
    # unwatched while the line reported them as covered.
    ("C02-F02a  a demonstration belongs to a later cycle than its acceptance",
     "cycle_projection.py",
     "            if self.accepted_at is not None and c <= self.accepted_at:",
     "            if False:",
     "test_ledger.py",
     "same-cycle demonstration resolved"),

    ("C02-F02b  a recurrence is observed later than the resolution it undoes",
     "cycle_projection.py",
     "            if self.demonstrated_at is not None and c <= self.demonstrated_at:",
     "            if False:",
     "test_ledger.py",
     "same cycle as the resolution it undoes"),

    ("C02-F02c  a rejection carries the same reopening guard as an acceptance",
     "cycle_projection.py",
     "            if self.reopened_at is not None and c < self.reopened_at:\n"
     "                return False, (f\"dated before the cycle "
     "{self.reopened_at:02d} \"",
     "            if False:\n"
     "                return False, (f\"dated before the cycle "
     "{self.reopened_at:02d} \"",
     "test_ledger.py",
     "dated before the reopening took effect"),

    ("C02-F11  the label reaches the zero-valid-cycle return as well",
     "loop_state.py",
     "        print(\"\\n\".join(lines) if not a.quiet else labelled(\"CONTINUE\"))",
     "        print(\"\\n\".join(lines) if not a.quiet else \"LOOP_STATUS: CONTINUE\")",
     "test_ledger.py",
     "unlabelled status through --quiet"),

    # Not repairs. The §6 exit order, which Alex Zamurko asked on 28 September
    # to be tested at cycle 4 specifically, because every other exit was only
    # ever exercised where the ceiling was not competing with it. Disabling
    # either branch sends its scenario to MAX_4_REACHED, which is the exact
    # failure the new controls exist to refuse, so these two mutations are what
    # make them evidence rather than decoration.
    ("exit A  converging at the ceiling is CONVERGED, not MAX_4",
     "loop_state.py",
     "    if not cur[OPEN] and not cur[DISPUTED]:",
     "    if False:",
     "test_ledger.py",
     "a fourth cycle that converges"),

    ("exit B  a dispute at the ceiling needs a human, not MAX_4",
     "loop_state.py",
     "    if not cur[OPEN] and cur[DISPUTED]:",
     "    if False:",
     "test_ledger.py",
     "only a dispute left"),

    ("exit C  an unchanged ledger stalls rather than reaching the ceiling",
     "loop_state.py",
     "        if stalled:\n"
     "            return (\"STALLED\",",
     "        if False:\n"
     "            return (\"STALLED\",",
     "test_ledger.py",
     "an unchanged ledger at the ceiling"),

    # SELF-F07. The exit checker is the tool the exit decision is read from,
    # and until 12 October nothing watched it. It was written on 10 October
    # and reported EC-1 PASS on its first run with all four blocking defects
    # open, because it counted the list instead of asking whether anything on
    # it was closed. The seven lines below are the reason to believe that
    # cannot come back quietly, rather than the hope that it will not.
    #
    # Each one disables a single condition inside the checker and requires the
    # negative control written for it to go red. Where a disabled line lets
    # the checker crash instead of answering, that is still red and still
    # named, because a condition that cannot answer has not passed.
    ("SELF-F07a  the frozen criteria are compared, not just recorded",
     "exit_criteria.py",
     "    if want != got:",
     "    if False:",
     "test_exit_criteria.py",
     "a changed criteria document stops the run entirely"),

    ("SELF-F07b  a missing digest is a refusal, not a pass",
     "exit_criteria.py",
     "    if not rec.is_file():",
     "    if False:",
     "test_exit_criteria.py",
     "no recorded digest stops the run entirely"),

    # The defect the checker shipped with. Counting a list is not asking
    # whether anything on it is closed.
    ("SELF-F07c  EC-1 asks whether blocking defects are closed",
     "exit_criteria.py",
     "        elif _open:",
     "        elif False:",
     "test_exit_criteria.py",
     "blocking defects nobody has examined cannot pass EC-1"),

    # Cycle 04: "A recent log containing one [caught] and no recognized
    # failure marker can pass the sweep check." These two are what a date
    # alone could never establish.
    ("SELF-F07d  a sweep is bound to the commit it examined",
     "exit_criteria.py",
     # Re-pointed 15 October, when EC-2 moved from HEAD to the frozen
     # candidate. The guarded line changed and this anchor did not move with
     # it, which is how a repair stops being watched without anybody
     # deciding that it should.
     "        elif not _at.startswith(_swept.group(1)):",
     "        elif False:",
     "test_exit_criteria.py",
     "a sweep of a different commit is not evidence about this one"),

    ("SELF-F07e  a sweep that stopped early is not a clean one",
     "exit_criteria.py",
     "        elif _held.group(1) != _held.group(2):",
     "        elif False:",
     "test_exit_criteria.py",
     "an interrupted sweep establishes nothing about what it skipped"),

    # Cycle 04: "Any nonempty cycle reference passes." The shape and the
    # target are two separate things to get wrong, so they get a line each.
    ("SELF-F07f  an examination reference has to name a cycle",
     "exit_criteria.py",
     "        if len(_parts) != 2 or not _parts[1].startswith(\"cycle-\"):",
     "        if len(_parts) != 2:",
     "test_exit_criteria.py",
     "a reference of the right shape with the wrong tail"),

    ("SELF-F07g  a named cycle has to exist on disk",
     "exit_criteria.py",
     "        if not _dir.is_dir():",
     "        if False:",
     "test_exit_criteria.py",
     "a reference to a cycle that does not exist"),

    # SELF-F09. The masking this line watches was written on 12 October and
    # crashed the first time anything called it, on a name that was never
    # imported. Seven runs and fourteen suites had gone green in between,
    # because every one of them selected mutations aimed at other files and
    # never took the branch. A function nothing reaches is a function nothing
    # tests, so the control this line requires calls it directly rather than
    # hoping a fixture wanders into it.
    ("SELF-F09  a self-aimed anchor is masked from its own table entry",
     "_probe/mutate_repairs.py",
     "    return text[:i] + re.sub(r\"[^\\n]\", \" \", text[i:j]) + text[j:]",
     "    return text",
     "test_probe_recovery.py",
     "an anchor quoted by its own table entry is found once"),

    # SELF-F11. The sweep log is the evidence EC-2 rests on, and for weeks the
    # checker could not decode it, because PowerShell's `>` writes UTF-16 and
    # the reader asked for UTF-8 with errors="replace". It reported a perfect
    # sweep as saying nothing. errors="replace" is what made it quiet, and
    # this line is what keeps the refusal honest.
    ("SELF-F11  an undecodable sweep is refused, not read as empty",
     "exit_criteria.py",
     "        if _unreadable:",
     "        if False:",
     "test_exit_criteria.py",
     "a sweep the checker cannot decode is unreadable, not empty"),

    # SELF-F12. The instance was one bare open() in test_citation_extract.py,
    # which made that suite pass on Linux, pass on Windows in any shell where
    # someone had typed PYTHONUTF8=1, and crash in any other. The rule is the
    # repair, so this line is aimed at the rule: remove the encoding from a
    # read anywhere in scripts/ or _probe/ and the scan must find it.
    ("SELF-F12  a text read that names no encoding is found",
     "exit_criteria.py",
     "    want = rec.read_text(encoding=\"utf-8\").split()[0].strip()",
     "    want = rec.read_text().split()[0].strip()",
     "test_encoding_discipline.py",
     "names no encoding"),

    # SELF-F06b. Alex Zamurko, 14 October 2026: "Has SELF-F06 been
    # independently verified to ensure that the three parallel sweeps cannot
    # interfere with each other or delete another run's active worktree?"
    #
    # The honest answer was no. The lock is claimed before anything touches a
    # sandbox directory, so a refused run cannot reach the cleanup, but that
    # was an argument from the order of the source rather than a
    # demonstration. Remove the claim and the next line sweeps the holder's
    # working copy out from under it, which is the whole defect. The control
    # this requires has to find the checkout still there.
    ("SELF-F06c  the lock is claimed before any sandbox is touched",
     "_probe/mutate_repairs.py",
     "    _busy = take_lock()",
     "    _busy = None",
     "test_probe_recovery.py",
     "leaves another run's checkout alone"),

    # B01-F14b. Alex Zamurko classified B01-F14 NOT BLOCKING on 13 October
    # 2026 with a condition: "This classification assumes missing metadata
    # cannot still produce an authoritative result." The guard that makes that
    # true sits in the controller, and nothing was watching it. Remove it and
    # a run that records no enforcement status prints an unqualified outcome,
    # which is what cycle 03's reviewer saw.
    ("B01-F14b  missing enforcement metadata cannot produce an outcome",
     "loop_state.py",
     "        problem = run_pins.mc1_enforcement_problem(run)",
     "        problem = None",
     "test_ledger.py",
     "cannot produce an authoritative result"),

    # EC-4a and EC-4b are taken, by two authority.py lines named for a
    # different thing. These two are aimed at EC-4 itself, which until
    # 14 October could not be satisfied by any evidence at all.
    ("EC-4d  evidence is bound to the commit it examined",
     "exit_criteria.py",
     "        if r.get(\"commit\") != at_head:",
     "        if False:",
     "test_exit_criteria.py",
     "evidence from a different commit is not evidence about this one"),

    # The digest is the line between a preserved log and a URL somebody typed.
    ("EC-4e  a preserved log still matches the digest taken with it",
     "exit_criteria.py",
     # Re-pointed 15 October, same cause: the digest moved to being taken
     # from the raw bytes and the anchor stayed where it was.
     "        if hashlib.sha256(raw).hexdigest() != r.get(\"log_sha256\"):",
     "        if False:",
     "test_exit_criteria.py",
     "a preserved log that no longer matches its digest"),

    # SELF-F14. Alex Zamurko, 15 October 2026: "A locally authored evidence
    # record with a matching log digest can therefore satisfy the mechanical
    # check without demonstrating that GitHub independently executed the
    # named repair." These two lines are the ones that stopped being true of,
    # and they are the difference between a fetch that verifies and a fetch
    # that decorates.
    ("SELF-F14a  a record's commit must match GitHub's own reply",
     "exit_criteria.py",
     "            if got != str(r.get(\"commit\", \"\")).lower():",
     "            if False:",
     "test_exit_criteria.py",
     "a record whose commit GitHub's own reply contradicts"),

    ("SELF-F14b  a record's conclusion must match GitHub's own reply",
     "exit_criteria.py",
     "            if job.get(\"conclusion\") != r.get(\"conclusion\"):",
     "            if False:",
     "test_exit_criteria.py",
     "a record calling a job successful that GitHub calls failed"),

    # EC-4f and EC-4g. The last two of the six negative cases Alex Zamurko
    # named on 16 October, written on the 20th. Until then a record could
    # cite a run in somebody else's repository and EC-4 accepted it.
    #
    # Two lines because they refuse two different things. The first catches a
    # record and GitHub's reply disagreeing about whose run it was. The
    # second catches them agreeing perfectly on a repository that is not this
    # one, which is the dangerous case: a fork shares commits, workflows get
    # copied, and the conclusion is genuine, so every other check in EC-4
    # passes on it.
    ("EC-4f  a record's repository must match GitHub's own reply",
     "exit_criteria.py",
     "            if said_repo and claimed and said_repo.lower() "
     "!= claimed.lower():",
     "            if False:",
     "test_exit_criteria.py",
     "a record whose repository"),

    ("EC-4g  the run must belong to this repository, not a fork of it",
     "exit_criteria.py",
     "            if here.lower() != claimed.lower():",
     "            if False:",
     "test_exit_criteria.py",
     "a genuine green run in somebody else's repository"),

    # SELF-F29, 26 October. The other side of EC-4's coverage refusal. The
    # refusal is named for what the output supports, and was computed by
    # subtracting the blocking-filtered set, so every true claim about a
    # non-blocking finding was reported as unsupported. The replacement here
    # is the defect verbatim: if somebody unifies the two sets again because
    # they look redundant, this goes red.
    #
    # Matched on [EC4-COVERAGE] rather than on the sentence. The sentence is
    # the sort that gets reworded, and the 86 entries above that match on
    # prose are SELF-F15b's residual, not a pattern to copy.
    # SELF-F30, 26 October. The repository check is correct and is not what
    # this watches. What it watches is the half of the message that tells a
    # reader which of the two situations they are in: a fork substitution, or
    # a repository that moved. Remove it and the fork control still passes,
    # because the comparison is unchanged, which is exactly why the second
    # control had to be written.
    #
    # Matched on the needle rather than the control's label. The needle is
    # quoted into the failure line and appears nowhere in a green run, and it
    # is the text the repair is about rather than a sentence describing it.
    ("SELF-F30  a moved repository is named, not left reading as a fork",
     "exit_criteria.py",
     '                        f"\\n      If this repository was transferred or "',
     '                        f"\\n      If this repository moved, "',
     "test_exit_criteria.py",
     "transferred or renamed"),

    ("SELF-F29  a declared finding is judged against the output, not the "
     "blocking list",
     "exit_criteria.py",
     "        over = sorted(d for d in declared if d not in text)",
     "        over = sorted(declared - observed)",
     "test_exit_criteria.py",
     "[EC4-COVERAGE]"),

    # SELF-F18. Alex Zamurko, 16 October 2026: the coverage checker "must
    # recognise actual executable test commands, not comments or disabled
    # steps." The first version searched ci.yml as one string, so a suite named
    # only in a comment passed, and the comments in that file name several
    # suites while explaining why they were added. It established that somebody
    # had once typed the name.
    #
    # Two lines, because a comment can hide in two places. This one is the
    # shell comment inside a `run:` block, which the YAML parser hands over as
    # data and only this line removes.
    ("SELF-F18a  a suite commented out inside a run block is not coverage",
     "test_ci_coverage.py",
     "    live = [ln for ln in run.splitlines() "
     "if not ln.lstrip().startswith(\"#\")]",
     "    live = run.splitlines()",
     "test_ci_coverage.py",
     "a suite commented out inside a run block"),

    # And this one is the gate. Flatten every `if:` to the empty condition and
    # a step that runs only on a manual dispatch counts as running on push,
    # which is the permissive direction the whole check exists to refuse.
    ("SELF-F18b  a step behind an undecided condition is not coverage",
     "test_ci_coverage.py",
     "    text = str(value).strip()",
     "    return \"\"",
     "test_ci_coverage.py",
     "a suite in a job gated by an undecided condition"),

    # SELF-F25, both halves, because the two are one repair and a probe that
    # only removed one of them would report the other as watched when nothing
    # watches it.
    #
    # The speaking half. ledger.py is a program holding characters cp1252 has
    # no room for, and the guard is what lets it say them. Take the guard out
    # and the scan must name that file, not merely fail somewhere.
    ("SELF-F25a  a program printing non-ASCII must configure its console",
     "scripts/ledger.py",
     "    sys.stdout.reconfigure(encoding=\"utf-8\")",
     "    pass",
     "test_encoding_discipline.py",
     "scripts/ledger.py"),

    # The listening half. One subprocess call in cycle_projection.py, so the
    # anchor cannot match the wrong one. Removing the encoding puts the parent
    # back to decoding its child at whatever locale it happens to have, which
    # is the state that returned None for stdout and raised a TypeError two
    # lines later in test_interfaces.py on 20 October 2026.
    ("SELF-F25b  a call reading a child as text must name the encoding",
     "scripts/cycle_projection.py",
     "                       capture_output=True, text=True, "
     "encoding=\"utf-8\")",
     "                       capture_output=True, text=True)",
     "test_encoding_discipline.py",
     "decoded at the locale"),

    # Issue 6. Two mutations, because the check has two halves and they fail
    # differently. One asks whether the record still describes the manifest;
    # the other asks whether the manifest still describes the system.
    #
    # The date comparison is the half that answers "will it agree next week".
    # Remove it and a status record left behind by a scope change passes.
    # Both of these came back WRONG CONTROL in ci run #332, found by Alex
    # Zamurko reading the sweep. The expected text was the wording of the
    # original failure, and that wording cannot appear: disabling a check
    # makes its control fail with "expected a failure, got none" instead. A
    # mutation matching on the check's own message can never be caught by the
    # control it names. SELF-F15b is the same defect and was repaired the day
    # before this was written.
    ("ISSUE-6a  a record older than the scope change it describes is stale",
     "scripts/test_system_identity.py",
     "    if last and claims[\"STATUS_AS_OF\"] < last[:10]:",
     "    if False:",
     "test_system_identity.py",
     "[SYSID-STALE]"),

    # And the closure, which is the "suites' dependencies" half. Remove it
    # and a manifest can pin a file whose imports nobody pinned.
    ("ISSUE-6b  a covered file's dependencies are part of the covered system",
     "scripts/test_system_identity.py",
     "    uncovered = sorted(reach - set(comps))",
     "    uncovered = []",
     "test_system_identity.py",
     "[SYSID-CLOSURE]"),

    # Issue 8. The load-bearing half of that check is not "does the suite
    # read a record", which is allowed, but "does it say which way it fails
    # when the record is gone". Remove that question and a declaration can
    # omit the one thing that distinguishes the two cases.
    ("ISSUE-8  a record source must say which way it fails when absent",
     "scripts/test_fixture_sources.py",
     "        if not any(m in why.lower() for m in ABSENT_MARKERS):",
     "        if False:",
     "test_fixture_sources.py",
     "a record source with no absent clause"),

    # SELF-F13's line belongs here and is deliberately absent. The repair is
    # in approval_package.py, on Alex Zamurko's ruling of 14 October 2026 that
    # a failed dependency must prevent approval. Its control is not written
    # yet, because the fixture needed to reach that branch has to get past the
    # findings reconciliation first and two attempts at it refused earlier for
    # two correct reasons. A mutation whose named control does not exist
    # reports a defect in this probe rather than in the code, so the line goes
    # in when the control does. Recorded in the register as outstanding.
]


# Alex Zamurko, 9 October 2026: "rather than continuing to fix recovery
# problems one by one, can we run these destructive tests in a separate,
# disposable copy of the repository?"
#
# He is right, and it ends a family of defects rather than shrinking it. This
# probe has always written its mutations into the live controller and put them
# back afterwards, so every way a run can die is a way to leave a check
# switched off in the real tree. SELF-F02 was the first, SELF-F05 the second,
# and the one-slot sentinel the third, each a patch on the same wrong idea.
#
# A git worktree is a second checkout of the same commit in its own directory,
# sharing the object store. The mutation goes there, the suite runs there, and
# the directory is deleted at the end. A kill now costs a folder that was
# going to be thrown away. There is nothing to recover, because nothing the
# probe touches is anybody's work.
#
# The recovery machinery below stays, because a tree can still carry damage
# from before today, but it stops being what the safety of a run depends on.
SANDBOX_PREFIX = "epistemicos-probe-"

# Inside the repository, gitignored, rather than in the shared system temp.
#
# The first version put them in tempfile.gettempdir() and swept them by asking
# git which worktrees it knew about. Both halves of that were wrong, and the
# control written for Alex Zamurko's "prove the tree survives an interrupted
# run" found it within the hour: that control clones the repository, runs a
# probe inside the clone, and deletes the clone. The sandbox the clone made
# outlived it in the shared temp, and no repository remembered the worktree
# any more, so nothing could ever sweep it. Five of them had piled up by
# midnight on 9 October.
#
# Living here, a deleted clone takes its sandboxes with it. And the sweep
# below reads the directory rather than asking git, so a checkout whose
# registration is gone is still found. A question answered by looking is
# better than one answered by asking something that might have forgotten.
SANDBOX_ROOT = REPO / ".probe-sandboxes"


LOCK = Path(__file__).resolve().parent / ".probe-lock.json"

# Whether THIS process holds the lock, as distinct from whether a lock file
# exists. Without this, a run that refuses because another holds the lock
# would delete that lock on its way out, which is SELF-F06 again wearing a
# different hat: one process removing another's claim because it only
# checked that the thing existed, not whose it was. Nearly shipped that way.
_HELD = False


def take_lock() -> str:
    """Claim exclusive use of the sandboxes. Returns '' on success.

    SELF-F06, raised by the BOOTSTRAP-003 cycle 04 reviewer: "drop_sandboxes()
    does not establish that another checkout is abandoned. It excludes only
    the current PID's directory and removes every other matching directory. A
    second concurrent probe can therefore delete the first probe's active
    checkout."

    Correct, and the docstring there claimed the opposite. A pid in a
    directory name identifies it; it does not protect it.

    Two ways to fix that: work out whether another run is alive before
    deleting its directory, or make two runs impossible. The second is
    simpler, matches how this is actually used, and does not require
    guessing at liveness, which is the part that would be wrong on some
    platform or other.

    A stale lock after a killed run is left for a person rather than cleaned
    up automatically, and the refusal prints the command. Deciding on its own
    that another run is dead is exactly the guess this is avoiding, and
    guessing wrong means deleting a live run's working copy, which is the
    defect being repaired.
    """
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            held = json.loads(LOCK.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            held = {}
        _pid = held.get("pid", "unrecorded")
        return (
            f"another run holds the sandboxes.\n"
            f"      pid     {_pid}\n"
            f"      since   {held.get('at', 'unrecorded')}\n"
            f"      command {held.get('argv', 'unrecorded')}\n\n"
            "  Two probes at once delete each other's working copies, so this "
            "one refuses\n  rather than racing. If that run is finished or was "
            "killed, remove the lock:\n\n"
            f"      Remove-Item {LOCK}\n\n"
            "  It is not removed automatically, because deciding on its own "
            "that another run\n  is dead is the guess this exists to avoid.\n\n"
            f"  Check it properly. A pid is reused: on 20 October this lock "
            f"named a pid that\n  the operating system had since given to an "
            f"unrelated program, so finding a\n  live process by that number "
            f"proves nothing. Compare the command too:\n\n"
            f"      Get-CimInstance Win32_Process -Filter \"ProcessId={_pid}\""
            f" | Select-Object CommandLine\n\n"
            "  If it is not running this probe, the lock is stale.")
    global _HELD
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(),
                   "at": datetime.now().astimezone().isoformat(timespec="seconds"),
                   # SELF-F22. A pid does not identify a process for long.
                   # On 20 October a sweep died overnight and its lock named
                   # pid 21568; by morning the operating system had given
                   # that number to `ipf_helper`, so looking it up found a
                   # live process that had nothing to do with the probe. The
                   # refusal asks a person to decide whether that run is
                   # alive, and the only thing it gave them to decide with
                   # was a number that had already been reused.
                   #
                   # The command line is what makes the question answerable:
                   # a live process bearing this pid that is not running this
                   # file is not the run that took the lock.
                   "argv": " ".join(sys.argv)[:200]},
                  fh, indent=2)
    _HELD = True
    return ""


def drop_lock() -> None:
    """Release the lock, and only if this process took it."""
    global _HELD
    if _HELD:
        LOCK.unlink(missing_ok=True)
        _HELD = False


def drop_sandboxes() -> tuple[list[str], list[str]]:
    """Remove checkouts this probe left behind. Returns (swept, stuck).

    Safe in a way none of the recovery code is: these directories contain no
    work. The one hazard is deleting a directory a concurrent run is using,
    and the lock above is what prevents that.

    This used to say the pid in each name kept concurrent runs out of each
    other's way. It did not. A pid names a directory; it does not stop
    another process removing it, and nothing here checked whether a directory
    it was about to delete was in use. SELF-F06. A comment asserting a
    property the code does not have is worse than no comment, because it is
    the thing that stops the next reader from checking.

    Both lists are returned because the first version returned only the fully
    deleted ones, and on Windows `git worktree remove` deregisters the
    checkout while `rmtree` can leave the folder behind if anything still
    holds a handle. So the registration was gone, the sweep had plainly done
    something, and it reported nothing at all. A run reporting silence after
    acting is the shape of defect this probe exists to find, and it took the
    control written for Alex Zamurko's interrupted-run requirement to notice
    it.
    """
    if not SANDBOX_ROOT.is_dir():
        return [], []
    mine = f"{SANDBOX_PREFIX}{os.getpid()}"
    swept, stuck = [], []
    for p in sorted(SANDBOX_ROOT.iterdir()):
        if not p.name.startswith(SANDBOX_PREFIX) or p.name == mine:
            continue
        # Through git first, so its registration goes too, then from disk in
        # case git never knew about it or has since forgotten.
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove",
                        "--force", str(p)], capture_output=True, text=True, encoding="utf-8")
        shutil.rmtree(p, ignore_errors=True)
        (stuck if p.exists() else swept).append(p.name)
    subprocess.run(["git", "-C", str(REPO), "worktree", "prune"],
                   capture_output=True, text=True, encoding="utf-8")
    return swept, stuck


def make_sandbox() -> Path:
    """A second checkout of HEAD, for the probe to break at will."""
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
    path = SANDBOX_ROOT / f"{SANDBOX_PREFIX}{os.getpid()}"
    if path.exists():
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove",
                        "--force", str(path)], capture_output=True, text=True, encoding="utf-8")
        shutil.rmtree(path, ignore_errors=True)
    r = subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach",
                        "--quiet", str(path), "HEAD"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("could not create the disposable checkout:\n"
                           + (r.stderr or r.stdout).strip())
    return path


def restore_in(root: Path, rel: str) -> None:
    """Put one file in the sandbox back to HEAD.

    Cheaper and more exact than remembering the original text, and there is no
    index in play to confuse it with: the worktree was created detached at
    HEAD and nothing stages anything in it.
    """
    subprocess.run(["git", "-C", str(root), "checkout", "--", rel],
                   capture_output=True, text=True, encoding="utf-8")


def run_suite(name: str, root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(root / "scripts" / name)],
                          cwd=str(root),
                          env=env, capture_output=True, text=True, encoding="utf-8", timeout=900)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _head() -> str:
    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip() if r.returncode == 0 else ""


def write_atomic(path: Path, text: str) -> None:
    """Replace a file's contents, or leave them alone. Never in between.

    SELF-F05. `Path.write_text` opens for writing, which truncates to zero
    before any new bytes arrive. Kill the process in that window, which is what
    closing a PowerShell window does, and the file is empty. On the night of
    8 October it emptied scripts/loop_state.py, 1163 lines of a covered
    component, and the tree sat that way until the next morning.

    What made it worse is that recovery is built to restore only a file that is
    byte for byte the mutation this probe wrote. An empty file is not that, so
    recovery looked at it, could not prove it was its own writing, and refused.
    The guard behaved exactly as designed and the repository stayed broken.

    A temporary file in the same directory, flushed and fsynced, then
    os.replace, which is atomic on Windows and on POSIX. Same directory because
    a replace across filesystems is not atomic. After this, a kill at any point
    leaves either the old content or the new.
    """
    tmp = path.with_name(path.name + ".probe-tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def recover() -> int:
    """Put back a mutation that a killed run left applied. 0 = clear to start.

    Deliberately narrow. It restores only when the file is byte for byte the
    mutated content this probe wrote and HEAD is where it was, so an edit made
    in between cannot be destroyed by a recovery that assumed it knew better.
    When anything has moved it says what it knows and refuses, which is the
    same rule as everywhere else here: a restore that might be wrong is worse
    than a message that is certainly right.
    """
    if not ACTIVE.is_file():
        return 0
    try:
        rec = json.loads(ACTIVE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  [CANNOT RUN] {ACTIVE.name} cannot be read ({exc}), so a "
              f"mutation may still be\n  applied and this probe cannot tell "
              f"which one. Check `git status` and `git diff`\n  before running "
              f"anything else against this tree.")
        return 2
    rel = str(rec.get("path", ""))
    label = str(rec.get("finding", "an unnamed mutation"))
    path = REPO / rel
    if not rel or not path.is_file():
        print(f"  [CANNOT RUN] {rel!r} is recorded as mutated and is not a "
              f"file. Restore it by hand,\n  then delete {ACTIVE.name}.")
        return 2
    with path.open("r", encoding="utf-8", newline="") as fh:
        live = fh.read()
    # SELF-F05, the half the atomic write cannot cover. A tree can already be
    # in this state from before that repair, which ours was, and a flush can
    # still fail. An empty file is the one case where refusing to act is not
    # the cautious choice: nobody edits a source file down to zero bytes and
    # walks away, so there is no human work here to protect. HEAD still has to
    # match, because restoring from a commit that has moved would put back
    # something nobody reviewed.
    if not live.strip() and _head() == rec.get("head"):
        print(f"  [recovering] {rel} is empty. A previous run was killed "
              f"between truncating\n  the file and writing the mutation for "
              f"{label}, so what is on disk is neither\n  the original nor the "
              f"mutation. Restoring from HEAD: an empty source file is\n  not "
              f"somebody's edit to preserve.")
    elif _head() != rec.get("head") or _sha_text(live) != rec.get("mutated"):
        print(f"  [CANNOT RUN] a previous run was killed while {rel} carried "
              f"the mutation for\n  {label}, and the file or the commit has "
              f"moved since. It is not restored here,\n  because a recovery "
              f"that guesses is worse than one that refuses. Read `git diff "
              f"{rel}`,\n  put it back yourself, then delete {ACTIVE.name}.")
        return 2
    # The bytes HEAD holds for this path, written directly.
    #
    # This was `git checkout -- <path>`, which restores from the INDEX, not from
    # HEAD, while the message below said HEAD. BOOTSTRAP-003's reviewer built
    # the case: unchanged HEAD, mutated working bytes matching the sentinel,
    # different bytes staged. Recovery returned 0, wrote the staged bytes, and
    # reported that it had restored from HEAD. The sentence was false and the
    # file was wrong, and nothing here could have noticed either.
    #
    # `git show HEAD:<path>` names its source in the command, cannot be
    # satisfied by anything in the index, and leaves the index alone, which
    # matters because someone else's staged work is not this probe's to revert.
    r = subprocess.run(["git", "-C", str(REPO), "show", f"HEAD:{rel}"],
                       capture_output=True)
    if r.returncode != 0:
        print(f"  [CANNOT RUN] {rel} could not be read from HEAD: "
              f"{r.stderr.decode('utf-8', 'replace').strip()}")
        return 2
    # SELF-F05 again. The restore is the half that matters most: a kill here
    # empties the file while the sentinel still points at a mutation, which is
    # the state that needed a human this morning. Bytes, not text, because what
    # HEAD holds is what goes back, with no encoding or newline step in between.
    _tmp = path.with_name(path.name + ".probe-tmp")
    with _tmp.open("wb") as fh:
        fh.write(r.stdout)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(_tmp, path)
    # Verified rather than assumed: the file now holds what HEAD holds.
    with path.open("r", encoding="utf-8", newline="") as fh:
        if _sha_text(fh.read()) != hashlib.sha256(r.stdout).hexdigest():
            print(f"  [CANNOT RUN] {rel} was rewritten from HEAD and does not "
                  f"match HEAD afterwards. Restore it by hand.")
            return 2
    ACTIVE.unlink()
    print(f"  [recovered] a previous run was killed while {rel} held the "
          f"mutation for\n  {label}. It is restored from HEAD. That run "
          f"established nothing about anything;\n  this one starts from a "
          f"clean tree.\n")
    return 0


OWN_REL = "_probe/" + Path(__file__).name


def outside_own_table(text: str) -> str:
    """This file with its own mutation table blanked, offsets preserved.

    A mutation aimed at this file finds its anchor twice: once in the code
    and once in the entry that names it, because the entry quotes the code
    verbatim. The probe then reports a broken probe and declines to run, so
    every repair to the instrument itself is unwatched.

    SELF-F05's two lines escaped this by luck. Their anchors contain quote
    characters, which appear escaped inside a Python string literal and
    therefore do not match the code. Nothing about that was designed, and
    SELF-F06's anchor has no quotes in it, so it collided immediately.

    Blanking the table for the purpose of counting and locating is the
    general fix. Line structure is preserved so positions still line up with
    the real text, which is what the replacement is applied to.
    """
    i = text.find("\nMUTATIONS = [")
    if i < 0:
        return text
    j = text.find("\n]\n", i)
    if j < 0:
        return text
    return text[:i] + re.sub(r"[^\n]", " ", text[i:j]) + text[j:]


def rel_of(fname: str) -> str:
    """The repo-relative path a mutation entry names.

    A bare name means scripts/, which is every entry written before 9 October.
    A name carrying a slash is repo-relative, which exists so the probe can be
    aimed at its own source.

    One function because the first version of this rule was written inline in
    the loop and the target list a hundred lines above kept its own copy with
    the prefix hardcoded. For the one entry that needed the new form, the
    clean-tree guard and the left-modified guard were both checking
    `scripts/_probe/mutate_repairs.py`, which does not exist, so both reported
    nothing and both looked like they had passed. A check that answers about a
    path that is not there is the same defect this probe exists to find, and it
    lasted about an hour.
    """
    return fname if "/" in fname else f"scripts/{fname}"


def modified(rel_paths: list[str]) -> list[str]:
    """Which of these repo-relative paths git reports as changed."""
    r = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain", "--"] + rel_paths,
        capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"git status failed:\n{r.stderr.strip()}")
    return sorted({ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()})


class Tee:
    """Write to a stream and to a UTF-8 file at the same time.

    SELF-F11. Every local sweep log this repository has ever held was written
    by `python ... > _probe\\full-sweep.txt`, and Windows PowerShell's `>`
    writes UTF-16LE with a byte-order mark. exit_criteria.py reads that file
    with encoding="utf-8", errors="replace", so the words arrived as
    replacement characters and the checker could not find `swept commit` or
    `[caught]` in a sweep that had neither failed nor been interrupted. It
    reported the sweep as saying nothing. The log was perfect on screen and
    unreadable to the only reader that mattered.

    The fix is not to teach the reader about UTF-16. It is to stop the shell
    deciding the encoding of evidence at all: with --out=PATH the probe writes
    its own log, in UTF-8, on every platform. The shell is then only a place
    to watch it happen.

    Flushed per write so the file can be tailed while a two-hour run goes on,
    which is the same reason `python -u` is used.
    """

    def __init__(self, stream, path: Path) -> None:
        self._stream = stream
        self._file = open(path, "w", encoding="utf-8", newline="\n")

    def write(self, s: str) -> int:
        self._stream.write(s)
        self._file.write(s)
        self._file.flush()
        return len(s)

    def flush(self) -> None:
        self._stream.flush()
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def out_path() -> Path | None:
    """The --out=PATH argument, if one was given.

    Only the `--out=PATH` form, with no space, so the path can never be
    mistaken for a mutation filter. The filter takes every argument that does
    not begin with a dash, and `--out _probe/full-sweep.txt` would have handed
    it a filename to match finding labels against.
    """
    for a in sys.argv[1:]:
        if a.startswith("--out="):
            v = a.split("=", 1)[1].strip()
            if v:
                return Path(v)
    return None


def main() -> int:
    # An optional filter, because a whole run is twenty-odd suite executions and
    # correcting one line of this file should not cost all of them. Matched
    # against the finding label, so `C02-F08` takes one mutation and `C02-F02`
    # takes the three that make up that finding.
    #
    # A filtered run is not a verification run: it says nothing about the
    # repairs it skipped, and the summary below says which it looked at rather
    # than claiming the whole set.
    # Recovery first, before the arguments are even looked at.
    #
    # It used to sit after the filter check, so `mutate_repairs.py NOPE` exited
    # on "nothing matches" with a mutation still applied to tracked source. The
    # argument list has nothing to do with whether the working tree is in a
    # state this probe left behind, and a tree left mutated should be put back
    # whatever you asked for. Found by test_probe_recovery.py, whose fixture
    # passes a filter that matches nothing precisely so that no mutation runs.
    rc = recover()
    if rc:
        return rc

    # Before anything touches a sandbox directory, including the sweep.
    _busy = take_lock()
    if _busy:
        print(f"  [CANNOT RUN] {_busy}")
        return 2

    # Before the filter, for the same reason recovery is. `mutate_repairs.py
    # NOPE` used to exit on "nothing matches" with a mutation still applied,
    # which BOOTSTRAP-003 raised and which was fixed by moving recovery up.
    # Three days later this function was added below the filter and the
    # identical defect came back wearing a different name: a run matching
    # nothing left an abandoned checkout lying around forever. Found by the
    # control written for Alex Zamurko's request to prove the tree survives
    # an interrupted run, which is the first thing that has ever looked.
    _swept, _stuck = drop_sandboxes()
    if _swept:
        print(f"  [cleaned] {len(_swept)} abandoned checkout(s) from a killed "
              f"run, removed:\n      " + "\n      ".join(_swept) +
              "\n      Nothing was lost. That is the point of them.\n")
    if _stuck:
        print(f"  [cleaned] {len(_stuck)} abandoned checkout(s) deregistered, "
              f"but the folder\n      remains on disk, most likely because "
              f"something still holds a handle:\n      "
              + "\n      ".join(_stuck) +
              "\n      Harmless, and said out loud rather than left for "
              "someone to find.\n")

    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    selected = [m for m in MUTATIONS
                if not want or any(w.lower() in m[0].lower() for w in want)]
    if want and not selected:
        print(f"  [CANNOT RUN] nothing matches {', '.join(want)}")
        return 2

    # The clean-tree guard follows recovery above, because the commonest reason
    # this tree is dirty is this probe itself, and "commit or discard them
    # first" is the wrong instruction for a file this process mutated and
    # failed to put back.
    targets = sorted({rel_of(m[1]) for m in selected})
    try:
        dirty = modified(targets)
    except RuntimeError as exc:
        print(f"  [CANNOT RUN] {exc}")
        return 2
    if dirty:
        print("  [CANNOT RUN] this probe writes to tracked source and restores "
              "it afterwards,\n  so it can only run against a clean tree. These "
              "already differ from HEAD:\n")
        for p in dirty:
            print(f"      {p}")
        print("\n  Commit or discard them first. A mutation is applied to a "
              "checkout of HEAD, so\n  anything uncommitted here is not what "
              "would be tested, and the result would\n  say nothing about the "
              "source you are actually running.")
        return 2

    # What the real files hold before anything starts. The end-of-run check
    # used to compare against HEAD, which cannot tell a mutation that escaped
    # from an edit someone made while the run was going. On 9 October it
    # reported ESCAPED for two files the implementing agent had edited during
    # the sweep, and the message asserted the isolation was broken when it had
    # not been. A check that names one cause while unable to distinguish two
    # is the defect this probe exists to find, so it now compares against the
    # tree it actually started from and says both possibilities out loud.
    before = {}
    for rel in targets:
        p = REPO / rel
        before[rel] = (hashlib.sha256(p.read_bytes()).hexdigest()
                       if p.is_file() else None)

    # Everything destructive from here happens in a copy.
    try:
        work = make_sandbox()
    except RuntimeError as exc:
        print(f"  [CANNOT RUN] {exc}")
        return 2

    bad = 0
    for finding, fname, old, new, suite, needle in selected:
        # Aimed at its own source when the entry says so. An instrument that
        # cannot be pointed at itself is one whose repairs are taken on trust,
        # and this run has been finding out what that costs.
        _rel = rel_of(fname)
        path = work / _rel
        # newline="" on the READ as well, not only on the writes below. Without
        # it Python translates CRLF to LF on the way in, so `original` is not
        # the file's bytes and restoring it rewrites every line ending in the
        # file. That is how run_pins.py came back [LEFT MODIFIED] on
        # 30 September after a restore that had put the source back correctly:
        # the probe reported a real difference it had introduced itself.
        # `Path.read_text` only grew a newline argument in 3.13, while
        # `write_text` has had one since 3.10, so the read is spelled out.
        with path.open("r", encoding="utf-8", newline="") as _f:
            original = _f.read()
        # Counted and located against the file with its own mutation table
        # blanked, when the target is this file. Otherwise every anchor aimed
        # here matches twice, once in the code and once in the entry quoting
        # it, and the probe refuses to test its own repairs.
        _search = outside_own_table(original) if _rel == OWN_REL else original
        found = _search.count(old)
        if found != 1:
            hint = ""
            if found == 0 and new in original:
                hint = ("\n      The replacement text is there instead, so the "
                        "mutation is already applied:\n      an earlier run "
                        "wrote it and did not restore it.")
            print(f"  [BROKEN PROBE] {finding}\n"
                  f"      the source this mutation replaces appears {found} "
                  f"times in {fname}, not\n      once, so the mutation cannot "
                  f"be applied. That is reported rather than\n      counted as "
                  f"a catch.{hint}")
            bad += 1
            continue

        # No sentinel is written any more, because there is nothing for a
        # later run to recover: this file lives in a directory that exists to
        # be deleted. The sentinel and recover() stay in this file for a tree
        # damaged before today, and test_probe_recovery still exercises them,
        # but no new run creates that situation.
        #
        # Still written atomically. Not for safety now, but because a half
        # written file in the sandbox would make a suite fail for a reason
        # that has nothing to do with the mutation, and this probe's whole
        # value is that a red suite means the thing it names.
        # Positioned from the masked text and spliced into the real one, so
        # the replacement lands in the code and never in the table quoting
        # it. The mask preserves line structure precisely so this index is
        # valid in both.
        _at = _search.find(old)
        mutated = original[:_at] + new + original[_at + len(old):]
        write_atomic(path, mutated)
        try:
            r = run_suite(suite, work)
        except subprocess.TimeoutExpired as _exc:
            # Not a catch and not a miss. The suite never finished, so nothing
            # at all is known about the control this mutation is aimed at, and
            # saying so is the only honest report.
            #
            # Seen on 29 September with a remaining time of minus 2138 seconds,
            # which is not a hang: a negative remainder means the deadline had
            # already passed when the wait began, because the machine slept
            # between starting the suite and waiting on it. Ninety minutes of
            # sleep and a genuinely wedged suite arrive here identically, and
            # neither says anything about the repair.
            #
            # Before this the exception escaped and killed the run. The restore
            # still happened, because it is in the finally below, and the tree
            # was clean afterwards. But the output was a traceback, which is the
            # one signal a failing control never produces, so reading it as
            # anything about the repairs would have been the same mistake this
            # probe refuses everywhere else.
            # Say which of the two it was rather than leaving the reader to
            # guess. A negative remainder is a deadline that passed while
            # nothing was executing, which only happens if the machine slept.
            _t = getattr(_exc, "timeout", None)
            _why = ("the machine slept mid-run: the deadline passed while "
                    "nothing was executing"
                    if isinstance(_t, (int, float)) and _t < 0
                    else "the suite genuinely ran past the limit")
            print(f"  [COULD NOT RUN] {finding}\n"
                  f"      {suite} did not finish. Nothing is established about "
                  f"its control\n      either way. Remaining time {_t}, so "
                  f"{_why}. Re-run it.")
            bad += 1
            continue
        finally:
            restore_in(work, _rel)

        blob = (r.stdout or "") + (r.stderr or "")
        if "Traceback (most recent call last)" in (r.stderr or ""):
            print(f"  [CRASHED] {finding}\n"
                  f"      {suite} crashed rather than failing controls, so "
                  f"its output says nothing about which controls hold.")
            bad += 1
        elif r.returncode == 0:
            print(f"  [MISSED] {finding}\n"
                  f"      the repair was removed and {suite} still passed. "
                  f"Nothing in that suite is checking for it.")
            bad += 1
        elif needle.lower() not in blob.lower():
            print(f"  [WRONG CONTROL] {finding}\n"
                  f"      {suite} went red, and not for anything mentioning "
                  f"{needle!r}. Something failed; it is not shown to be the "
                  f"control this repair is supposed to have.")
            bad += 1
        else:
            print(f"  [caught] {finding}")

    # The real tree, which this run should not have touched at all. Before the
    # sandbox this was the last line of defence; now it is an assertion that
    # the isolation held, and a failure here means something reached past it.
    left = []
    for rel in targets:
        p = REPO / rel
        now = (hashlib.sha256(p.read_bytes()).hexdigest()
               if p.is_file() else None)
        if now != before.get(rel):
            left.append(rel)
    if left:
        print(f"\n  [CHANGED DURING THE RUN] these differ from what they held "
              f"when this run\n  started:\n")
        for p in left:
            print(f"      {p}")
        print("\n  Two things look identical from here and this cannot tell "
              "them apart.\n"
              "  Either a mutation escaped the disposable checkout, which "
              "would mean the\n  isolation is broken, or somebody edited "
              "these files while the run was in\n  progress. Read `git diff` "
              "and decide which.\n\n"
              "  Either way this run's result is not evidence about the "
              "source as it stands\n  now. If it was an edit, commit it and "
              "run again; the result would otherwise\n  describe a commit "
              "nobody is using.")
        bad += 1

    subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force",
                    str(work)], capture_output=True, text=True, encoding="utf-8")
    subprocess.run(["git", "-C", str(REPO), "worktree", "prune"],
                   capture_output=True, text=True, encoding="utf-8")

    # SELF-F07, the EC-2 row: "A recent log containing one [caught] and no
    # recognized failure marker can pass the sweep check. An interrupted
    # sweep can satisfy that test without covering the expected mutation set.
    # Timestamp freshness also does not bind a sweep result to the exact
    # tested commit and mutation inventory."
    #
    # So the run states, in its own output, which commit it examined and how
    # many mutations the set held. A reader of the log, and the exit check
    # that parses it, can then tell a complete sweep from one that stopped
    # after four. Printed at the end rather than the start because at the
    # start it would survive the interruption it exists to reveal.
    print(f"\n  swept commit {_head() or 'unknown'}")
    print(f"  mutation set holds {len(MUTATIONS)}; this run looked at "
          f"{len(selected)}")

    print()
    _of = (f"{len(selected)} selected repair(s)" if want
           else f"{len(MUTATIONS)} repairs")
    if bad:
        print(f"  {bad} of {_of} are not demonstrably held by a control.")
        return 1
    print(f"  all {_of} go red when removed, each in a control that names what "
          f"it is about.")
    if want:
        print(f"  Only {', '.join(want)} was looked at. The rest of the set is "
              f"not established\n  by this run.")
    print("  That is not proof the repairs are correct. It is proof they are")
    print("  watched, which is the claim each commit made.")
    return 0


if __name__ == "__main__":
    # The log is opened here, before anything prints, so that a refusal is
    # recorded as faithfully as a finished sweep. A --out run that refuses and
    # writes nothing would leave whatever the previous run wrote in place, and
    # a reader would take the old file for this run's answer.
    _tee = None
    _dest = out_path()
    if _dest is not None:
        _dest.parent.mkdir(parents=True, exist_ok=True)
        _tee = Tee(sys.stdout, _dest)
        sys.stdout = _tee

    # The lock is released here rather than at each return inside main(),
    # because there are several and one of them would eventually be missed.
    # A killed run leaves it behind on purpose: the next run refuses and
    # prints the command to clear it, which is better than this process
    # deciding on its own that the other one is dead.
    try:
        _rc = main()
    finally:
        drop_lock()
        if _tee is not None:
            sys.stdout = _tee._stream
            _tee.close()
    raise SystemExit(_rc)
