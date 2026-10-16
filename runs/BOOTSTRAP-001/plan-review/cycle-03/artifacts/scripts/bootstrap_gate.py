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
import subprocess
import sys
from pathlib import Path

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
COMPONENTS = (
    "specs/evidence-schema-v1.0.md",
    "scripts/validate_cycle.py",
    "scripts/run_review.py",
    "scripts/ledger.py",
    "scripts/loop_state.py",
)

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
    reached: dict[str, list[str]] = {}
    pending = list(COMPONENTS) + list(ALWAYS)
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

    # Roots are covered because they were declared, not because something
    # reached them. Keep the two kinds separate in the record.
    for rel in list(COMPONENTS) + list(ALWAYS):
        reached.pop(rel, None)
    return reached


def covered(root: Path) -> dict[str, str]:
    """Every path the decision must pin: declared roots, this file, and the
    executable closure of both."""
    out: dict[str, str] = {}
    for rel in list(COMPONENTS) + list(ALWAYS) + sorted(closure(root)):
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


def runner_approvals_in_history(root: Path) -> list[str]:
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
    """
    r = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--diff-filter=A",
         "--format=%H", "--name-only", "--", f"{RUNNER_APPROVAL_DIR}/"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return sorted({l.strip() for l in r.stdout.splitlines()
                   if l.strip().startswith(f"{RUNNER_APPROVAL_DIR}/")
                   and l.strip().endswith(".json")})


def bootstrap_exception_available(root: Path) -> tuple[bool, list[str]]:
    """(available, reasons). Ruling 2's termination point, asked as a question.

    Available means no runner has been approved yet, so there is still no prior
    approved runner that could serve as ACTIVE_REVIEW_RUNNER, and development
    evidence is the only kind obtainable. That is ruling 1's reasoning for
    cycle 02 and it stops being true the moment the first approval exists.
    """
    live = runner_approvals_on_disk(root)
    historic = runner_approvals_in_history(root)

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
        return False, [
            "no bootstrap review on record.",
            "  These components have not been independently reviewed, and they",
            "  cannot go through the process they enable:",
            *[f"    {c}" for c in list(COMPONENTS) + list(ALWAYS)],
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
            deps = closure(root)
            print("BOOTSTRAP_REVIEW: APPROVED")
            print(f"  decided by  {d.get('decided_by', '?')}")
            print(f"  decided at  {d.get('decided_at', '?')}")
            for rel in list(COMPONENTS) + list(ALWAYS):
                print(f"  root        {rel}  {d['components'][rel][:16]}…")
            for rel in sorted(deps):
                via = ", ".join(Path(v).name for v in deps[rel])
                print(f"  dependency  {rel}  {d['components'][rel][:16]}…  "
                      f"via {via}")
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
        "roots": list(COMPONENTS) + list(ALWAYS),
        "dependencies": {k: v for k, v in sorted(closure(REPO).items())},
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
