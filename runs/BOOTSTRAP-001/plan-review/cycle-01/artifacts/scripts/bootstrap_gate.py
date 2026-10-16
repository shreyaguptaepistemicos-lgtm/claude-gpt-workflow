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
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO / "bootstrap-review"
RECORD = REVIEW_DIR / "decision.json"

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
COMPONENTS = (
    "scripts/validate_cycle.py",
    "scripts/run_review.py",
    "scripts/ledger.py",
    "scripts/loop_state.py",
)

# This file is always covered, whatever the roots are. It was not, and that was
# the sharpest form of the hole Alex found: bootstrap_gate.py did not hash
# itself, so editing `evaluate` to return (True, []) would have defeated every
# other pin while `check` still reported APPROVED. A gate that does not cover
# itself is an honour system with extra steps.
ALWAYS = ("scripts/bootstrap_gate.py",)

# Anything matching this that resolves to a file in scripts/ is treated as an
# executable dependency of the component that mentions it.
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
        for name in sorted(set(PY_REF.findall(p.read_text(encoding="utf-8")))):
            dep = f"scripts/{name}"
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


# ------------------------------------------------------------------ check

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
    r.add_argument("--supersede", action="store_true",
                   help="replace an existing decision, preserving it in the record")

    a = ap.parse_args(argv[1:])
    try:
        if a.cmd == "check":
            return cmd_check()
        return cmd_record(a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
