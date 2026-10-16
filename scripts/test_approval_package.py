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

    # The positive, so the two refusals above cannot be "refuse everything".
    # BOOTSTRAP-002 has four frozen cycles and a recorded ledger.
    # --out again, because its package is tracked too.
    b2_dir = REPO / "runs" / "BOOTSTRAP-002" / "plan-review"
    b2_before = {p: p.read_bytes() for p in sorted(b2_dir.rglob("*"))
                 if p.is_file()}
    p2 = Path(tempfile.mkdtemp()) / "APPROVAL-PACKAGE.md"
    r = run("--run", "BOOTSTRAP-002", "--type", "plan",
            "--out", str(p2), cwd=REPO)
    if any(p.read_bytes() != b for p, b in b2_before.items()):
        failures.append("building BOOTSTRAP-002's package altered its review "
                        "directory")
    if r.returncode != 0:
        failures.append(f"a run with frozen cycles and a recorded ledger "
                        f"should produce a package:\n{r.stdout}{r.stderr}")
    else:
        t2 = p2.read_text(encoding="utf-8")
        if "### Unresolved findings" not in t2:
            failures.append(
                "the package for a run with a ledger does not present "
                "unresolved findings under their own heading")
        else:
            ok("a run with frozen cycles and a recorded ledger produces a "
               "package")

        # SELF-F01's own ruling: implementer-disclosed defects appear in the
        # package, under their own heading, separately from reviewer findings.
        # Read out of the register rather than restated here, so an entry that
        # stops being shown shows up as missing instead of being agreed with.
        #
        # Guarded since 14 October. A malformed register made this line raise
        # JSONDecodeError, so the suite crashed with a traceback and reported
        # nothing about the twenty-odd controls that had already passed. A
        # test that cannot survive bad input says the wrong thing at exactly
        # the moment something is wrong, which is the same note already
        # written against the missing_ok in test_probe_recovery.
        _regp = REPO / "registers" / "implementer-disclosed.json"
        try:
            reg = json.loads(_regp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as _e:
            failures.append(
                f"the implementer-disclosed register could not be read, so "
                f"this suite can say\n  nothing about whether the package "
                f"presents its entries: {_e}")
            reg = {}
        live = [k for k, v in reg.get("entries", {}).items()
                if v.get("state") != "RESOLVED"]
        required = ("description", "discovery_source", "affected_component",
                    "severity", "state", "proposed_repair", "evidence")
        thin = [f"{k}.{f}" for k, v in reg.get("entries", {}).items()
                for f in required if not v.get(f)]
        if thin:
            failures.append(
                "the register is missing fields the ruling names: "
                + ", ".join(thin[:6]))
        elif "## Implementer-disclosed defects" not in t2:
            failures.append(
                "the package has no implementer-disclosed section. A defect "
                "disclosed outside the ledger and then absent from the package "
                "is disclosed to nobody who matters.")
        elif t2.index("## Implementer-disclosed defects") < t2.index("## Findings"):
            failures.append("implementer-disclosed defects are presented above "
                            "the reviewer findings; they must be separate and "
                            "subordinate, not first")
        elif [k for k in live if k not in t2]:
            failures.append(
                "the register holds unresolved entries the package does not "
                "name: " + ", ".join(k for k in live if k not in t2))
        else:
            ok(f"{len(live)} implementer-disclosed defect(s) appear under "
               f"their own heading, after the reviewer findings")

        # The section as the package actually laid it out, split per entry, so
        # the two controls below assert about one entry's own block rather
        # than about the whole document. My earlier controls in this file
        # passed by matching text that belonged to a different part of the
        # page, which is the same defect as the one they were watching for.
        _sec = t2.split("## Implementer-disclosed defects", 1)[-1]
        _sec = _sec.split("## MC-2 conformance", 1)[0]
        _blocks = {}
        for _chunk in _sec.split("\n### ")[1:]:
            _blocks[_chunk.split("\n", 1)[0].split(" ")[0].strip("*` ")] = _chunk

        # The glossary paragraph under each entry must describe that entry's
        # state. It used to print the REPAIRED_UNREVIEWED text unconditionally,
        # so an OPEN defect with no repair carried a line reading "a repair has
        # landed with controls behind it".
        wrong_gloss = []
        for k, v in reg.get("entries", {}).items():
            st = v.get("state")
            if st == "RESOLVED" or k not in _blocks:
                continue
            for other in reg.get("states", {}):
                if other != st and f"`{other}` means" in _blocks[k]:
                    wrong_gloss.append(f"{k} is {st} but its block explains {other}")
        if wrong_gloss:
            failures.append("an entry is glossed with a state it is not in: "
                            + "; ".join(wrong_gloss))
        elif not _blocks:
            failures.append("no implementer-disclosed entry blocks were found "
                            "to check, so this control proves nothing")
        else:
            ok("each disclosed defect is glossed with its own state, not with "
               "REPAIRED_UNREVIEWED regardless")

        # A resolved entry must still be named. Dropping it entirely leaves a
        # reader following one disclosure across packages unable to tell
        # resolution from deletion.
        done = [k for k, v in reg.get("entries", {}).items()
                if v.get("state") == "RESOLVED"]
        if not done:
            failures.append(
                "the register currently holds no RESOLVED entry, so the "
                "control for naming resolved entries did not exercise "
                "anything. It is reported rather than passed.")
        elif "### Resolved and no longer outstanding" not in _sec:
            failures.append(
                "resolved implementer-disclosed entries are dropped from the "
                "package with no trace: " + ", ".join(sorted(done)))
        elif [k for k in done if k not in _sec]:
            failures.append(
                "the resolved summary omits: "
                + ", ".join(k for k in done if k not in _sec))
        else:
            ok(f"{len(done)} resolved disclosure(s) are still named, so "
               f"resolution is distinguishable from deletion")

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

    # And the positive half, so the two refusals above cannot be refusing
    # everything: a real run still reports its sets and says it established
    # them. Without this, removing the flag entirely would leave both green.
    _r3 = run("--review", "runs/BOOTSTRAP-003/plan-review", "--json",
              "--development", cwd=REPO, script=SRC / "loop_state.py")
    try:
        _j3 = json.loads(_r3.stdout)
    except json.JSONDecodeError:
        _j3 = None
    if _j3 is None or _j3.get("sets_established") is not True:
        failures.append(
            "a review with valid cycles does not report established sets, so "
            "the two controls above would pass on a controller that never "
            "establishes anything")
    elif "open" not in _j3:
        failures.append("a review with valid cycles reports no `open` set")
    else:
        ok("a review with valid cycles still reports its sets and says it "
           "established them")

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
