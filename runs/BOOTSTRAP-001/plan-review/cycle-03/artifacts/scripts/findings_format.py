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

# B02-F01. The strict header is line-anchored with no leading whitespace, so a
# block indented by one space was invisible to it — and because the SIGNALS
# reconciliation below only ran when NOTHING parsed, one successful block
# disabled the safeguard against the rest. Codex demonstrated it: two blocks in,
# one identifier out, and an empty problems list.
#
# This counts apparent boundaries and is never used to parse. Its only job is to
# disagree with the strict pass, which is a refusal rather than a silent
# shortfall.
LOOSE_HEADER = re.compile(r"^[ \t]*Finding\s*ID\s*[:=]\s*(\S+)", re.I | re.M)

# B02-F02. A cycle-01 finding whose repair did not hold is not a new finding: it
# keeps its persistent identifier (V40) and its original class. The cycle-02
# prompt asked for exactly this form and the parser refused it, which is the
# prompt/parser/ledger divergence Alex Zamurko ruled against on 9 September,
# reappearing in the module built to end it.
#
# The class is deliberately NOT re-asserted by the reviewer. Asking for it again
# invites a value that disagrees with the original, and then two records claim
# different classes for one identifier. It is resolved from the ledger by the
# caller, which is the only place that knows what was raised.
FINDING_STATUS = re.compile(r"^Status:\s*(.+?)\s*$", re.M)
RECURRENCE_STATUS = "REPAIR NOT DEMONSTRATED"

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
    """(entries, problems) parsed deterministically from raw reviewer output.

    Each entry carries a `kind`:

        finding      a new finding, with its own class from §4's vocabulary
        recurrence   a persistent identifier whose repair was not demonstrated,
                     class None, to be resolved from the ledger by the caller

    Anything unparseable is a problem rather than a silent omission. The failure
    being prevented is findings going missing between the reviewer and the
    ledger, so this never quietly returns fewer than it saw.
    """
    grammar = canonical_id_grammar()
    found: list[dict] = []
    problems: list[str] = []

    starts = [(m.start(), m.group(1)) for m in FINDING_HEADER.finditer(raw)]
    raw_count = len(starts)

    # B02-F01, checked before anything else. If the loose pass sees a boundary
    # the strict pass does not, the difference is named rather than dropped, and
    # it is fatal regardless of how many blocks parsed cleanly.
    loose = [m.group(1) for m in LOOSE_HEADER.finditer(raw)]
    strict_ids = [fid for _, fid in starts]
    if len(loose) != len(strict_ids):
        missed = [i for i in loose if i not in strict_ids] or ["(unnamed)"]
        problems.append(
            f"{len(loose)} apparent finding block(s) in the raw review but only "
            f"{len(strict_ids)} in canonical form: {', '.join(missed)}\n"
            "  A block the strict parser cannot see is a finding the loop never "
            "hears about.\n  Fix the formatting in the review rather than "
            "accepting the smaller set.")

    for i, (pos, fid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
        block = raw[pos:end]

        if not grammar.fullmatch(fid):
            problems.append(f"finding identifier {fid!r} does not match the "
                            f"canonical grammar {grammar.pattern}")
            continue

        km = FINDING_CLASS.search(block)
        sm = FINDING_STATUS.search(block)

        if km and sm:
            problems.append(
                f"{fid} carries both a Class: and a Status: line. A block is "
                "either a new finding\n  with its own class, or a recurrence of "
                "an existing identifier, not both.")
            continue

        if km:
            klass = km.group(1).strip()
            if klass not in CLASSES:
                problems.append(f"{fid} declares a class outside the closed "
                                f"vocabulary of §4: {klass!r}")
                continue
            found.append({"id": fid, "class": klass, "kind": "finding"})
            continue

        if sm:
            status = sm.group(1).strip().upper()
            if status != RECURRENCE_STATUS:
                problems.append(
                    f"{fid} declares Status: {sm.group(1).strip()!r}, which is "
                    f"not recognised. The only status a review may report "
                    f"against a persistent\n  identifier is "
                    f"{RECURRENCE_STATUS!r}.")
                continue
            # Class deliberately absent. Resolved from the ledger downstream.
            found.append({"id": fid, "class": None, "kind": "recurrence"})
            continue

        problems.append(
            f"{fid} has neither a Class: line nor a Status: line. A new finding "
            f"needs a class from\n  §4's vocabulary; a recurrence of an existing "
            f"identifier needs Status: {RECURRENCE_STATUS}.")

    ids = [f["id"] for f in found]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate finding identifiers: {', '.join(dupes)}")

    # RAW_FINDING_COUNT = STRUCTURED_FINDING_COUNT.
    if raw_count != len(found) and not problems:
        problems.append(f"{raw_count} finding block(s) detected in the raw "
                        f"review but {len(found)} structured record(s) produced")

    # The signal net. Formerly gated on raw_count == 0, which meant one parsed
    # block switched it off entirely; that gating is half of B02-F01. It now
    # runs whenever nothing was structured, so a review that parses to nothing
    # still has to survive the broader search.
    if not found:
        hits = [p.pattern for p in SIGNALS if p.search(raw)]
        if hits:
            problems.append(
                "no finding blocks parsed, but the raw review carries signals "
                "that one is present:\n    " + "\n    ".join(hits) +
                "\n  Zero cannot be asserted over a review the parser may have "
                "failed to read.")
    return found, problems
