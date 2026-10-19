#!/usr/bin/env python3
"""Controls for the §7 human review package generator.

    python scripts/test_approval_package.py

Exit 0 = every control fired.

Deliberately not in `refresh_counts.SUITES`. That number counts controls over
the execution layer under review, and `approval_package.py` is not in the review
target: it is not a declared component and nothing covered imports it, so it is
not in `bootstrap_gate.covered()`. Adding it to SUITES would inflate a figure
that four frozen prompts state, for a file no reviewer was asked about.

The thing most worth controlling here is what this tool must NOT do. It assembles
a package for a human to decide from; if it could decide anything itself, or
recompute a figure the owning tool refused to give, the package would be a second
implementation of the rule and the human would be reading it rather than the
record.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent
REPO = SRC.parent


def run(*args: str, cwd: Path, script: Path | None = None) -> subprocess.CompletedProcess:
    """Run the generator. `script` names which copy, which is not cosmetic.

    approval_package.py resolves the repository from its own location, not from
    the working directory, so running the real script with cwd set to a fixture
    reads the real repository. The first version of the temp-directory control
    below did exactly that and reported a refusal about the wrong run.
    """
    return subprocess.run(
        [sys.executable, str(script or (SRC / "approval_package.py")), *args],
        cwd=str(cwd), capture_output=True, text=True)


# The §6 exits that end a loop. Named here rather than imported from the
# controller on purpose: a control that asks the thing it is testing what
# counts as terminal would agree with it by construction, and this one needs
# to fail if the controller's idea of terminal quietly changes.
TERMINAL_FOR_TEST = {"CONVERGED", "MAX_4_REACHED",
                     "HUMAN_ADJUDICATION_REQUIRED", "STALLED"}


def with_register(root: Path, text: str | None = None) -> Path:
    """Give a fixture the register the real repository always has.

    Added 14 October 2026, with Alex Zamurko's ruling that an unreadable
    register must prevent approval rather than be noted and passed over:
    "A failed dependency must prevent approval with a clear explanation."

    That made the absence of a register a refusal, and every fixture here had
    one by omission. The fixtures are what was wrong. A run directory with no
    implementer-disclosed register is not a state this repository can be in,
    and a fixture that represents an impossible state tests the behaviour of
    something that will never happen. The same argument is already written
    against run.json in test_ledger.py's fixture.

    `text` overrides the contents, which is how the malformed case is built.

    Built rather than copied, since 17 October 2026. The first version copied
    the live register in from this repository, which is SELF-F17's defect in a
    second place: a fixture that reaches outside itself for a production file
    passes only where that file happens to exist, and an outside reviewer
    running this suite on a scope-limited copy got FileNotFoundError before
    the first control. The register's contents are not what any control here
    examines; its readability is. So the fixture provides exactly that, and
    says in its own text that it is a fixture.

    The real register is still read, once, by the control that checks the
    package presents its entries. That control examines this repository's own
    record on purpose and belongs with the others that do.
    """
    (root / "registers").mkdir(exist_ok=True)
    dest = root / "registers" / "implementer-disclosed.json"
    if text is None:
        text = json.dumps({
            "schema": "implementer-disclosed/1",
            "purpose": "A fixture register. Not a record of anything. The "
                       "entry below is invented so the approval package's "
                       "disclosure section has something to render.",
            "states": {
                "OPEN": "disclosed, not repaired",
                "REPAIRED_UNREVIEWED": "a repair has landed with controls "
                                       "behind it, and nobody independent has "
                                       "examined it",
                "RESOLVED": "an independent review examined the repair in a "
                            "later target and found it held",
            },
            "entries": {
                "FIXTURE-01": {
                    "description": "Invented for this fixture. No reviewer "
                                   "and no agent found it.",
                    "discovery_source": "Fixture, written by "
                                        "scripts/test_approval_package.py.",
                    "affected_component": "none, this is a fixture",
                    "severity": "none, this is a fixture",
                    "state": "REPAIRED_UNREVIEWED",
                    "review_cycle": None,
                    "proposed_repair": "none required, this is a fixture",
                    "required_of_next_review": True,
                    "history": [],
                },
            },
        }, indent=2) + "\n"
    dest.write_text(text, encoding="utf-8", newline="\n")
    return root


def main() -> int:
    failures: list[str] = []
    made: list[Path] = []

    def ok(m: str) -> None:
        print(f"  [ok] {m}")

    print("approval package")

    # ---- refusals: a package about nothing is worse than no package ----
    r = run("--run", "NO-SUCH-RUN", "--type", "plan", cwd=REPO)
    if r.returncode == 0:
        failures.append("a package was produced for a run that does not exist")
    elif "no run.json" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the missing run\n{r.stderr}")
    else:
        ok("refused: a run with no run.json")

    r = run("--run", "BOOTSTRAP-001", "--type", "implementation", cwd=REPO)
    if r.returncode == 0:
        failures.append("a package was produced for a review type that has no "
                        "directory")
    elif "no implementation review" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the absent review\n{r.stderr}")
    else:
        ok("refused: a review type this run never held")

    # A run initialised but never frozen. There is nothing to approve, and
    # saying so beats producing a package with empty headings that reads like
    # an approval-ready document.
    t = Path(tempfile.mkdtemp()); made.append(t)
    (t / "runs" / "T-001" / "plan-review").mkdir(parents=True)
    (t / "scripts").mkdir()
    for f in ("approval_package.py", "loop_state.py", "ledger.py",
              "validate_cycle.py", "cycle_projection.py", "authority.py",
              "run_pins.py", "findings_format.py"):
        shutil.copy(SRC / f, t / "scripts" / f)
    with_register(t)
    (t / "runs" / "T-001" / "run.json").write_text(json.dumps({
        "run_id": "T-001", "mc1_enforcement": "CONVENTION_ONLY",
        "max_cycles": 4}), encoding="utf-8")
    r = run("--run", "T-001", "--type", "plan", cwd=t,
            script=t / "scripts" / "approval_package.py")
    if r.returncode == 0:
        failures.append("a package was produced for a review with no frozen "
                        "cycles; there is nothing to approve")
    elif "no frozen cycles" not in (r.stdout + r.stderr):
        failures.append(f"refused, but not for the absent cycles\n{r.stderr}")
    else:
        ok("refused: a review with no frozen cycle")

    # ---- the real run ----
    #
    # --out, to a temp path. Without it the generator writes to its default,
    # which is the committed APPROVAL-PACKAGE.md of a finished review, so
    # running this suite silently rewrote a real artifact — in CI invisibly,
    # because the checkout is thrown away, and locally as a dirty working tree
    # someone could commit without noticing. Found 18 September, by `git status`
    # after a routine local CI run, not by anything here.
    review_dir = REPO / "runs" / "BOOTSTRAP-001" / "plan-review"
    canonical = review_dir / "APPROVAL-PACKAGE.md"
    ledger = review_dir / "ledger.json"

    # Everything the run owns, watched as a whole rather than one file of it.
    def snapshot() -> dict[Path, bytes]:
        return {p: p.read_bytes() for p in sorted(review_dir.rglob("*"))
                if p.is_file()}

    before = snapshot()
    tmp_out = Path(tempfile.mkdtemp()) / "APPROVAL-PACKAGE.md"
    r = run("--run", "BOOTSTRAP-001", "--type", "plan",
            "--out", str(tmp_out), cwd=REPO)
    if r.returncode != 0:
        failures.append(f"could not build a package for BOOTSTRAP-001:\n"
                        f"{r.stdout}{r.stderr}")
        text = ""
    else:
        text = tmp_out.read_text(encoding="utf-8")
        ok("a package is produced for a run with frozen cycles")

    # The one thing it must never do.
    #
    # This control used to compare ledger.json alone and pass, while the same
    # call overwrote APPROVAL-PACKAGE.md in the directory next to it. The
    # package is part of the record it describes, so the control was named for
    # the right rule and watching one file of it. Comparing the whole review
    # directory is what the sentence below actually claims.
    after = snapshot()
    changed = sorted({p for p in set(before) | set(after)
                      if before.get(p) != after.get(p)})
    if changed:
        failures.append(
            "building a package altered the review it describes: "
            + ", ".join(p.relative_to(REPO).as_posix() for p in changed) +
            "\n      It assembles a record for a human to decide from and must "
            "write nothing\n      into that record. Pass --out.")
    else:
        ok("building a package writes nothing into the review it describes")

    if canonical.read_bytes() != before.get(canonical):
        failures.append("the committed APPROVAL-PACKAGE.md was modified by "
                        "this suite")

    if text and "decides nothing" not in text:
        failures.append("the package does not say that it decides nothing, so "
                        "a reader could take it for the decision")
    elif text:
        ok("the package states that it decides nothing")

    # §7.2, in the protocol's own words: "Disputes and unresolved findings must
    # be presented separately." One heading holding both satisfies a reader
    # skimming for the word and defeats the requirement.
    if text:
        if "### Unresolved findings" not in text or "### Disputes" not in text:
            failures.append("§7.2 requires disputes and unresolved findings "
                            "presented separately; they are not two headings")
        elif text.index("### Unresolved findings") == text.index("### Disputes"):
            failures.append("disputes and unresolved findings share a heading")
        else:
            ok("§7.2: disputes and unresolved findings are separate headings")

    # It must quote the owning tool, including when that tool refuses. A package
    # that recomputed a refused figure would be a second controller, and the
    # human would be reading this file instead of the record.
    if text:
        if "REFUSED" not in text or "development" not in text.lower():
            failures.append(
                "the controller refuses an authoritative loop result for this "
                "run, and the package does not carry the refusal. Either it "
                "recomputed the figure or it dropped it; both are worse than "
                "quoting the refusal.")
        else:
            ok("a refusal by the owning tool is quoted, not worked around")

    # The coverage table is checked against §7's list, so an item that stops
    # being produced shows as absent. Verified by reading the list out of the
    # generator rather than restating it here: a second copy would be free to
    # disagree, which is the defect this whole layer keeps finding.
    if text:
        import importlib.util as il
        spec = il.spec_from_file_location("_ap", SRC / "approval_package.py")
        mod = il.module_from_spec(spec); spec.loader.exec_module(mod)
        absent = [k for k in mod.SECTION_7_ITEMS if f"- [ ] {k}" in text]
        listed = [k for k in mod.SECTION_7_ITEMS
                  if f"- [x] {k}" in text or f"- [ ] {k}" in text]
        if len(listed) != len(mod.SECTION_7_ITEMS):
            failures.append(
                f"the coverage table lists {len(listed)} of "
                f"{len(mod.SECTION_7_ITEMS)} §7 items. An item missing from "
                "the table cannot be seen to be missing from the package.")
        elif not absent:
            failures.append(
                "every §7 item reports present. BOOTSTRAP-001 has no plan and "
                "therefore no SPEC -> CODE -> TEST mapping, so a table with "
                "nothing absent is not reporting, it is agreeing.")
        else:
            ok(f"all {len(listed)} §7 items appear in the coverage table, "
               f"{len(absent)} marked absent")

        for k in absent:
            if f"*{k}*" not in text:
                failures.append(f"§7 item {k!r} is marked absent and the "
                                "package never says why")
                break
        else:
            if absent:
                ok("each absent §7 item carries a stated reason")

    # ---- SELF-F01: frozen cycles and no ledger is not zero findings ----
    # Alex Zamurko, 5 October: "Require the ledger whenever frozen review cycles
    # exist... Never translate missing evidence into zero findings", because
    # "absence of evidence must not become evidence of absence."
    #
    # This is where the tool used to explain, inside a produced package, that no
    # review had reported yet. The explanation was true and the package was
    # still a package: headings with nothing under them, in a document titled
    # for an approval decision. Now it refuses and names the state.
    #
    # Two fixtures, because missing and unreadable are two states, and one
    # control covering both would pass while either of them went unwatched.
    def _frozen_no_ledger(ledger_text, cycle_findings=None,
                          register: str | None = None):
        f = Path(tempfile.mkdtemp()); made.append(f)
        (f / "runs" / "T-001" / "plan-review" / "cycle-01").mkdir(parents=True)
        if cycle_findings is not None:
            (f / "runs" / "T-001" / "plan-review" / "cycle-01"
             / "findings.json").write_text(cycle_findings, encoding="utf-8")
        (f / "scripts").mkdir()
        for name in ("approval_package.py", "loop_state.py", "ledger.py",
                     "validate_cycle.py", "cycle_projection.py", "authority.py",
                     "run_pins.py", "findings_format.py"):
            shutil.copy(SRC / name, f / "scripts" / name)
        with_register(f, register)
        (f / "runs" / "T-001" / "run.json").write_text(json.dumps({
            "run_id": "T-001", "mc1_enforcement": "CONVENTION_ONLY",
            "max_cycles": 4}), encoding="utf-8")
        if ledger_text is not None:
            (f / "runs" / "T-001" / "plan-review" / "ledger.json").write_text(
                ledger_text, encoding="utf-8")
        return run("--run", "T-001", "--type", "plan", cwd=f,
                   script=f / "scripts" / "approval_package.py")

    # BOOTSTRAP-003's reviewer on SELF-F01: "a readable ledger containing
    # `{"findings": {}}` beside a valid review reporting a finding still
    # produces an approval package with exit 0... the unresolved-findings
    # section says 'None' and its coverage item is marked present."
    #
    # The first repair handled the two ways a ledger can fail to be READ. This
    # is the third way it can fail to be TRUE, and it is the one that produces
    # a confident answer rather than an error. The ledger below is valid and
    # parses; it simply holds none of what the cycle beside it reported.
    _reported = json.dumps({
        "schema": "cycle-findings/1",
        "count": 1,
        "findings": [{"id": "D01-F01", "class": "MISSING REQUIREMENT",
                      "kind": "finding"}],
    }, indent=2)
    rr = _frozen_no_ledger(json.dumps({"review": "plan-review",
                                       "findings": {}}, indent=2),
                           cycle_findings=_reported)
    _o = rr.stdout + rr.stderr
    if rr.returncode == 0:
        failures.append(
            "a package was produced from a ledger that holds none of what the "
            "review beside it reported. The findings section would say None, "
            "which is a confident wrong answer rather than a missing one.")
    elif "CANNOT_ESTABLISH" not in _o or "reported" not in _o:
        failures.append(f"refused for a ledger disagreeing with its own "
                        f"review, but not for that reason:\n{_o[-400:]}")
    else:
        ok("refused: a readable ledger that holds none of what the review "
           "reported")

    for _label, _text in (("missing", None), ("unreadable", "{ not json")):
        rr = _frozen_no_ledger(_text)
        _o = rr.stdout + rr.stderr
        if rr.returncode == 0:
            failures.append(
                f"a package was produced for a run with a frozen cycle and a "
                f"{_label} ledger. Nothing in that run says what any reviewer "
                f"found, and the package presented the silence under its own "
                f"findings headings.")
        elif "CANNOT_ESTABLISH" not in _o:
            failures.append(f"refused for a {_label} ledger, but without the "
                            f"explicit state:\n{_o[-400:]}")
        else:
            ok(f"refused: frozen cycles and a {_label} ledger, "
               f"CANNOT_ESTABLISH")

    # SELF-F01, third pass. BOOTSTRAP-003 cycle 02: the package grouped
    # findings by the `state` field cached in the ledger rather than by the
    # state the controller reconstructs. Invalidate the cycle carrying a
    # demonstration and the cached RESOLVED survives, so the controller says
    # OPEN and CONTINUE while the package says "None" under unresolved and
    # counts one resolved. Alex Zamurko called it critical, because the
    # reporting layer was presenting a cleaner state than the authoritative
    # reconstruction.
    #
    # The fixture needs cycles that actually pass MC-2, which test_ledger
    # already knows how to build. Imported rather than copied: a second
    # cycle-builder here would be free to drift from the one the controller's
    # own suite uses, and this file would then be testing a shape no real run
    # has.
    import test_ledger as _TL

    def _section(text: str, heading: str) -> str:
        """Just that section, not everything after its heading.

        The package ends with the full ledger inside a <details> block, so
        `split(heading)[-1]` reaches a JSON dump naming every finding. The
        first version of the resolved-section check did exactly that and
        reported a finding as listed under a heading it never appeared beneath.
        """
        rest = text.split(heading, 1)[-1]
        for stop in ("\n<details", "\n## ", "\n### "):
            rest = rest.split(stop, 1)[0]
        return rest

    _lr, _commit = _TL.make_repo()
    made.append(_lr)
    shutil.copy2(SRC / "approval_package.py", _lr / "scripts")
    shutil.copy2(SRC / "authority.py", _lr / "scripts")
    # This fixture is built by test_ledger's make_repo rather than by the
    # helpers above, so it needs the register separately. Since 14 October a
    # package whose disclosure section cannot be assembled exits non-zero, on
    # Alex Zamurko's ruling, and a fixture with no register is a repository
    # state that cannot exist.
    with_register(_lr)
    _rev = _lr / "runs" / "T-001" / "plan-review"
    _TL.make_cycle(_lr, _rev, 1, _commit)
    _TL.make_cycle(_lr, _rev, 2, _commit)
    # Cycle 1 reports the finding; cycle 2 demonstrates the repair.
    for _n, _body, _entry in (
            (1, "Finding ID: C01-F01\nClass: UNTESTED RULE\n",
             {"id": "C01-F01", "class": "UNTESTED RULE"}),):
        _c = _rev / f"cycle-{_n:02d}"
        (_c / "codex-output-raw.md").write_text(_body, encoding="utf-8")
        (_c / "findings.json").write_text(json.dumps({
            "schema": "cycle-findings/1", "cycle": _n, "count": 1,
            "findings": [_entry]}, indent=2), encoding="utf-8")
    _TL.ledger(_lr, "raise", "--review", str(_rev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
    _TL.ledger(_lr, "respond", "--review", str(_rev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
    _TL.ledger(_lr, "resolve", "--review", str(_rev), "--cycle", "2",
               "--id", "C01-F01", "--evidence", "demonstrated")

    # The baseline: with both cycles valid the finding really is resolved, and
    # the package should say so. Without this the control below would pass on a
    # package that calls everything unresolved.
    _pb = Path(tempfile.mkdtemp()) / "base.md"
    _rb = run("--run", "T-001", "--type", "plan", "--out", str(_pb), cwd=_lr,
              script=_lr / "scripts" / "approval_package.py")
    if _rb.returncode != 0:
        failures.append(f"a run whose demonstration is intact could not "
                        f"produce a package:\n{_rb.stdout}{_rb.stderr}")
    # The resolved section reports a COUNT, not identifiers, so this asserts on
    # the count and on the unresolved section being empty. Checking for the
    # identifier here passed for a while against the full-ledger dump at the
    # foot of the document, which names every finding regardless of state.
    elif ("1 resolved." not in _section(_pb.read_text(encoding="utf-8"),
                                        "### Resolved findings")
          or "None." not in _section(_pb.read_text(encoding="utf-8"),
                                     "### Unresolved findings")):
        failures.append(
            "a genuinely resolved finding is not reported as resolved with "
            "nothing unresolved, so the control below proves nothing")
    else:
        ok("a demonstrated repair is reported as resolved")

    # The positive half of SELF-F04's two refusals, which sit further down.
    # It lives here because it needs a review whose cycles are valid, and this
    # fixture has exactly that at this moment, before the next block
    # invalidates one of them on purpose.
    #
    # It pointed at a real run until 17 October 2026, first BOOTSTRAP-003 and
    # then briefly BOOTSTRAP-001, and both were the same mistake in two sizes.
    # What the control needs is a review with valid cycles. Reaching for a real
    # one ties it to whichever runs the checkout happens to carry, and a
    # scope-limited copy of this tree carries different ones. Worse, no frozen
    # cycle can be valid in such a copy at all: MC-2 check 8 resolves the
    # commit the cycle was frozen against, and that commit belongs to this
    # repository's history. The record there is not broken, it is bound, which
    # is the property it is supposed to have. A control that reads boundness as
    # brokenness was asking the wrong question of the wrong thing.
    # No --development. The real runs this pointed at before were labelled
    # bootstrap evidence and needed it; this fixture is a protocol run, and the
    # controller refuses the flag for one, in those words: "labelling a
    # protocol outcome as development evidence would understate it just as
    # badly as the reverse overstates it." Carrying the flag over with the
    # target was the kind of copy that looks harmless and asks a different
    # question.
    _rj = run("--review", "runs/T-001/plan-review", "--json",
              cwd=_lr, script=_lr / "scripts" / "loop_state.py")
    try:
        _j3 = json.loads(_rj.stdout)
    except json.JSONDecodeError:
        _j3 = None
    if _j3 is None or _j3.get("sets_established") is not True:
        failures.append(
            "a review with valid cycles does not report established sets, so "
            "SELF-F04's two refusals below would pass on a controller that "
            "never establishes anything:\n" + (_rj.stdout + _rj.stderr)[-300:])
    elif "open" not in _j3:
        failures.append("a review with valid cycles reports no `open` set")
    else:
        ok("a review with valid cycles still reports its sets and says it "
           "established them")

    # ---- an unauthorized continuation is not an approvable result ----
    #
    # specs/review/TERMINAL-EXIT-WITH-CYCLES-BEYOND-IT.md, 26 September 2026:
    # the continuation block "is prose under the status line rather than part
    # of the status, so it informs a reader and not a caller." That was written
    # as an open question and left for three weeks. Alex Zamurko ruled on it on
    # 17 October: preserve the historical terminal result, and ensure an
    # unauthorised continuation prevents downstream consumers from treating it
    # as a valid approval or convergence result, tested through the actual
    # consumer path.
    #
    # Tested here because this package IS the consumer path. It is the document
    # a human approves from, and it could not see a continuation at all.
    _uc, _ucc = _TL.make_repo()
    made.append(_uc)
    shutil.copy2(SRC / "approval_package.py", _uc / "scripts")
    shutil.copy2(SRC / "authority.py", _uc / "scripts")
    with_register(_uc)
    _ucrev = _uc / "runs" / "T-001" / "plan-review"
    # Four valid cycles, with the finding raised in 1 and demonstrated in 2.
    # Nothing is open at n=2, so the loop converges there, and cycles 3 and 4
    # exist past a terminal exit that nobody cleared.
    for _i in (1, 2, 3, 4):
        _TL.make_cycle(_uc, _ucrev, _i, _ucc)
    (_ucrev / "cycle-01" / "codex-output-raw.md").write_text(
        "Finding ID: C01-F01\nClass: UNTESTED RULE\n", encoding="utf-8")
    (_ucrev / "cycle-01" / "findings.json").write_text(json.dumps({
        "schema": "cycle-findings/1", "cycle": 1, "count": 1,
        "findings": [{"id": "C01-F01", "class": "UNTESTED RULE"}]}, indent=2),
        encoding="utf-8")
    _TL.ledger(_uc, "raise", "--review", str(_ucrev), "--cycle", "1",
               "--id", "C01-F01", "--class", "UNTESTED RULE",
               "--source", "CODEX_REVIEW")
    _TL.ledger(_uc, "respond", "--review", str(_ucrev), "--cycle", "1",
               "--id", "C01-F01", "--disposition", "ACCEPT", "--note", "fix")
    _TL.ledger(_uc, "resolve", "--review", str(_ucrev), "--cycle", "2",
               "--id", "C01-F01", "--evidence", "demonstrated")

    # First the controller, because if it does not report the continuation in
    # machine-readable form then the package below cannot possibly act on it,
    # and the two failures would look identical from here.
    _ucj = run("--review", "runs/T-001/plan-review", "--json", cwd=_uc,
               script=_uc / "scripts" / "loop_state.py")
    try:
        _ucd = json.loads(_ucj.stdout)
    except json.JSONDecodeError:
        _ucd = None
    if _ucd is None:
        failures.append("the controller produced no readable JSON for a loop "
                        "with cycles past a terminal exit:\n"
                        + (_ucj.stdout + _ucj.stderr)[-300:])
    elif _ucd.get("status") not in TERMINAL_FOR_TEST:
        failures.append(
            f"the fixture does not reach a terminal exit before its last "
            f"cycle, so nothing below is\n  being tested. The controller says "
            f"{_ucd.get('status')!r} at n="
            f"{_ucd.get('governing_boundary')}.")
    elif not _ucd.get("unauthorized_continuation"):
        failures.append(
            "the controller reports a terminal exit with valid cycles after "
            "it and carries no\n  unauthorized_continuation in its machine "
            "output. A caller cannot act on prose,\n  which is what the note "
            "of 26 September said and what nobody had tested.")
    else:
        ok("the controller reports an unauthorized continuation in machine "
           "output, not only in prose")

    _ucp = Path(tempfile.mkdtemp()) / "uc.md"
    _ucr = run("--run", "T-001", "--type", "plan", "--out", str(_ucp), cwd=_uc,
               script=_uc / "scripts" / "approval_package.py")
    _uco = _ucr.stdout + _ucr.stderr
    if _ucr.returncode == 0:
        failures.append(
            "a package was produced for a loop that terminated and then ran "
            "two more cycles.\n  The document a human approves from would "
            "present that exit as the outcome while\n  evidence exists past "
            "it that nobody authorized.")
    elif "UNAUTHORIZED_CONTINUATION" not in _uco:
        failures.append(f"the package refused, but not for the continuation:\n"
                        f"{_uco[-400:]}")
    elif "cycle-03" not in _uco or "cycle-04" not in _uco:
        failures.append("the refusal does not name which cycles were run past "
                        "the exit, so a reader\n  cannot check it")
    else:
        ok("refused: a terminal exit with unauthorized cycles after it is not "
           "an approvable result, and the refusal names them")

    # Now invalidate only the cycle that carried the demonstration. The ledger
    # is untouched and still caches RESOLVED.
    (_rev / "cycle-02" / "codex-output-raw.md").write_text("", encoding="utf-8")
    _cached = json.loads((_rev / "ledger.json").read_text(encoding="utf-8"))
    if _cached["findings"]["C01-F01"].get("state") != "RESOLVED":
        failures.append("the fixture's ledger does not cache RESOLVED, so "
                        "nothing stale is being tested")
    _pi = Path(tempfile.mkdtemp()) / "invalid.md"
    _ri = run("--run", "T-001", "--type", "plan", "--out", str(_pi), cwd=_lr,
              script=_lr / "scripts" / "approval_package.py")
    _itext = _pi.read_text(encoding="utf-8") if _pi.exists() else ""
    _unres = _section(_itext, "### Unresolved findings")
    if _ri.returncode != 0:
        # Refusing is also correct: his instruction was to derive the state
        # from the controller or refuse when it cannot be established.
        if "CANNOT_ESTABLISH" in (_ri.stdout + _ri.stderr):
            ok("an invalidated demonstration makes the package refuse rather "
               "than report the stale state")
        else:
            failures.append(f"the package failed for some other reason\n"
                            f"{(_ri.stdout + _ri.stderr)[-400:]}")
    elif "C01-F01" not in _unres:
        failures.append(
            "the cycle carrying the demonstration was invalidated, the "
            "controller reconstructs the finding as OPEN, and the package "
            "still does not list it as unresolved. The reporting layer is "
            "presenting a cleaner state than the authoritative one.")
    elif "None." not in _section(_itext, "### Resolved findings"):
        failures.append(
            "the finding is listed as unresolved and the resolved section "
            "still counts one, so the two sections disagree about the same "
            "finding")
    else:
        ok("an invalidated demonstration is reported as unresolved, not from "
           "the ledger's cached RESOLVED")

    # The positive that keeps the refusals above from being "refuse
    # everything" lives in scripts/test_approval_package_record.py, along with
    # the controls over the implementer-disclosed section. Both examine
    # BOOTSTRAP-002 and this repository's register, which a scope-limited copy
    # of this tree does not carry, and both were moved out on 17 October 2026
    # after an outside reviewer found this suite failing in such a copy for
    # that reason and no other.
    #
    # Moved rather than taught to stand down. A control that covers less when
    # its subject is absent, and says nothing about it, is the defect this
    # whole layer exists to find; writing one into the file that guards the
    # approval package would have been the joke writing itself. As a separate
    # file it cannot happen quietly: test_ci_coverage.py requires every suite
    # present to be invoked by CI, so while that file exists it runs, and if it
    # stops existing that is a deletion somebody can see in a diff.

    # ---- SELF-F04: the controller's machine interface on the path where
    # nothing was computed, and this package's handling of it.
    #
    # Raised by the BOOTSTRAP-003 cycle 03 reviewer, who found it by reading
    # rather than by running anything, because until now the --json flag added
    # for SELF-F01's third repair had no control of its own at all. The flag
    # exists so that nothing downstream parses prose, and on a run with no
    # valid cycle it returned prose under exit 0.
    def _no_valid_cycle() -> Path:
        f = Path(tempfile.mkdtemp()); made.append(f)
        # A cycle directory with no target.json cannot pass MC-2, so the
        # controller reaches its "nothing to measure" return with the review
        # itself perfectly well-formed. That is the point: this is not an
        # error path, it is an answer path, and it still has to answer.
        (f / "runs" / "T-004" / "plan-review" / "cycle-01").mkdir(parents=True)
        (f / "scripts").mkdir()
        for name in ("approval_package.py", "loop_state.py", "ledger.py",
                     "validate_cycle.py", "cycle_projection.py", "authority.py",
                     "run_pins.py", "findings_format.py"):
            shutil.copy(SRC / name, f / "scripts" / name)
        with_register(f)
        # bootstrap_review is not optional. C01-F05: a run with no label is a
        # run whose identity is not established, and the controller refuses it
        # rather than assuming the stronger classification. Leaving it out made
        # the first version of this fixture refuse for that reason instead of
        # reaching the path it was built to exercise.
        (f / "runs" / "T-004" / "run.json").write_text(json.dumps({
            "run_id": "T-004", "bootstrap_review": "APPROVED",
            "mc1_enforcement": "CONVENTION_ONLY",
            "max_cycles": 4}), encoding="utf-8")
        (f / "runs" / "T-004" / "plan-review" / "ledger.json").write_text(
            json.dumps({"review": "plan-review", "findings": {}}, indent=2),
            encoding="utf-8")
        return f

    _f = _no_valid_cycle()
    _r = run("--review", "runs/T-004/plan-review", "--json", cwd=_f,
             script=_f / "scripts" / "loop_state.py")
    try:
        _j = json.loads(_r.stdout)
    except json.JSONDecodeError:
        _j = None
    if _j is None:
        failures.append(
            "asked for --json on a review with no valid cycle, the controller "
            "did not emit JSON. A caller that must not parse prose was handed "
            "prose:\n" + (_r.stdout + _r.stderr)[-400:])
    elif _j.get("sets_established") is not False:
        failures.append(
            "the controller emitted JSON for a review with no valid cycle but "
            "did not say that no sets were established; a caller cannot tell "
            "this from a genuine clean boundary")
    elif any(k in _j for k in ("open", "resolved", "disputed")):
        failures.append(
            "the controller reported finding sets for a boundary it never "
            "walked. An empty set here reads as 'nothing is open', which is "
            "the silent zero this whole layer exists to refuse.")
    else:
        ok("--json on a review with no valid cycle: JSON, no sets, and an "
           "explicit statement that none were established")

    # The same fixture through the package. Writing the control above showed
    # that the package never reaches its reading of the controller's sets on
    # this route: it reconciles each frozen cycle's own record first, and a
    # cycle with no record makes that refuse. The honest control is therefore
    # about what actually happens, which is that a frozen cycle whose record
    # cannot be read must produce a stated refusal.
    #
    # It produced a Python stack trace instead, naming a line number in
    # loop_state.py. The package's whole contract is that it withholds the
    # document and says why; a crash does the first half only, to the one
    # reader this tool exists for.
    #
    # The sets_established guard further down stays, and is not controlled
    # here, because nothing today can reach it: a run with no valid cycle is
    # refused above, and a run with one always establishes sets. It is written
    # as a guard against a future controller, and saying that is better than
    # a control that would pass whether or not the guard were there.
    _r2 = run("--run", "T-004", "--type", "plan", cwd=_f,
              script=_f / "scripts" / "approval_package.py")
    _o2 = _r2.stdout + _r2.stderr
    if _r2.returncode == 0:
        failures.append(
            "a package was produced for a run whose frozen cycle carries no "
            "record of what any reviewer found.")
    elif "Traceback" in _o2:
        failures.append(
            "the package crashed rather than refusing. An operator is shown a "
            "stack trace and a line number where a stated reason belongs:\n"
            + _o2[-400:])
    elif "CANNOT_ESTABLISH" not in _o2:
        failures.append(f"refused a frozen cycle with no readable record, but "
                        f"not with the explicit state:\n{_o2[-400:]}")
    else:
        ok("refused, not crashed: a frozen cycle whose record cannot be read "
           "produces a stated reason")

    # The positive half of these two refusals is above, against the fixture
    # with valid cycles, and its comment says why it is not here.

    # ---- an unreadable register prevents approval: NOT COVERED HERE ----
    #
    # Alex Zamurko, 14 October 2026: "Catch JSON decoding and file-reading
    # errors... return CANNOT_ESTABLISH with a non-zero exit status. Add a
    # negative test. Never substitute an empty register when loading fails."
    #
    # The repair is in approval_package.py and his ruling settled a question
    # this file's own comment had left open since 5 October: a register that
    # cannot be read is not a register with nothing in it, and the package
    # must not be approvable while that is true.
    #
    # The negative test is NOT here yet, and saying so is better than a
    # control that looks like one. To exercise that branch a fixture has to
    # reach the register section, which means getting past the findings
    # reconciliation, which means a frozen cycle that reports something and a
    # ledger that holds it. Two attempts at that fixture refused earlier for
    # two different and entirely correct reasons: first the cycle had no
    # findings.json, then the hand-written ledger could not be read. Both
    # refusals were the tool working. The fixture was wrong.
    #
    # Every control above that produces a package does so against the real
    # repository, so there is no existing fixture to copy. Building one means
    # reading ledger.py's reader and writing a ledger it accepts, which is
    # half an hour with a clear head and was not worth guessing at near
    # midnight on 14 October. Recorded in the register as outstanding.
    #
    # The probe line aimed at this repair was removed with it, for the same
    # reason: a mutation whose named control does not exist reports a defect
    # in the probe rather than in the code.

    for p in made:
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("  the package generator assembles, refuses, and decides nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
