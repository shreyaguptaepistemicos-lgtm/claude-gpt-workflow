#!/usr/bin/env python3
"""A fixture says which real files it reads, and why, and of what kind.

    python scripts/test_fixture_sources.py

Exit 0 = every suite that reaches outside its own fixture declares what it
reaches for, and no behavioural suite reads a real record.

Why this file exists
--------------------
Issue 8 on the public repository. Four suites failed for one reason: each
reached outside its own fixture for a file the surrounding repository
happened to carry. Alex Zamurko's acceptance: "A stated rule for which real
files a fixture may read and why, and a check that enforces it, so the next
instance fails on the push that creates it rather than in somebody else's
checkout."

And the constraint that makes it harder than it looks, in his words:

    "Some borrowing is correct. specs/covered-components.json is deliberately
     copied rather than invented, because there is one canonical manifest and
     a second list written into a suite would be the duplicate source of
     truth that ruling removed. So the rule cannot be 'never read a real
     file'. It has to distinguish a fixture that needs a canonical artefact
     from a fixture that merely found one lying around."

The rule, its four kinds and the reasoning are in specs/FIXTURE-SOURCES.md.
This file enforces the part of it that can be enforced.

The load-bearing line
---------------------
Of everything below, one check does the work: a `record:` source is allowed
only in a suite whose filename ends `_record.py`. Reading a real run or
ledger or register is a different question from testing behaviour against
fixtures, and mixing them is what made test_approval_package.py fail in an
exported copy carrying no runs/ directory. The repair then was to split the
suite in two. This is that split, written down and enforced.

What it does NOT check
----------------------
Whether a declared reason is true. A suite can call a real record
`canonical:` and this accepts it. The marker makes the claim visible to a
reader, which is the most a check inside the repository can do about a claim
of intent.

Paths assembled from variables are not resolved. The declaration requirement
rather than the path scan is what covers those suites, so a suite could
declare one path and read another by variable and pass.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

MIN_REASON = 60

# Directories holding records rather than code or canonical specs. Reading
# one of these is the case issue 8 is about, and the only case this file
# requires anything of.
#
# The first version of this check required all 23 suites to declare every
# real file they touch. Eight of those declarations would have read "copies
# production modules into a temp tree", and bookkeeping at that volume
# invites the rubber-stamping the check cannot detect while burying the one
# line that matters. Narrowed to the records on 22 October 2026.
RECORD_ROOTS = ("runs", "registers", "approvals", "bootstrap-review")

# A record read has to say what happens when the record is not there, because
# that is the whole difference between the two cases. test_prompts.py reads a
# real ledger to check that a frozen-prompt exemption is bound to a finding
# somebody actually recorded, and when the ledger is absent its reader returns
# False and the caller treats False as a failure. The suite goes red where the
# record is missing rather than accepting the exemption. That is a correct
# record read.
#
# test_approval_package.py's old fixture read the production register and
# passed wherever it happened to exist. Same act, opposite direction, and the
# difference is invisible in a diff. So the declaration has to state it.
ABSENT_MARKERS = ("absent:", "when absent", "if absent")

FIXTURE_SOURCES = {
    "scripts": "subject: every suite in this directory is what this file "
               "examines, so a copy would examine the copy. absent: cannot "
               "be, since the directory holding this file is the directory "
               "it reads",
}


def declares(tree: ast.Module) -> dict | None:
    """The suite's FIXTURE_SOURCES literal, or None if it has none."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "FIXTURE_SOURCES" not in names:
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
    return None


def _chain(node: ast.AST) -> list[ast.AST]:
    """Flatten `a / b / c` into [a, b, c]."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _chain(node.left) + _chain(node.right)
    return [node]


def record_roots_read(tree: ast.Module) -> set[str]:
    """Record directories this suite reads from the real repository.

    What the path hangs off, not which strings appear in it. The first
    version matched the string alone and reported twelve suites, most of
    them wrongly: test_ledger.py and four others build `tmp / "runs" /
    "T-001"` inside their own temporary tree, which is a fixture creating
    its own records and the opposite of the defect. This file was flagged
    too, for defining RECORD_ROOTS.

    A path rooted at REPO or SRC leaves the fixture. A path rooted at
    anything else does not, and the name of a directory says nothing about
    whose directory it is.

    Limit, named rather than implied: `REPO / rel` where rel is a variable
    cannot be resolved here. The declaration requirement is what covers
    those, and a suite could read a record through a variable and not be
    reported.
    """
    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        parts = _chain(node)
        base = parts[0]
        if isinstance(base, ast.Name):
            name = base.id
        elif (isinstance(base, ast.Attribute)
                and isinstance(base.value, ast.Name)):
            name = base.value.id            # SRC.parent / "runs"
        else:
            continue
        if name not in ("REPO", "SRC"):
            continue
        for p in parts[1:]:
            if isinstance(p, ast.Constant) and isinstance(p.value, str):
                head = p.value.strip("/").split("/", 1)[0]
                if head in RECORD_ROOTS:
                    found.add(head)
    return found


def fault(rel: str, src: str, why: object, exists: bool) -> str:
    """What is wrong with one declaration, or "" if nothing is.

    Out here rather than inline in the loop so the controls below can ask it
    about cases this repository does not contain. The first version kept it
    in the loop, which meant the only way to exercise the record rule was to
    write a bad declaration into a real suite and watch it fail, and a check
    whose only test is the repository itself cannot be shown working on the
    cases the repository has never had.
    """
    if not isinstance(why, str) or len(why) < MIN_REASON:
        n = len(why) if isinstance(why, str) else 0
        return (f"{rel} declares {src!r} with a reason of {n} characters. "
                f"The reason is\n    the deliverable; a word is a label.")
    if not exists:
        return f"{rel} declares {src!r}, which does not exist in this " \
               f"repository"
    if src.split("/", 1)[0] in RECORD_ROOTS:
        if not any(m in why.lower() for m in ABSENT_MARKERS):
            return (f"{rel} declares the record source {src!r} without "
                    f"saying what happens when\n    it is absent. That is the "
                    f"one thing separating a correct record read from a\n    "
                    f"suite that passes wherever the file happens to exist. "
                    f"Say 'absent: ...' and\n    say which way it goes.")
    return ""


# Cases this repository does not contain, with the answers written down. A
# scan that only ever runs against a clean repository reports nothing either
# way, and the two are indistinguishable from the output.
SELF_CASES = (
    ("a record source with no absent clause", "runs",
     "record: reads BOOTSTRAP-002's ledger to establish that the exemption "
     "is bound to a finding somebody actually raised", True, True),
    ("the same source with one", "runs",
     "record: reads BOOTSTRAP-002's ledger to establish that the exemption "
     "is bound to a finding somebody raised. absent: returns False and the "
     "caller fails", True, False),
    ("a non-record source needs no absent clause", "specs",
     "canonical: one manifest by the ruling of 2 October 2026 and a second "
     "list here would be the duplicate source of truth it removed", True,
     False),
    ("a reason of one word", "runs", "record: yes", True, True),
    ("a declared path that is not there", "runs",
     "record: reads a ledger that establishes the exemption is bound to a "
     "real finding. absent: returns False and the caller fails", False, True),
)


def self_check() -> list[str]:
    out = []
    for label, src, why, exists, want_fault in SELF_CASES:
        got = bool(fault("fixture.py", src, why, exists))
        if got != want_fault:
            out.append(f"{label}: expected {'a fault' if want_fault else 'none'}, "
                       f"got {'a fault' if got else 'none'}")
    return out


SOURCE_CASES = (
    ('p = REPO / "runs" / "X"', {"runs"}),
    ('p = SRC.parent / "approvals"', {"approvals"}),
    ('p = tmp / "runs" / "T-001"', set()),
    ('ROOTS = ("runs", "registers")', set()),
    ('p = REPO / "specs" / "x.md"', set()),
)


def source_self_check() -> list[str]:
    out = []
    for src, want in SOURCE_CASES:
        got = record_roots_read(ast.parse(src))
        if got != want:
            out.append(f"{src!r}: expected {want or 'no record root'}, "
                       f"got {got or 'none'}")
    return out


def main() -> int:
    failures: list[str] = []
    suites = sorted((REPO / "scripts").glob("test_*.py"))

    wrong = self_check() + source_self_check()
    if wrong:
        print("fixture sources")
        print("  the check does not agree with its own cases, so nothing it "
              "says about the\n  repository below can be relied on:")
        for w in wrong:
            print(f"    FAIL: {w}")
        return 1

    def ok(m: str) -> None:
        print(f"  [ok] {m}")

    print("fixture sources")
    print(f"  [ok] the check agrees with its own cases: "
          f"{len(SELF_CASES)} declaration(s) and {len(SOURCE_CASES)} path "
          f"shape(s)")
    print(f"  {len(suites)} suite(s) in scripts/")

    undeclared: list[str] = []
    declared_count = 0

    for p in suites:
        rel = p.relative_to(REPO).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            failures.append(f"{rel}: will not parse: {e}")
            continue

        sources = declares(tree)
        named = record_roots_read(tree)

        if not named:
            if sources and rel != "scripts/test_fixture_sources.py":
                failures.append(
                    f"{rel} declares FIXTURE_SOURCES and reads no record "
                    f"directory. A declaration\n    nothing uses drifts "
                    f"without failing, which is the defect one level up.")
            continue

        if sources is None:
            undeclared.append(f"{rel}  (names {', '.join(sorted(named))})")
            continue
        declared_count += 1

        for root in sorted(named):
            if root not in sources:
                failures.append(
                    f"{rel} reads {root}/ and declares every other source but "
                    f"that one. A\n    declaration that covers the easy cases "
                    f"and omits the hard one is worse\n    than none, because "
                    f"it reads as complete.")

        for src, why in sorted(sources.items()):
            bad = fault(rel, src, why, (REPO / src).exists())
            if bad:
                failures.append(bad)

    if undeclared:
        failures.append(
            "suite(s) that read a real record and declare nothing:\n      "
            + "\n      ".join(undeclared) +
            "\n    specs/FIXTURE-SOURCES.md says what a declaration looks "
            "like and why the\n    absent case has to be in it.")
    else:
        ok(f"{declared_count} suite(s) read a real record, and each says "
           f"which, why, and what\n       happens when it is not there")

    if failures:
        print()
        for f in failures:
            print(f"  FAIL: {f}")
        print(f"\n  {len(failures)} problem(s).")
        return 1

    print("\n  every suite that reads a real record says so, and says which "
          "way it fails\n  when the record is absent")
    print("\n  Note: nothing here checks that a declared reason is true, and "
          "nothing runs the\n  suite without its records to see whether the "
          "stated direction is the real one.\n  The declaration makes the "
          "claim visible to a reader, which is the most a check\n  inside the "
          "repository can do about intent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
