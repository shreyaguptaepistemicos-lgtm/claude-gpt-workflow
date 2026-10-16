#!/usr/bin/env python3
"""The one-time bootstrap review, and the gate that makes it mandatory.

    python scripts/bootstrap_gate.py check
    python scripts/bootstrap_gate.py record --decision APPROVE \\
        --decided-by "Alex Zamurko" --note "..."

Exit 0 = a bootstrap review exists, was approved, and still covers the code that
is actually on disk.
Exit 1 = it does not, and no real protocol cycle may run.
Exit 2 = could not run.

Why this exists
---------------
The orchestrator exists to constrain the implementing agent, and the implementing
agent wrote it. The MC-2 checker decides whether a cycle counts, and the same
agent wrote that too. Neither can go through the process it enables, because the
process does not exist until they do.

Alex Zamurko ruled on 8 September 2026:

    Make a one-time BOOTSTRAP_REVIEW mandatory before relying on those
    components for real protocol cycles. Preserve the exact bootstrap input, raw
    Codex output, findings, responses, and human decision.

So this is the one declared exception to the protocol, made explicit and made
enforceable rather than left as a paragraph someone remembers.

The part that is easy to get wrong
----------------------------------
A gate that only asks "did a bootstrap review happen" passes forever. The review
would authorise the code as it stood that day, the code would change the next
morning, and the gate would keep saying yes about a file that no longer exists in
the form anyone reviewed. That is the same defect as a green test pinned to a
superseded protocol, one level up.

So the decision record pins the sha256 of every component it covers, and `check`
re-hashes them. Editing a reviewed component invalidates the review, by design.
Re-reviewing is the cost of changing the thing that everything else trusts.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import authority  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO / "bootstrap-review"
RECORD = REVIEW_DIR / "decision.json"

# Alex Zamurko, 9 September 2026, rulings 1 and 2:
#
#     Cycle 02 remains inside the bootstrap exception; start the ACTIVE/CANDIDATE
#     chain only after the first human approval ... The bootstrap exception ends
#     immediately after the first human approval of a runner ... without a precise
#     termination point, "bootstrap" can become an indefinite exemption.
#
# So the exception is not a period someone declares over. It ends when the first
# runner approval exists, and that is a fact on disk rather than a judgement.
RUNNER_APPROVAL_DIR = "runner-approvals"

# The declared roots. Widened from two to four by Alex Zamurko, 9 September 2026:
# ledger.py and loop_state.py "determine the authoritative meaning of otherwise
# valid review evidence ... An error here could produce a false process outcome
# even when MC-2 evidence is valid."
#
# The section mapping is his, and it is what the review is against:
#
#     validate_cycle.py   MC-2, §10.2
#     run_review.py       §2.2, §10.1
#     ledger.py           §§5, 12
#     loop_state.py       §§6, 13
# The evidence schema is here because of B01-F10: the frozen review target
# carried six artifacts and the covered set held five. Codex was reviewing the
# schema, and editing it afterwards did not invalidate its own approval.
#
# It is not a script, and it implements no code, but MC-2 checks evidence
# against it. A gate that covers the checker and not the document the checker
# reads its expectations from has a seam running straight through the middle of
# what it claims to cover.
# C03-F02. Alex Zamurko, 2 October 2026, on a covered set that had grown from
# ten files to seventeen by textual reference:
#
#     Make the covered-component set explicit and authoritative... A filename
#     appearing in source code, comments, documentation, strings, fixtures, or
#     other covered files must not automatically add that file to the covered
#     set... Treat test suites and execution records as review evidence unless
#     explicitly declared as covered components.
#
# I proposed an explicit list here and he corrected it in the same conversation:
#
#     The weak point is having the gate maintain a second independent copy of
#     the covered-file list. That creates two sources of truth and introduces
#     synchronization risk... Store the covered-file set in one canonical
#     manifest.
#
# So there is no list in this file. There is the location of the one list, and
# everything that reads it reads it from there.
COVERED_MANIFEST = "specs/covered-components.json"
MANIFEST_SCHEMA = "covered-components/1"

# One approval per manifest version, at a path derived from the version rather
# than discovered. Alex Zamurko, 2 October: "A workflow message counts as
# authorisation evidence only if it is persisted and referenced deterministically
# as a durable approval record."
SCOPE_APPROVAL_DIR = "approvals/covered-scope"

# This file is always covered, whatever the roots are. It was not, which is the
# hole Alex found on 9 September.
#
# What that fixes, precisely, and what it does not. Covering this file means a
# later edit to it is DETECTED, by a subsequent run of the unedited code. It does
# not mean the edit is prevented, and it does not survive an edit that also
# disables the detection: replacing `evaluate` with an unconditional success
# defeats the self-hash along with everything else, because the same writable
# code performs both.
#
# An earlier comment here claimed self-hashing closed that hole. Codex raised it
# as B01-F15 and was right. Under CONVENTION_ONLY this is drift detection that
# holds when the checks run faithfully, and nothing stronger. The stronger claim
# needs a write boundary the implementing agent does not hold, which is what
# MC1_ENFORCEMENT: TECHNICALLY_ENFORCED would record.
ALWAYS = ("scripts/bootstrap_gate.py",)

# A filename mentioned as a string, which is how this repository loads modules
# dynamically: run_review.py builds a path to bootstrap_gate.py, and both
# run_review.py and loop_state.py invoke validate_cycle.py as a subprocess.
PY_REF = __import__("re").compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.py)\b")

# Named in the ruling: "the exact bootstrap input, raw Codex output, findings,
# responses, and human decision". The decision is decision.json; these are the
# other four, and all must be present and non-empty before a decision is written.
EVIDENCE = (
    "codex-input.md",
    "codex-output-raw.md",
    "findings.md",
    "claude-response.md",
)

DECISIONS = ("APPROVE", "RETURN_FOR_REWORK", "REJECT")


class Refused(Exception):
    """Exit 1, change nothing."""


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def references(path: Path) -> set[str]:
    """Every scripts/*.py this file could load, by either route.

    Two routes, because this repository uses both and an earlier version saw
    only one. Codex, B01-F16:

        Dependency discovery recognizes filename strings ending in `.py`.
        Ordinary `import helper_module` and `from helper_module import VALUE`
        are not recognized.

    That was correct, and the control that was supposed to demonstrate the
    closure inserted `_HELPER = "helper_module.py"` — a string. So it exercised
    the route that already worked and said nothing about the one that did not.
    A real local import sat outside the approval hash set.

    Imports are read from the parsed syntax tree rather than by regex, because a
    regex over source text cannot tell an import from the word "import" in a
    comment, and being wrong in that direction means covering files nothing
    actually loads.
    """
    text = path.read_text(encoding="utf-8")
    found = {f"scripts/{n}" for n in PY_REF.findall(text)}

    # The filename scan applies to every covered file; import analysis only to
    # Python. A covered file need not be code — the evidence schema is covered
    # because MC-2 reads its expectations from it — and ast.parse on markdown
    # raises rather than returning nothing.
    if path.suffix != ".py":
        return found
    return found | imports(path)


def imports(path: Path) -> set[str]:
    """Every scripts/*.py this file actually imports, from the syntax tree.

    C03-F02. Split out from `references` because the two answer different
    questions and the gate now needs them apart. An import is a fact about what
    the interpreter will load. A filename appearing in text is a fact about the
    text, and Alex Zamurko, 2 October: "A textual filename reference does not
    establish that the referenced file is part of the reviewed object."

    So this one, and only this one, is allowed to refuse a covered set for
    omitting something. The textual scan stays, recorded for audit, binding
    nothing.
    """
    found: set[str] = set()
    if path.suffix != ".py":
        return found
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(f"scripts/{alias.name.split('.')[0]}.py")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # from . import x  /  from .x import y
                for alias in node.names:
                    found.add(f"scripts/{alias.name}.py")
                if node.module:
                    found.add(f"scripts/{node.module.split('.')[0]}.py")
            elif node.module:
                found.add(f"scripts/{node.module.split('.')[0]}.py")
    return found


def closure(root: Path) -> dict[str, list[str]]:
    """Every scripts/*.py a covered component can reach, and who reaches it.

    Alex Zamurko, 9 September 2026:

        If validate_cycle.py or run_review.py imports repository-local modules
        whose changes can alter their behaviour, pinning only the two top-level
        files is insufficient. Either include those executable dependencies in
        the bootstrap decision hash set, or establish that the two files are
        behaviorally self-contained.

    They are not self-contained. run_review.py loads bootstrap_gate.py by path
    and invokes validate_cycle.py as a subprocess; loop_state.py invokes
    validate_cycle.py too. Editing a dependency changes a reviewed component's
    behaviour without changing its bytes, so a hash set of top-level files only
    is a hash set with a hole in it.

    Derived by walking references rather than listed by hand, because a
    hand-maintained dependency list is one that is right on the day it is written
    and silently wrong afterwards, which is the failure this whole gate exists to
    prevent one level down.

    Deliberately over-inclusive: a scripts/*.py named anywhere in a covered file,
    including in a usage line in its docstring, is treated as a dependency. The
    cost of over-inclusion is that an unrelated edit forces a re-review. The cost
    of under-inclusion is a component whose behaviour changed while its approval
    still verified. Those are not comparable, so the ambiguity resolves toward
    covering more.
    """
    # C03-F02. Still walked, still recorded, and no longer load-bearing. What
    # this returns is an observation about text, kept in the decision so a
    # reader can see what the components mention, and used by nothing to decide
    # what is covered.
    declared = sorted(set(read_manifest(root)["components"]) | set(ALWAYS))
    reached: dict[str, list[str]] = {}
    pending = list(declared)
    seen: set[str] = set()

    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            continue
        for dep in sorted(references(p)):
            if dep == rel or not (root / dep).is_file():
                continue
            reached.setdefault(dep, []).append(rel)
            if dep not in seen:
                pending.append(dep)

    # Declared components are not "reached"; they are declared. Keeping the two
    # kinds separate was always the point of this, and it matters more now that
    # only one of them means anything.
    for rel in declared:
        reached.pop(rel, None)
    return reached


def read_manifest(root: Path) -> dict:
    """The canonical covered-component manifest, replayed against its history.

    C03-F02. Four things are checked here, and each is one of the failures the
    ruling names.

    The schema, so a file of some other shape is refused rather than read
    hopefully. The history, replayed from nothing through every recorded
    addition and removal, which must end at the component list the file
    declares: that is what makes a quiet edit fail, because an edit that does
    not also write its own authorisation leaves the two disagreeing. The
    version, which must match the last history entry, so a bump without a change
    and a change without a bump are both refused. And an authorisation on every
    entry, because "explicit, recorded" means somebody's name is on it.
    """
    p = root / COVERED_MANIFEST
    if not p.is_file():
        raise Refused(
            f"the covered-component manifest is missing: {COVERED_MANIFEST}\n"
            "  There is no fallback list. A gate that invents a scope when the "
            "declaration is\n  gone is a gate deciding what it is approving.")
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"{COVERED_MANIFEST} is not valid JSON: {e}")

    if m.get("schema") != MANIFEST_SCHEMA:
        raise Refused(
            f"{COVERED_MANIFEST} declares schema {m.get('schema')!r}, "
            f"expected {MANIFEST_SCHEMA!r}")

    comps = m.get("components")
    if not isinstance(comps, list) or not comps:
        raise Refused(f"{COVERED_MANIFEST} declares no components")

    hist = m.get("history")
    if not isinstance(hist, list) or not hist:
        raise Refused(
            f"{COVERED_MANIFEST} carries no history, so its component list "
            "rests on nothing.\n  Every scope change has to be recorded where "
            "the scope is declared.")

    replayed: list[str] = []
    for i, e in enumerate(hist, 1):
        if not isinstance(e, dict):
            raise Refused(f"{COVERED_MANIFEST}: history entry {i} is not an "
                          f"object")
        if not str(e.get("authorized_by", "")).strip():
            raise Refused(
                f"{COVERED_MANIFEST}: history entry {i} names nobody who "
                "authorised it.\n  A scope change with no author is a scope "
                "change nobody made.")
        if not str(e.get("reason", "")).strip():
            raise Refused(
                f"{COVERED_MANIFEST}: history entry {i} gives no reason")
        if e.get("version") != i:
            raise Refused(
                f"{COVERED_MANIFEST}: history entry {i} declares version "
                f"{e.get('version')!r}. Versions run from 1 with no gaps, or "
                f"the record\n  cannot say which change produced which scope.")
        for rel in e.get("removed") or []:
            if rel not in replayed:
                raise Refused(
                    f"{COVERED_MANIFEST}: version {i} removes {rel!r}, which "
                    f"the scope did not contain")
            replayed.remove(rel)
        for rel in e.get("added") or []:
            if rel in replayed:
                raise Refused(
                    f"{COVERED_MANIFEST}: version {i} adds {rel!r}, which the "
                    f"scope already contained")
            replayed.append(rel)

    if m.get("version") != len(hist):
        raise Refused(
            f"{COVERED_MANIFEST} declares version {m.get('version')!r} but "
            f"records {len(hist)} change(s).\n  A bump with no change, or a "
            "change with no bump, and either way the version stops\n  "
            "identifying the scope.")

    if sorted(replayed) != sorted(comps):
        raise Refused(
            f"{COVERED_MANIFEST}: the component list is not what its own "
            "history produces.\n"
            f"  declared  {sorted(comps)}\n"
            f"  replayed  {sorted(replayed)}\n"
            "  The list was edited without the account of it being updated to "
            "match.\n  This is an internal consistency check and not proof of "
            "anything: an edit that\n  changed both would pass it. The "
            "authorisation evidence is the repository\n  record, checked "
            "separately by manifest_provenance.")

    if COVERED_MANIFEST not in comps:
        raise Refused(
            f"{COVERED_MANIFEST} does not cover itself.\n  A scope declaration "
            "outside the scope it declares can be rewritten without\n  "
            "invalidating any approval, which makes every approval it supports "
            "conditional\n  on nobody having done so.")
    return m


def manifest_digest(root: Path) -> str:
    return sha256_file(root / COVERED_MANIFEST)


def manifest_provenance(root: Path) -> dict:
    """Where the current manifest came from, according to the repository.

    C03-F02. I proposed the manifest's own change history as the record of who
    authorised a scope change, and Alex Zamurko, 2 October, refused it:

        That history should not be the sole proof of authorisation because it
        is stored inside the same mutable file. Otherwise, a scope change could
        also rewrite its own history... The manifest's internal change history
        is descriptive. The repository/workflow record is the independent
        evidence that the scope change was actually authorised.

    Which is correct, and is the same defect as a check that passes for a reason
    other than the one it is named for: an edit that rewrites the list and the
    account of the list in one action leaves the two agreeing and says nothing.

    So the evidence the gate uses is outside the file. A scope change has to
    exist as a commit, and the commit that introduced the manifest's current
    bytes is recorded with the decision. That is not a signature and it is not
    claimed to be one: under MC1_ENFORCEMENT: CONVENTION_ONLY a history rewrite
    still reaches it. It is the difference between an act the repository saw and
    an edit somebody made before running the gate, which is the difference the
    ruling asks for.
    """
    def git(*args: str) -> tuple[int, str]:
        try:
            r = subprocess.run(["git", "-C", str(root), *args],
                               capture_output=True, text=True)
            return r.returncode, r.stdout.strip()
        except FileNotFoundError:
            return 127, ""

    def committed(rel: str) -> bytes:
        """The bytes HEAD holds for this path, or a refusal.

        C03-F02, raised again by cycle 04. The previous version asked `git
        status --porcelain` whether a file had uncommitted changes and treated
        silence as "committed". Cycle 04: "an ignored, untracked approval file
        can satisfy authority.require_approval while producing empty ordinary
        porcelain status output." Silence from that command means no DIFFERENCE
        was reported, which is also what it says about a file git has never
        heard of.

        So the committed content is fetched and compared instead. There is no
        answer this can give that means "I did not look".
        """
        try:
            r = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{rel}"],
                               capture_output=True)
        except FileNotFoundError:
            raise Refused(
                f"git is not available, so whether {rel} is in the repository "
                "record\n  cannot be established. A provenance question that "
                "cannot be answered is not\n  an answer of yes.")
        if r.returncode != 0:
            raise Refused(
                f"{rel} is not in the repository record at HEAD.\n"
                "  A scope change that exists only on disk has no independent "
                "evidence that\n  anyone made it. Commit it, so that what the "
                "review is approved against is\n  something the repository saw "
                "rather than something it was shown once.\n\n  git said: "
                + (r.stderr.decode("utf-8", "replace").strip() or "(nothing)"))
        return r.stdout

    # The same comparison for the manifest. It had the stronger check of the two
    # and still rested on a status query; fetching the bytes says what the
    # record actually holds rather than what differs from it.
    _live = (root / COVERED_MANIFEST).read_bytes()
    if committed(COVERED_MANIFEST) != _live:
        raise Refused(
            f"{COVERED_MANIFEST} differs from the version in the repository "
            "record.\n  The scope on disk is not the scope anyone committed, so "
            "there is no evidence\n  the change was made rather than merely "
            "typed.")

    rc, commit = git("log", "-1", "--format=%H", "--", COVERED_MANIFEST)
    if rc != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise Refused(
            f"{COVERED_MANIFEST} has no commit in the repository's history, so "
            "there is no\n  record of the scope it declares having been "
            "introduced by anyone.")
    digest = manifest_digest(root)
    version = read_manifest(root)["version"]

    # C03-F02, Alex Zamurko's third correction on this one, 2 October:
    #
    #     One gap remains: a repository commit proves a scope change was
    #     recorded, not that it was authorised... A valid scope change requires
    #     both: provenance, the changed manifest exists in a repository commit;
    #     and authorisation, human approval recorded independently of the
    #     manifest.
    #
    # Each correction removed a thing standing in for the one next to it: first
    # two lists standing in for one, then a file's own account of itself
    # standing in for evidence, then a commit standing in for consent. The same
    # shape three times.
    #
    # Deterministic path per version, so the approval is referenced rather than
    # searched for, and bound to the manifest's exact bytes, so an approval for
    # one scope cannot carry a later one.
    appr = root / SCOPE_APPROVAL_DIR / f"v{version}.json"
    try:
        rec = authority.require_approval(
            appr, "covered-scope-change",
            {"manifest_version": str(version), "manifest_sha256": digest})
    except authority.NotAuthorized as e:
        raise Refused(
            f"the covered-component scope is not authorised.\n\n{e}")

    # C03-F02, raised again by cycle 04, and the worse half of it. This read
    # `rc == 0 and appr_dirty.strip()`, so a failed query made the condition
    # false and execution continued. Cycle 04: "Failure to establish approval
    # provenance is treated as permission." That is the defect class this entire
    # run has been removing, in the code I wrote three days ago to remove it.
    #
    # `committed` refuses rather than returning, so there is no path from "could
    # not check" to "carry on".
    _appr_rel = f"{SCOPE_APPROVAL_DIR}/v{version}.json"
    if committed(_appr_rel) != appr.read_bytes():
        raise Refused(
            f"{_appr_rel} differs from the version in the repository record.\n"
            "  The approval being consumed is not the approval anyone "
            "committed. An approval\n  that exists only on disk can be written, "
            "used, and removed with nothing left\n  behind, which is the whole "
            "of what it was supposed to prevent.")

    return {"path": COVERED_MANIFEST,
            "sha256": digest,
            "version": version,
            "introduced_by_commit": commit,
            "authorized_by": rec.get("authorized_by", ""),
            "authorization_record": f"{SCOPE_APPROVAL_DIR}/v{version}.json",
            "authorization_sha256": sha256_file(appr)}


def undeclared_imports(root: Path) -> dict[str, list[str]]:
    """Modules a declared component imports that the declaration does not name.

    C03-F02. Removing the automatic expansion leaves a real hazard: a component
    can import a module nobody declared, and editing that module changes the
    component's behaviour without changing its bytes. That was the thing the
    closure existed to prevent, and Alex Zamurko's ruling removes the mechanism
    rather than the hazard.

    So it is caught here instead, and refused rather than absorbed. The
    difference matters: absorbing it widens the reviewed object silently, which
    is the defect. Refusing says a component imports something nobody decided
    about, and leaves the deciding to a person.

    Imports only. A filename in a comment is not a dependency.
    """
    declared = set(read_manifest(root)["components"]) | set(ALWAYS)
    out: dict[str, list[str]] = {}
    for rel in sorted(declared):
        p = root / rel
        if not p.is_file() or p.suffix != ".py":
            continue
        for dep in sorted(imports(p)):
            if dep == rel or dep in declared or not (root / dep).is_file():
                continue
            out.setdefault(dep, []).append(rel)
    return out


def covered(root: Path) -> dict[str, str]:
    """Every path the decision pins: the declared components and this file.

    C03-F02. This used to add the executable closure of the declared set, which
    is how ten files became seventeen, four of them control suites and one named
    only inside a comment. Nothing is derived now.
    """
    missed = undeclared_imports(root)
    if missed:
        raise Refused(
            "these modules are imported by a covered component and are not "
            "declared:\n    "
            + "\n    ".join(f"{dep}  imported by {', '.join(by)}"
                            for dep, by in sorted(missed.items())) +
            f"\n\n  Editing one of them changes a reviewed component's "
            f"behaviour without changing\n  its bytes. Add it to "
            f"{COVERED_MANIFEST} if it is part of the implementation\n  under "
            f"review, with an authorisation recorded for the new version, or "
            f"stop\n  importing it. The gate will not decide that for you by "
            f"widening the reviewed\n  object on its own.")

    out: dict[str, str] = {}
    for rel in sorted(set(read_manifest(root)["components"]) | set(ALWAYS)):
        p = root / rel
        if not p.is_file():
            raise Refused(f"component under bootstrap review is missing: {rel}")
        out[rel] = sha256_file(p)
    return out


def component_hashes(root: Path) -> dict[str, str]:
    return covered(root)


def target_artifacts(target_json: Path) -> dict[str, str]:
    """The path→sha256 map the review target froze, from its plan_files."""
    if not target_json.is_file():
        raise Refused(f"review target not found: {target_json}")
    try:
        t = json.loads(target_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"review target is not valid JSON: {e}")
    entries = t.get("plan_files") or []
    if not entries:
        raise Refused(f"{target_json} lists no plan_files, so there is nothing "
                      "to bind the decision to")
    return {e["path"]: e["sha256"] for e in entries
            if isinstance(e, dict) and "path" in e and "sha256" in e}


def target_drift(root: Path, target_json: Path) -> list[str]:
    """Where the covered set and the reviewed target disagree.

    Three ways they can, and each means the decision would be about something
    other than what was reviewed:

      - a covered file was edited after the freeze;
      - a covered file was never in the target, so nobody reviewed it;
      - the target carried an artifact the gate does not cover, so approving it
        commits to nothing.
    """
    frozen = target_artifacts(target_json)
    now = covered(root)
    out: list[str] = []

    for rel, digest in sorted(now.items()):
        if rel not in frozen:
            out.append(f"{rel} is covered but was not in the review target, so "
                       "no reviewer saw it")
        elif frozen[rel] != digest:
            out.append(f"{rel} changed after the freeze\n"
                       f"      reviewed  {frozen[rel]}\n"
                       f"      on disk   {digest}")

    for rel in sorted(set(frozen) - set(now)):
        out.append(f"{rel} was reviewed but is not in the covered set, so "
                   "approving it would bind nothing")
    return out


# ------------------------------------------------------------------ check

# -------------------------------------------------- the exception's end

def runner_approvals_on_disk(root: Path) -> list[Path]:
    d = root / RUNNER_APPROVAL_DIR
    return sorted(d.glob("*.json")) if d.is_dir() else []


def runner_approvals_in_history(root: Path) -> tuple[list[str], str | None]:
    """Runner approvals git has ever seen added, whether or not they exist now.

    This is what makes the termination one-way, and it is the part that took a
    second look. A gate that decides by listing a directory can be reopened by
    deleting the directory: the exception would end and then quietly resume, and
    nothing in the tree would show it had ever ended. "Bootstrap" becoming an
    indefinite exemption is the exact failure ruling 2 exists to prevent, and
    deletion is the easiest route to it.

    Git history is the cheapest available record that a delete does not reach. It
    is not tamper-proof; a history rewrite defeats it. But a rewrite is a loud,
    deliberate act that leaves the reflog and every clone disagreeing, where
    deleting a file is neither.

    The asymmetry that makes this sound under MC1_ENFORCEMENT: CONVENTION_ONLY is
    worth stating. Nothing stops the implementing agent from WRITING an approval,
    but writing one only ever makes the rules stricter: it ends its own
    exemption and subjects every later runner to review by a prior approved one.
    The direction that would benefit the implementing agent is removing one, and
    that is the direction this closes.

    B02-F08. This returned [] when git failed, which is the same value it
    returns for a successful search that found nothing. So "no approval has ever
    been recorded" and "I could not find out" were indistinguishable, and the
    second one read as the first. Codex injected exit 128 and the exception came
    back available.

    That is the one-way termination failing open at exactly the point it is
    supposed to be hardest: an unreadable history is not evidence of absence,
    and the whole mechanism rests on history being readable. So the error
    travels back with the result and the caller decides, rather than being
    handed an empty list and no way to tell what it means.
    """
    r = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--diff-filter=A",
         "--format=%H", "--name-only", "--", f"{RUNNER_APPROVAL_DIR}/"],
        capture_output=True, text=True)
    if r.returncode != 0:
        detail = (r.stderr.strip().splitlines() or ["(no reason given)"])[0]
        return [], f"git log exited {r.returncode}: {detail}"
    return sorted({l.strip() for l in r.stdout.splitlines()
                   if l.strip().startswith(f"{RUNNER_APPROVAL_DIR}/")
                   and l.strip().endswith(".json")}), None


def bootstrap_exception_available(root: Path) -> tuple[bool, list[str]]:
    """(available, reasons). Ruling 2's termination point, asked as a question.

    Available means no runner has been approved yet, so there is still no prior
    approved runner that could serve as ACTIVE_REVIEW_RUNNER, and development
    evidence is the only kind obtainable. That is ruling 1's reasoning for
    cycle 02 and it stops being true the moment the first approval exists.
    """
    live = runner_approvals_on_disk(root)
    historic, hist_error = runner_approvals_in_history(root)

    # B02-F08. Checked before the historic list is consulted, because an empty
    # list from a failed query looks exactly like an empty list from a clean
    # one. Deletion resistance rests entirely on that query; if it cannot run,
    # the mechanism is not operating and saying "available" would be reporting
    # its own blindness as a clean bill of health.
    #
    # Fails closed. Refusing the exception when the check cannot run costs a
    # development run that has to be explained; granting it when the check
    # cannot run costs the termination that ruling 2 exists to make one-way.
    if hist_error:
        return False, [
            "whether a runner has ever been approved cannot be determined:",
            f"    {hist_error}",
            "  The bootstrap exception ends at the first approval, and that is "
            "established from",
            "  git history. An unreadable history is not evidence that no "
            "approval exists, so the",
            "  exception is not available while this check cannot run.",
            "  Repair the repository, or record the decision out of band and "
            "say so.",
        ]

    if live:
        return False, [
            "the bootstrap exception ended when the first runner was approved:",
            *[f"    {p.relative_to(root).as_posix()}" for p in live],
            "  From that approval onward every candidate runner is reviewed by "
            "the prior",
            "  approved one. There is no route back to the exception; it covered "
            "the period",
            "  before any approved runner existed, and that period is over.",
        ]

    if historic:
        return False, [
            "a runner approval was recorded and is no longer on disk:",
            *[f"    {h}" for h in historic],
            "  git history has it even though the working tree does not, so the "
            "exception is",
            "  still over. Ruling 2 ends it at the first approval, not at the "
            "most recent",
            "  surviving copy of the file.",
            "  Restore the approval record, or explain the deletion in a commit. "
            "A gate that",
            "  could be reopened by deleting a file would be a convention, not a "
            "termination.",
        ]

    return True, [
        "no runner has been approved yet, so the bootstrap exception is still "
        "available.",
        "  There is no prior approved runner to act as ACTIVE_REVIEW_RUNNER, "
        "which is the",
        "  condition the exception exists to cover. It ends at the first "
        "approval.",
    ]


def evaluate(root: Path) -> tuple[bool, list[str]]:
    """(ok, reasons). Never raises; the reasons are the useful output."""
    rec = root / "bootstrap-review" / "decision.json"
    if not rec.is_file():
        # C03-F02. Read from the manifest, and say so if it cannot be read: a
        # listing printed from a constant would be this function's own account
        # of the scope rather than the declared one. `evaluate` never raises, so
        # the failure becomes a line in the reasons like everything else.
        try:
            _declared = sorted(set(read_manifest(root)["components"])
                               | set(ALWAYS))
        except Refused as e:
            _declared = [f"(the covered-component manifest cannot be read: {e})"]
        return False, [
            "no bootstrap review on record.",
            "  These components have not been independently reviewed, and they",
            "  cannot go through the process they enable:",
            *[f"    {c}" for c in _declared],
            "  Ruled mandatory 8 September 2026, widened to the finding ledger",
            "  and loop controller on 9 September because they determine the",
            "  authoritative meaning of otherwise valid review evidence.",
            f"  Expected: {rec.relative_to(root).as_posix()}",
        ]

    try:
        d = json.loads(rec.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"the bootstrap decision record is not valid JSON: {e}"]

    reasons: list[str] = []

    decision = d.get("decision")
    if decision != "APPROVE":
        reasons.append(f"the bootstrap review decision is {decision!r}, not APPROVE.")
        if decision in ("RETURN_FOR_REWORK", "REJECT"):
            reasons.append("  Repair the components, rerun the review, record a "
                           "new decision.")

    # B01-F09, the half cycle 02 found still open. This checked the decision and
    # the component hashes and stopped, so the evidence the decision rests on
    # was recorded and then never looked at again. Codex: "After recording
    # approval in a fixture, deleting all four bootstrap evidence files left
    # evaluate returning (True, [])."
    #
    # Alex Zamurko, 10 September: "bind each approval to the exact review
    # evidence and hashes it depends on, and recheck that evidence whenever the
    # approval is used. Why it works: an approval remains valid only while the
    # evidence it was based on still exists unchanged."
    #
    # An approval is a statement about a review. If the review is gone, the
    # statement has no subject, and "a decision was recorded once" is not the
    # same claim as "this decision is about evidence you can still read".
    recorded_evidence = d.get("evidence") or {}
    if not recorded_evidence:
        reasons.append(
            "the decision record pins no review evidence, so nothing ties it to "
            "the review it\n    was made about. Re-record it.")
    for name, want in sorted(recorded_evidence.items()):
        p = root / "bootstrap-review" / name
        if not p.is_file():
            reasons.append(
                f"the review evidence this approval rests on is gone: {name}\n"
                "    The decision stands on a review nobody can now read.")
        elif sha256_file(p) != want:
            reasons.append(
                f"{name} has changed since the decision was recorded.\n"
                f"    recorded  {want}\n"
                f"    on disk   {sha256_file(p)}\n"
                "    The approval covers the review that was actually "
                "conducted, not a later edit\n    of it.")

    # The frozen target the review was run against, checked the same way. B01-F09
    # required the decision to be bound to what was reviewed; recording that
    # binding and never verifying it is the binding existing only on paper.
    rt = d.get("reviewed_target") or {}
    if rt.get("path") and rt.get("sha256"):
        tp = root / rt["path"]
        if not tp.is_file():
            reasons.append(f"the reviewed target is gone: {rt['path']}")
        elif sha256_file(tp) != rt["sha256"]:
            reasons.append(
                f"the reviewed target has changed since the decision: "
                f"{rt['path']}\n"
                f"    recorded  {rt['sha256']}\n"
                f"    on disk   {sha256_file(tp)}")
    else:
        reasons.append(
            "the decision record names no reviewed target, so it is not bound "
            "to the artifacts\n    a reviewer actually saw. This is B01-F09; "
            "re-record with --target.")

    pinned = d.get("components") or {}

    # Required now, which may be more than was required when the decision was
    # written: the root list was widened on 9 September, and the dependency
    # closure changes whenever a covered file starts referencing another. A
    # decision that predates either is not a decision about the current system.
    try:
        required = set(covered(root))
    except Refused as e:
        return False, [str(e)]

    absent = sorted(required - set(pinned))
    if absent:
        reasons.append(
            "the review does not cover every component it must: "
            + ", ".join(absent) +
            "\n    Either the covered set was widened after this decision, or a "
            "reviewed file\n    now reaches code the decision never pinned. "
            "Re-review.")

    for rel, recorded in sorted(pinned.items()):
        p = root / rel
        if not p.is_file():
            reasons.append(f"{rel} was reviewed but no longer exists")
            continue
        actual = sha256_file(p)
        if actual != recorded:
            reasons.append(
                f"{rel} has changed since it was reviewed.\n"
                f"    reviewed  {recorded}\n"
                f"    on disk   {actual}\n"
                "    The approval covers the reviewed bytes, not the filename. "
                "Re-review or revert.")

    return (not reasons), reasons


def cmd_check(root: Path = REPO, quiet: bool = False) -> int:
    ok, reasons = evaluate(root)
    if ok:
        d = json.loads((root / "bootstrap-review" / "decision.json")
                       .read_text(encoding="utf-8"))
        if not quiet:
            # C03-F02. Printed from the decision rather than from the current
            # manifest, because this is a report about what was approved. If
            # the scope has moved since, the drift check above has already
            # refused and this line is not reached.
            scope = d.get("covered_scope", {})
            print("BOOTSTRAP_REVIEW: APPROVED")
            print(f"  decided by  {d.get('decided_by', '?')}")
            print(f"  decided at  {d.get('decided_at', '?')}")
            if scope:
                print(f"  scope       {scope.get('path')} v"
                      f"{scope.get('version')}  "
                      f"{str(scope.get('sha256', ''))[:16]}…")
                print(f"  authorised  {scope.get('authorized_by', '?')}  "
                      f"in {str(scope.get('introduced_by_commit', ''))[:12]}")
            for rel in sorted(d.get("components", {})):
                print(f"  covers      {rel}  {d['components'][rel][:16]}…")
            # Recorded, binding nothing. Alex Zamurko, 2 October: filename
            # references "must not expand the review scope automatically".
            for rel in sorted(closure(root)):
                via = ", ".join(Path(v).name for v in closure(root)[rel])
                print(f"  mentions    {rel}  via {via}")
        return 0
    if not quiet:
        print("BOOTSTRAP_REVIEW: NOT SATISFIED")
        for r in reasons:
            print(f"  {r}")
        print()
        print("No real protocol cycle may run until this passes.")
    return 1


# ------------------------------------------------------------------ record

def cmd_record(a: argparse.Namespace) -> int:
    if a.decision not in DECISIONS:
        raise Refused(f"decision must be one of {', '.join(DECISIONS)}")
    if not a.decided_by.strip():
        raise Refused("--decided-by is required; a human gate with no human "
                      "named is not a human gate")
    # The decision is made in Slack and recorded here by someone else, so the
    # record has to point back at where it was actually made. Without this the
    # operator can write any name into --decided-by and nothing distinguishes a
    # relayed approval from an invented one. Same distinction as everywhere else
    # in this repository: recorded, or merely asserted.
    if len(a.note.strip()) < 20:
        raise Refused(
            "--note is required, and must attribute the decision.\n"
            "  Give where it was made and what was said: channel, timestamp, and "
            "the words.\n"
            "  Example:\n"
            '    --note "#gap, 9 Sep 2026 12:03 AM, Alex Zamurko: \'Confirmed '
            "...'\"\n"
            "  --decided-by alone is a name typed by whoever ran this command.")

    # B01-F09. The decision must be about the artifacts that were reviewed, not
    # about whatever is on disk when someone gets round to recording it.
    #
    # Codex: "Recording a decision checks only that four evidence files are
    # nonempty, then hashes the current component files. It never compares those
    # files with the frozen review target."
    #
    # So: approve, edit a component, record — and the approval covered code the
    # reviewer never saw, under evidence describing code that no longer exists.
    # `check` would then verify the decision against itself and pass forever.
    # C03-F02. Before the drift comparison, because an unauthorised or
    # uncommitted scope is a different fact and the reader needs the one that
    # names the cause. Checked first, a manifest edited and not committed says
    # so; checked second, it arrives as "the components have changed", which is
    # true, unhelpful, and points at the wrong file.
    manifest_provenance(REPO)

    if a.target:
        drift = target_drift(REPO, Path(a.target).resolve())
        if drift:
            raise Refused(
                "the components have changed since the review target was "
                "frozen:\n  " + "\n  ".join(drift) +
                "\n\n  A decision recorded now would approve bytes the reviewer "
                "never saw.\n  Revert the drift, or re-freeze and re-review.")
    else:
        raise Refused(
            "--target is required: the frozen target.json the review was run "
            "against.\n"
            "  The decision has to be bound to what was reviewed. Without it "
            "this records\n  an approval of whatever happens to be on disk now, "
            "which is B01-F09.\n"
            "  Example:\n"
            "    --target runs/BOOTSTRAP-001/plan-review/cycle-01/target.json")

    absent = []
    for name in EVIDENCE:
        p = REVIEW_DIR / name
        if not p.is_file():
            absent.append(f"{name} (missing)")
        elif p.stat().st_size == 0:
            absent.append(f"{name} (empty)")
    if absent:
        raise Refused(
            "the bootstrap review evidence is incomplete, so there is nothing to "
            "decide about:\n  " + "\n  ".join(absent) +
            f"\n  Expected under {REVIEW_DIR.relative_to(REPO).as_posix()}/\n"
            "  The ruling requires the exact input, the raw Codex output, the "
            "findings and\n  the responses to be preserved alongside the decision.")

    # C02-F07. The block above checks those four files exist and are non-empty,
    # and stops there. The block before it checks today's components match the
    # supplied target. Both are true of a pairing that has nothing to do with
    # itself: stale evidence for target A sitting beside a --target naming B
    # whose components happen to match the current tree. The decision then
    # records both, hashes both, and `check` verifies those hashes forever
    # without either of them ever being about the other.
    #
    # Codex, cycle 02: "Checking that component files match a target and that
    # review files exist is not checking that the review was of that target."
    #
    # The binding already exists one layer down. MC-2 check 10 requires a
    # cycle's codex-input.md to carry its target's digest verbatim, which is how
    # a reviewer's input is tied to the artifact it describes. The same rule read
    # the same way closes this, so nothing new is invented. It establishes only
    # that the input the reviewer was handed names this target; it claims
    # nothing about authorship, and nothing about whether the reviewer read it.
    _target = Path(a.target).resolve()
    _tdigest = sha256_file(_target)
    _input = (REVIEW_DIR / "codex-input.md").read_text(encoding="utf-8",
                                                       errors="replace")
    if _tdigest not in _input:
        raise Refused(
            "the review evidence does not name the target being decided "
            "about.\n"
            f"  target       {_target}\n"
            f"  its digest   {_tdigest}\n"
            f"  bootstrap-review/codex-input.md does not contain that digest.\n"
            "\n  Four evidence files existing, and today's components matching "
            "a target, are\n  two separate facts. Neither says the reviewer saw "
            "this target. Without that\n  link a decision can approve bytes "
            "reviewed under different evidence, which is\n  B01-F09 arriving "
            "through the other side of the same command.")

    if RECORD.exists():
        prior = json.loads(RECORD.read_text(encoding="utf-8"))
        if not a.supersede:
            raise Refused(
                f"a bootstrap decision already exists: {prior.get('decision')} "
                f"by {prior.get('decided_by')} at {prior.get('decided_at')}.\n"
                "  It is one-time by design. Pass --supersede to replace it, "
                "which preserves\n  the prior decision in the record rather than "
                "overwriting it silently.")

    record = {
        "decision": a.decision,
        "decided_by": a.decided_by.strip(),
        "decided_at": now(),
        "note": a.note,
        "components": component_hashes(REPO),
        "reviewed_target": {
            "path": Path(a.target).resolve().relative_to(REPO).as_posix(),
            "sha256": sha256_file(Path(a.target).resolve()),
        },
        # C03-F02. These two fields described a scope that was partly declared
        # and partly derived, which is the arrangement the ruling of 2 October
        # removed. The decision now records which manifest it was issued
        # against, by version, hash, the commit that introduced it and the
        # approval that authorised it, so a reader can ask what was approved
        # and get an answer from outside this file.
        #
        # `references` is still recorded, and binds nothing. Alex Zamurko:
        # "Filename references inside those components may be recorded or
        # validated where needed, but they must not expand the review scope
        # automatically."
        "covered_scope": manifest_provenance(REPO),
        "references_observed": {k: v for k, v in sorted(closure(REPO).items())},
        "evidence": {n: sha256_file(REVIEW_DIR / n) for n in EVIDENCE},
        "authority": "Alex Zamurko, 8 September 2026: a one-time BOOTSTRAP_REVIEW "
                     "is mandatory before relying on these components for real "
                     "protocol cycles.",
    }
    if RECORD.exists():
        record["supersedes"] = json.loads(RECORD.read_text(encoding="utf-8"))

    write_lf(RECORD, json.dumps(record, indent=2) + "\n")
    print(f"recorded {RECORD.relative_to(REPO).as_posix()}")
    print(f"  decision   {a.decision}")
    print(f"  decided by {record['decided_by']}")
    for rel, h in record["components"].items():
        print(f"  covers     {rel}  {h[:16]}…")
    if a.decision != "APPROVE":
        print()
        print("Real protocol cycles remain blocked until an APPROVE is recorded.")
    return 0


# ------------------------------------------------------- approve a runner

def cmd_approve_runner(a: argparse.Namespace) -> int:
    """Record the first human approval of a runner, which ends the exception.

    Ruling 2: "The first approved runner creates the missing first link in the
    chain; from that point onward, every candidate runner can and should be
    reviewed by the prior approved runner."

    Deliberately a separate command from `record`. The bootstrap decision
    approves the components as reviewed; this approves a specific runner to act
    as ACTIVE_REVIEW_RUNNER for the next candidate, and it is the event that ends
    the exemption. Folding them together would make ending the exception a side
    effect of approving code, and the two are different decisions taken at
    different moments.
    """
    if not a.decided_by.strip():
        raise Refused("--decided-by is required; the approval that ends the "
                      "exception cannot be anonymous")
    if len(a.note.strip()) < 20:
        raise Refused(
            "--note is required, and must attribute the decision.\n"
            "  Give where it was made and what was said: channel, timestamp, and "
            "the words.\n"
            "  This approval ends the bootstrap exception permanently, so the "
            "record has to\n  say who ended it and on what basis.")

    runner = Path(a.runner).resolve()
    if not runner.is_file():
        raise Refused(f"runner not found: {a.runner}")
    if not a.review:
        raise Refused(
            "--review is required: the review that approved this runner.\n"
            "  A runner approved by nothing is the thing the chain exists to "
            "rule out.")
    review = Path(a.review).resolve()
    if not review.is_file():
        raise Refused(f"review evidence not found: {a.review}")

    ok, reasons = evaluate(REPO)
    if not ok:
        raise Refused(
            "the bootstrap review does not currently hold, so no runner can be "
            "approved on\nthe strength of it:\n  " + "\n  ".join(reasons))

    available, _ = bootstrap_exception_available(REPO)
    d = REPO / RUNNER_APPROVAL_DIR
    d.mkdir(parents=True, exist_ok=True)
    rel_runner = runner.relative_to(REPO).as_posix()
    digest = sha256_file(runner)
    out = d / f"{digest[:12]}.json"
    if out.exists():
        raise Refused(f"this exact runner is already approved: "
                      f"{out.relative_to(REPO).as_posix()}")

    record = {
        "schema": "runner-approval/1",
        "runner_path": rel_runner,
        "runner_sha256": digest,
        "approved_by": a.decided_by.strip(),
        "approved_at": now(),
        "note": a.note,
        "review_evidence": {
            "path": review.relative_to(REPO).as_posix(),
            "sha256": sha256_file(review),
        },
        "components": component_hashes(REPO),
        "ends_bootstrap_exception": bool(available),
        "authority": "Alex Zamurko, 9 September 2026: the bootstrap exception "
                     "ends immediately after the first human approval of a "
                     "runner.",
    }
    write_lf(out, json.dumps(record, indent=2) + "\n")

    # B02-F08, the half that was mine. This used to print "commit this file"
    # and stop, which left a window where the termination could be undone by
    # deleting an uncommitted record. Worse, test_bootstrap_gate asserted that
    # the window existed and called it correct, and the cycle-02 prompt then
    # described the arrangement as enforcement. Codex: "do not present the
    # latter bypass as successful enforcement."
    #
    # So the record is committed here, in the same action that writes it. The
    # durability of this boundary rests on git history, and a boundary that
    # depends on someone remembering a second step is a convention with extra
    # stages, not a termination.
    rel_out = out.relative_to(REPO).as_posix()
    add = subprocess.run(["git", "-C", str(REPO), "add", "--", rel_out],
                         capture_output=True, text=True)
    if add.returncode != 0:
        out.unlink(missing_ok=True)
        raise Refused(
            f"the approval could not be staged, so it was not written:\n  "
            f"{add.stderr.strip()}\n"
            "  This boundary is durable only once git has the record. Leaving "
            "the file behind\n  uncommitted would recreate the deletion bypass "
            "this closes.")
    # --only so that unrelated staged work is not swept into this commit.
    msg = (f"Runner approved: {rel_runner} ({digest[:12]}), by "
           f"{record['approved_by']}. Ends the bootstrap exception.")
    com = subprocess.run(
        ["git", "-C", str(REPO), "commit", "--only", "-m", msg, "--", rel_out],
        capture_output=True, text=True)
    if com.returncode != 0:
        out.unlink(missing_ok=True)
        subprocess.run(["git", "-C", str(REPO), "reset", "--", rel_out],
                       capture_output=True, text=True)
        raise Refused(
            f"the approval could not be committed, so it was not written:\n  "
            f"{(com.stderr or com.stdout).strip()}")

    print(f"recorded and committed {rel_out}")
    print(f"  runner      {rel_runner}  {digest[:16]}…")
    print(f"  approved by {record['approved_by']}")
    if available:
        print()
        print("The bootstrap exception ends here. --bootstrap-exempt will be "
              "refused from now on,")
        print("and every candidate runner is reviewed by the prior approved "
              "runner.")
        print()
        print("The record is in git history, so deleting the file does not "
              "reopen the exception.")
        print("A history rewrite still reaches it; that is a louder act and is "
              "the limit of what")
        print("MC1_ENFORCEMENT: CONVENTION_ONLY supports.")
    return 0


def cmd_exception(root: Path = REPO) -> int:
    available, why = bootstrap_exception_available(root)
    print("BOOTSTRAP_EXCEPTION: " + ("AVAILABLE" if available else "ENDED"))
    for line in why:
        print(f"  {line}")
    return 0


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="does an approved, still-current bootstrap "
                                 "review exist")

    r = sub.add_parser("record", help="record the human decision on the "
                                      "bootstrap review")
    r.add_argument("--decision", required=True, help=" | ".join(DECISIONS))
    r.add_argument("--decided-by", required=True)
    r.add_argument("--note", default="")
    r.add_argument("--target", default="",
                   help="the frozen target.json the review was run against. "
                        "Required: it is what binds the decision to the "
                        "artifacts a reviewer actually saw.")
    r.add_argument("--supersede", action="store_true",
                   help="replace an existing decision, preserving it in the record")

    sub.add_parser("exception", help="is the bootstrap exception still available")

    ar = sub.add_parser("approve-runner",
                        help="record the first human approval of a runner, which "
                             "ends the bootstrap exception")
    ar.add_argument("--runner", required=True,
                    help="the runner being approved, e.g. scripts/run_review.py")
    ar.add_argument("--decided-by", required=True)
    ar.add_argument("--note", default="")
    ar.add_argument("--review", default="",
                    help="the review evidence this approval rests on, e.g. a "
                         "cycle's codex-output-raw.md")

    a = ap.parse_args(argv[1:])
    try:
        if a.cmd == "check":
            return cmd_check()
        if a.cmd == "exception":
            return cmd_exception()
        if a.cmd == "approve-runner":
            return cmd_approve_runner(a)
        return cmd_record(a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
