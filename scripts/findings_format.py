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
from collections import Counter
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
# A fenced block, and everything in it. Reviewers quote example reviews as
# evidence, and BOOTSTRAP-003 cycle 03 did exactly that: its evidence for
# D02-F01 contained a specimen finding block, the parser read the specimen as a
# declaration, and the capture recorded `D03-F90` as a finding the reviewer
# never raised. Quoted material is not a declaration.
#
# Masked rather than removed, so every offset below still points where it did
# and the block slicing is unaffected.
FENCE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$", re.M | re.S)


def mask_fences(raw: str) -> str:
    """Fenced blocks blanked out, line structure and offsets preserved."""
    return FENCE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw)


# An identifier with a declaration attached: the same shape SIGNALS uses, with
# the identifier captured so a signal can be matched against what parsed.
# The Class or Status must be on the identifier's own line or the very next
# one, and that next line must not carry an identifier of its own.
#
# A two-line window was tried first and was wrong. BOOTSTRAP-001 cycle 02 says
# in prose "B01-F01, B01-F04 ... remain OPEN by the stated deferral", and two
# lines below it a different, perfectly valid block begins with its own Status
# line. The wider window tied the prose reference to that block's status and
# reported a declaration nobody had written. Running the repair over four
# frozen runs is what surfaced it, which is the only reason it was not shipped.
DECLARATION = re.compile(
    r"\b([A-Z]{0,2}\d{2}-F\d{2,3})\b"
    # Same line: immediately after the identifier, not anywhere on the line.
    # `[^\n]*` was tried and was wrong twice over. BOOTSTRAP-002 cycle 02
    # contains a repair-assessment table whose first column is an identifier
    # and whose later columns mention a status, and the loose version paired
    # the two across the row and reported a declaration that is a table cell.
    r"(?:[ \t,;:.\-]{0,4}(?i:class|status)\s*:"
    r"|[^\n]*\n(?![^\n]*\b[A-Z]{0,2}\d{2}-F\d{2,3}\b)"
    r"[ \t]*(?i:class|status)\s*:)")

SIGNALS = (
    re.compile(r"finding\s*id\s*[:=]", re.I),
    re.compile(r"^\s*required correction\s*:", re.I | re.M),
    # D02-F01, BOOTSTRAP-003 cycle 02. This was `\b[A-Z]{0,2}\d{2}-F\d{2,3}\b`:
    # any canonical identifier, anywhere in the text, at all.
    #
    # That made a correct review unrecordable. A reviewer who writes "the repair
    # to D01-F01 is demonstrated, no new findings" trips the net, zero cannot be
    # asserted, and the capture is refused. The cycle 02 prompt instructed the
    # reviewer to assess D01-F01 explicitly, so the instruction and the recorder
    # had been contradicting each other since that prompt was written. Alex
    # Zamurko, 8 October: "The parser needs to distinguish 'reference to an
    # existing finding' from 'new finding declaration.'"
    #
    # The net is not dropped. It exists because a finding block with a malformed
    # header parses to nothing, and zero must not be assertable over a review
    # the parser may have failed to read. What distinguishes a declaration from
    # a reference is not the identifier: it is the Class or Status line that a
    # finding block must carry. So the identifier counts only when one of those
    # is attached to it, on its own line or within the two lines below.
    #
    # This only ever runs when NOTHING parsed, so an identifier mentioned in
    # prose near a block that did parse cannot reach it.
    DECLARATION,
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


def extract(raw: str, grammar: str | None = None) -> tuple[list[dict], list[str]]:
    """(entries, problems) parsed deterministically from raw reviewer output.

    Each entry carries a `kind`:

        finding      a new finding, with its own class from §4's vocabulary
        recurrence   a persistent identifier whose repair was not demonstrated,
                     class None, to be resolved from the ledger by the caller

    Anything unparseable is a problem rather than a silent omission. The failure
    being prevented is findings going missing between the reviewer and the
    ledger, so this never quietly returns fewer than it saw.

    C03-F01. `grammar` is the pattern a completed cycle was parsed with, which
    the runner records in its findings.json. Codex: "a completed review's
    interpretation depends on today's schema. A later grammar amendment
    excluding a previously valid identifier makes an unchanged historical raw
    review fail reconciliation, even though its frozen artifacts and recorded
    grammar remain intact."

    Which it did, because this read the live schema every time, including when
    re-reading a review from three weeks ago. A caller that knows which grammar
    a cycle was parsed with passes it; a caller parsing something new passes
    nothing and gets today's. Preserving the schema bytes in a target was never
    going to fix that, since the parser never consulted them.
    """
    pattern = re.compile(grammar) if grammar else canonical_id_grammar()
    return _extract_with(raw, pattern)


def _extract_with(raw: str, grammar: re.Pattern) -> tuple[list[dict], list[str]]:
    found: list[dict] = []
    problems: list[str] = []

    # Everything below reads the masked text. A finding block is a structure the
    # review declares, not something it quotes, and the parser had no way to
    # tell the difference until cycle 03 handed it one.
    text = mask_fences(raw)

    starts = [(m.start(), m.group(1)) for m in FINDING_HEADER.finditer(text)]
    raw_count = len(starts)

    # B02-F01, checked before anything else. If the loose pass sees a boundary
    # the strict pass does not, the difference is named rather than dropped, and
    # it is fatal regardless of how many blocks parsed cleanly.
    loose = [m.group(1) for m in LOOSE_HEADER.finditer(text)]
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
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[pos:end]

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
        hits = [p.pattern for p in SIGNALS if p.search(text)]
        if hits:
            problems.append(
                "no finding blocks parsed, but the raw review carries signals "
                "that one is present:\n    " + "\n    ".join(hits) +
                "\n  Zero cannot be asserted over a review the parser may have "
                "failed to read.")

    # D02-F01, second pass. BOOTSTRAP-003 cycle 03: "the signal net runs only
    # when `found` is empty. The new malformed declarations covered by this
    # repair remain invisible when another finding parses successfully."
    #
    # True, and it is the same gate twice. B02-F01 moved it from "no raw blocks"
    # to "nothing structured", which is a smaller gate and still a gate: one
    # block that parses switches the net off for every block that does not. His
    # reproduction is a canonical finding followed by `Finding-ID D03-F91` with
    # its own class, and the second one vanishes.
    #
    # So declarations are reconciled against what parsed, always, rather than
    # consulted only when nothing did. An identifier carrying a class or a
    # status that no parsed block accounts for is a block the parser could not
    # read, whatever else it managed.
    # Occurrences, not identifiers. BOOTSTRAP-003 cycle 04, D02-F01 for the
    # third time, and its case is sharper than either of the first two.
    #
    # This compared a SET of declared identifiers against a SET of parsed
    # ones. Two declarations carrying the SAME identifier, one canonical and
    # one malformed, therefore collapsed to a single element on both sides and
    # the difference was empty. The reviewer's case: a correct `Finding ID:
    # D04-F90` block followed by `Finding-ID D04-F90` with a different class
    # and different content. One parses, one does not, the sets agree, and the
    # second disappears with no problem reported. The duplicate check above
    # cannot see it either, because it looks only at what parsed.
    #
    # Twice now I have repaired the example rather than the rule: cycle 02
    # showed me a reference being read as a declaration, cycle 03 showed me
    # the net switched off by one parsed block, and each time I fixed the
    # shape I was shown. Counting occurrences is the rule. An identifier
    # declared more times than it parsed has a block the parser could not
    # read, whether or not some other block carries the same name.
    _declared = Counter(m.group(1) for m in DECLARATION.finditer(text))
    _parsed = Counter(f["id"] for f in found)
    _unaccounted = sorted(i for i, n in _declared.items()
                          if n > _parsed.get(i, 0))
    if _unaccounted:
        _detail = ", ".join(
            f"{i} (declared {_declared[i]}, parsed {_parsed.get(i, 0)})"
            for i in _unaccounted)
        problems.append(
            f"declaration(s) the parser could not read: {_detail}\n"
            "  Each carries a Class or Status line and matches no finding block "
            "this parser recognised.\n  A block it cannot see is a finding the "
            "loop never hears about, and one block parsing\n  correctly says "
            "nothing about the others, including another block that happens to\n"
            "  carry the same identifier.")

    # What masking costs, stated rather than guarded against.
    #
    # A reviewer who fences their entire review parses to nothing and trips no
    # net, because quoted material is deliberately ignored. A guard for that
    # case was written and removed within the hour: it fired on "no new
    # findings" plus a quoted example, which is precisely the shape cycle 03's
    # own review had and precisely what this repair exists to accept. Refusing
    # the common correct case to catch an uncommon careless one is the wrong
    # trade.
    #
    # The residual risk is bounded by something outside this parser. Zero is
    # never inferred: recording a zero-finding cycle takes an explicit
    # --zero-findings from the operator, over a raw review preserved in full
    # for anyone to read. So the fully-fenced review ends as a human asserting
    # zero over a document that visibly contains findings, which is a different
    # failure from a parser silently dropping them, and the one the rest of
    # this layer is built to surface.
    return found, problems
