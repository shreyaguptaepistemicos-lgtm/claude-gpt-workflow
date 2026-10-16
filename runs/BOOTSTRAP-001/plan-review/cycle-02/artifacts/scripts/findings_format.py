#!/usr/bin/env python3
"""The one parser for reviewer output, and the one Finding ID grammar.

Imported by the runner, which writes findings.json, and by the MC-2 checker,
which verifies it. One module rather than two implementations, because the
failure this closes is components each enforcing their own idea of the format.

Alex Zamurko, 9 September 2026:

    Prompt, parser, and ledger must not independently impose different
    grammars. The clean choice is: the review format defines the canonical
    grammar, the runner validates it, and the ledger preserves it unchanged.

That happened. The prompt said `B01-F01`, the ledger demanded `C{cycle}-F{nn}`,
and eighteen findings were renamed between the review and the record. A second
copy of this logic anywhere would be a fourth grammar with the same problem, so
there is exactly one, and the grammar itself is read from the schema rather than
restated here.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DOC = REPO / "specs" / "evidence-schema-v1.0.md"

# §4's closed vocabulary. A class outside it is a defect in the review, not a
# finding to be recorded.
CLASSES = (
    "MISSING REQUIREMENT",
    "WRONG OWNERSHIP",
    "NONDETERMINISTIC WHERE D POSSIBLE",
    "SEMANTIC STEP TOO BROAD",
    "UNTESTED RULE",
    "CONTRADICTORY IMPLEMENTATION MAPPING",
)

# Permissive about the identifier on purpose. An id that fails the canonical
# grammar must make the result INVALID, not disappear from the parse: a strict
# pattern here would turn a malformed identifier into a missing finding, which
# is the worse failure of the two.
FINDING_HEADER = re.compile(r"^Finding ID:\s*(\S+)\s*$", re.M)
FINDING_CLASS = re.compile(r"^Class:\s*(.+?)\s*$", re.M)

# Used only to prove that zero means zero. Deliberately looser than the header.
# Requirement 1: zero is permitted only when parsing confirms the raw review
# contains no finding blocks, and the risk is a parser that fails to recognise
# real findings while the operator honestly asserts none. So zero has to survive
# a broader net, and any signal the strict parse does not account for is
# ambiguity rather than absence.
SIGNALS = (
    re.compile(r"finding\s*id\s*[:=]", re.I),
    re.compile(r"^\s*required correction\s*:", re.I | re.M),
    re.compile(r"\b[A-Z]{0,2}\d{2}-F\d{2,3}\b"),
)


class FormatError(Exception):
    """The schema does not declare what this module needs. Not recoverable."""


def canonical_id_grammar() -> re.Pattern:
    """The Finding ID grammar, read from its one authoritative location."""
    m = re.search(r"^FINDING_ID_GRAMMAR\s*=\s*(\S+)\s*$",
                  SCHEMA_DOC.read_text(encoding="utf-8"), re.M)
    if not m:
        raise FormatError(
            f"no FINDING_ID_GRAMMAR declared in {SCHEMA_DOC.name}. The canonical "
            "grammar has one authoritative location and this is it; without it "
            "the parser would be inventing a grammar, which is the divergence "
            "being closed.")
    return re.compile(m.group(1))


def extract(raw: str) -> tuple[list[dict], list[str]]:
    """(findings, problems) parsed deterministically from raw reviewer output.

    Anything unparseable is a problem rather than a silent omission. The failure
    being prevented is findings going missing between the reviewer and the
    ledger, so this never quietly returns fewer than it saw.
    """
    grammar = canonical_id_grammar()
    found: list[dict] = []
    problems: list[str] = []

    starts = [(m.start(), m.group(1)) for m in FINDING_HEADER.finditer(raw)]
    raw_count = len(starts)

    for i, (pos, fid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
        block = raw[pos:end]

        if not grammar.fullmatch(fid):
            problems.append(f"finding identifier {fid!r} does not match the "
                            f"canonical grammar {grammar.pattern}")
            continue
        km = FINDING_CLASS.search(block)
        if not km:
            problems.append(f"{fid} has no Class: line")
            continue
        klass = km.group(1).strip()
        if klass not in CLASSES:
            problems.append(f"{fid} declares a class outside the closed "
                            f"vocabulary of §4: {klass!r}")
            continue
        found.append({"id": fid, "class": klass})

    ids = [f["id"] for f in found]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate finding identifiers: {', '.join(dupes)}")

    # RAW_FINDING_COUNT = STRUCTURED_FINDING_COUNT.
    if raw_count != len(found) and not problems:
        problems.append(f"{raw_count} finding block(s) detected in the raw "
                        f"review but {len(found)} structured record(s) produced")

    if raw_count == 0:
        hits = [p.pattern for p in SIGNALS if p.search(raw)]
        if hits:
            problems.append(
                "no finding blocks parsed, but the raw review carries signals "
                "that one is present:\n    " + "\n    ".join(hits) +
                "\n  Zero cannot be asserted over a review the parser may have "
                "failed to read.")
    return found, problems
