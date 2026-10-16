#!/usr/bin/env python3
"""Approvals that have to come from outside the implementing agent.

Alex Zamurko, 9 September 2026, ruling 3:

    An authoritative capture may be superseded only with explicit human/evidence
    authority approval and a recorded reason; the implementing agent cannot
    supersede it unilaterally ... allowing the implementing agent to choose a
    later Codex capture creates a direct cherry-picking path. Preserving all
    attempts is not sufficient if the same party can decide which one governs.

The same shape is needed for runner approval, which is what ends the bootstrap
exception, so it lives here once rather than being written twice and drifting.

What this establishes, and what it does not
-------------------------------------------
MC1_ENFORCEMENT is CONVENTION_ONLY on this environment. There is one machine and
one account, so nothing here proves who wrote a file. Saying otherwise would be
the "claim stronger than its evidence" failure the review prompt asks reviewers
to flag, and it would be this module claiming it.

What it does establish is narrower and still worth having:

  * an approval must exist as a separate artifact before the action runs, so the
    decision leaves a record instead of living in a command-line flag;
  * it must name a person and a reason, so the record is attributable;
  * it must bind to the exact bytes it approves, by hash, so an approval cannot
    be recycled for a different action later. This is the mechanical part, and
    it is the part that holds regardless of who wrote the file.

B02-F09: what this module used to claim
----------------------------------------
An earlier version of this docstring said the required hashes were "not knowable
until the action has been attempted and refused once", and concluded that
obtaining an approval was therefore a step outside the command. Codex checked it
in cycle 02 and it is false. Both values are ordinary facts available in advance:
the capture being displaced is named in capture-log.json as authoritative_sha256,
and the replacement is the sha256 of a file the caller already holds. The cycle
name is known too. No refusal is recorded anywhere and no nonce is involved, so a
valid approval can be written before any attempt is made. The probe that
demonstrated a successful supersession used exactly that construction.

Alex Zamurko, 10 September: "remove the claim that the external-authority step is
technically forced. Describe the current control as procedural / CONVENTION_ONLY,
and upgrade the claim only after a genuine independent write boundary exists."

So, stated at its real strength: this is a procedural control with deterministic
byte matching. It does not force a sequence, does not prove authorship, and does
not establish that the approval came from another actor. It requires the decision
to exist as a separate, attributable artifact bound to specific bytes. Under
CONVENTION_ONLY the implementing agent can write that artifact itself, and the
honest description of the difference is that doing so means composing a record in
someone else's name rather than passing a flag. How much that is worth depends on
the people involved, which is what "procedural" means. A write boundary would
make it structural, and needs a second machine.
"""

from __future__ import annotations

import json
from pathlib import Path

MIN_REASON = 20

# Alex Zamurko, 9 October 2026: "Make sure the authorisation is properly
# documented and can be verified, rather than relying only on a name entered
# into a file."
#
# He is right that a name in a file establishes nothing. This does not fix
# that, and it would be dishonest to present it as a fix. What it does is make
# the claim CHECKABLE BY A PERSON: the record must say where the authorisation
# was given and quote the words that gave it, so a reader who can reach that
# channel can confirm or refute it in a few seconds. Before this, there was
# nothing to check against at all.
#
# What it still does not establish, recorded as AR-2 in
# specs/ACCEPTED-RISKS.md: the implementing agent types all of this, and could
# type a quote that was never said. Only the approver writing or signing the
# record themselves removes that, and that is a decision about how much of
# Alex's time each supersession is worth.
MIN_QUOTE = 15

# The day the source requirement took effect. An approval dated on or after
# this must declare schema `<kind>/2` and carry one; anything earlier is read
# under the rule that existed when it was written.
SOURCE_REQUIRED_FROM = "2026-10-09"


class NotAuthorized(Exception):
    """No usable approval for this action. The caller refuses and changes nothing."""


def text(obj: dict, key: str) -> str:
    """The value at `key` if it is a non-blank string, otherwise ''.

    D04-F01, BOOTSTRAP-003 cycle 04. Every presence check in this file was
    written as `str(rec.get(k, "")).strip()`, and `str(None)` is the
    four-character string "None". So a JSON null passed every check that
    exists to require a value. An approval declaring

        "source": {"medium": null, "reference": null, "quote": "..."}

    satisfied the rule that it must say where the authorisation was given.

    The reviewer named the source fields. The same expression was also
    guarding `authorized_by`, `reason` and `at`, so a null name passed the
    check that exists to stop an unattributed approval. Fixing only the three
    it pointed at would be repairing the example rather than the rule, which
    is what D02-F01 took three cycles to teach.

    A value is present here only if it is genuinely a string with something
    in it. Anything else, null, a number, a list, an object, is absent.
    """
    v = obj.get(key)
    return v.strip() if isinstance(v, str) and v.strip() else ""


def _fail(path: Path, why: str, bindings: dict[str, str], kind: str) -> None:
    lines = [why, "",
             f"  Expected an approval record at:  {path}", "",
             "  It has to be written by someone other than the implementing "
             "agent, and name:",
             f"    schema          {kind}/1",
             "    authorized_by   the person approving, by name",
             f"    reason          why, in at least {MIN_REASON} characters",
             "    at              when, ISO 8601",
             "    source          where the authorisation was actually given:",
             "                      medium     Slack, WhatsApp, email, commit",
             "                      reference  a permalink, or a description "
             "precise enough to find it",
             f"                      quote      their own words, at least "
             f"{MIN_QUOTE} characters"]
    for k, v in bindings.items():
        lines.append(f"    {k:<15} {v}")
    lines += ["",
              "  The hashes above are what bind the approval to this exact "
              "action, so an approval",
              "  written for one supersession cannot be reused for another. "
              "They are printed",
              "  because you need them to write the record, not because they "
              "were secret: both",
              "  are derivable from the capture log and the replacement file. "
              "This is a",
              "  procedural control under MC1_ENFORCEMENT: CONVENTION_ONLY. It "
              "does not force a",
              "  sequence and does not establish who wrote the approval."]
    raise NotAuthorized("\n".join(lines))


def require_approval(path: Path, kind: str, bindings: dict[str, str]) -> dict:
    """Load and check an approval, or refuse.

    `bindings` are field name -> required value. Every one must appear in the
    record and match exactly. That is what stops an approval for one supersession
    being reused for the next.
    """
    if not path.is_file():
        _fail(path, "This action requires an approval from outside the "
                    "implementing agent, and none is recorded.", bindings, kind)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise NotAuthorized(f"the approval record at {path} is not valid JSON: {e}")

    # Two versions, and the difference is the `source` requirement below.
    #
    # Alex Zamurko asked on 9 October 2026 that an authorisation say where it
    # was given. Applying that to every approval already on record would mean
    # one of two bad things: editing records made weeks earlier to add a field
    # nobody asked for at the time, which is rewriting evidence, or a gate
    # that refuses its own history.
    #
    # So a record states which rule it was made under. `/1` predates the
    # requirement and is read as it was written. `/2` carries a source. This
    # is C03-F01's principle, which Codex forced on the review parser in
    # BOOTSTRAP-002: a completed record is read with its own grammar, not
    # today's, or amending a rule silently changes what a finished decision
    # meant.
    _declared = str(rec.get("schema", ""))
    if _declared not in (f"{kind}/1", f"{kind}/2"):
        raise NotAuthorized(
            f"the approval record declares schema {rec.get('schema')!r}, "
            f"expected {kind + '/1'!r} or {kind + '/2'!r}.\n"
            "  An approval for one kind of decision does not authorize another.")

    who = text(rec, "authorized_by")
    if not who:
        raise NotAuthorized(
            "the approval record names no one in authorized_by.\n"
            "  An unattributed approval is indistinguishable from the "
            "implementing agent\n  approving its own action, which is the thing "
            "this record exists to prevent.")

    reason = text(rec, "reason")
    if len(reason) < MIN_REASON:
        raise NotAuthorized(
            f"the approval record's reason is {len(reason)} characters; at least "
            f"{MIN_REASON} are required.\n"
            "  The reason is what a later reader uses to judge whether the "
            "decision was sound.\n  A placeholder leaves the record looking "
            "complete while saying nothing.")

    if not text(rec, "at"):
        raise NotAuthorized("the approval record has no `at` timestamp, so it "
                            "cannot be placed in the sequence of events.")

    # A `/1` record written after the rule took effect is the hole in
    # grandfathering, so it is closed here rather than left to goodwill. It
    # does not force anything: the writer sets `at` and could backdate it,
    # which is AR-1 and is accepted for bootstrap. What it does is make an
    # anomaly visible to a reader instead of silent.
    if _declared.endswith("/1") and str(rec.get("at", "")) >= SOURCE_REQUIRED_FROM:
        # The phrase "predates the requirement" is kept on one line on
        # purpose. The first version wrapped it across a newline, and the
        # control that looks for it reported a refusal for the wrong reason:
        # the refusal was right and the sentence was split where the check
        # was reading. A message is part of the interface when something
        # matches on it.
        raise NotAuthorized(
            f"this approval predates the requirement in its schema but not "
            f"in its date.\n"
            f"  It is dated {rec.get('at')} and declares {_declared!r}. "
            f"Records written before\n  {SOURCE_REQUIRED_FROM} are read "
            f"under the older rule, which did not ask where the\n  "
            f"authorisation was given. One written after it is not.\n"
            f"  Declare {kind}/2 and add a source.")

    # Where the authorisation was actually given, and in whose words. A record
    # without this is a claim with nothing behind it; with it, a reader can go
    # and look. That is a smaller thing than proof and a larger thing than
    # nothing.
    #
    # Only `/2` is asked for it. The first version of this skipped the whole
    # rest of the function for a `/1` record, with an early `return rec`, and
    # that skipped the hash bindings below as well: a `/1` approval issued for
    # a completely different manifest was accepted. The suites caught it on
    # the first run, which is the one good thing to say about it. Grandfather
    # the new requirement, not the old ones.
    if _declared.endswith("/2"):
        src = rec.get("source")
        if not isinstance(src, dict):
            raise NotAuthorized(
                "the approval record has no `source`.\n"
                "  A name and a reason are what the implementing agent typed. "
                "The source is where\n  the person actually said it, so that "
                "someone else can check. It needs a medium,\n  a reference "
                "precise enough to find the message, and their own words.")
        _missing = [k for k in ("medium", "reference", "quote")
                    if not text(src, k)]
        if _missing:
            raise NotAuthorized(
                f"the approval record's source is missing "
                f"{', '.join(_missing)}.\n"
                "  Each of the three does different work: the medium says "
                "where to look, the\n  reference says where exactly, and the "
                "quote is what has to match when you\n  get there. Two out of "
                "three cannot be checked.")
        if len(text(src, "quote")) < MIN_QUOTE:
            raise NotAuthorized(
                f"the approval record quotes "
                f"{len(text(src, 'quote'))} characters; at least "
                f"{MIN_QUOTE} are required.\n"
                "  A quote too short to be distinctive cannot be matched "
                "against the message it\n  came from, which is the only thing "
                "it is here for.")

    wrong = []
    for field, expected in bindings.items():
        got = text(rec, field)
        if got != expected:
            wrong.append(f"    {field}\n      approved  {got or '(absent)'}\n"
                         f"      actual    {expected}")
    if wrong:
        raise NotAuthorized(
            "the approval record does not match the action being attempted:\n"
            + "\n".join(wrong) +
            "\n\n  An approval binds to the exact bytes it approved. If this is "
            "a different\n  action, it needs its own approval rather than "
            "inheriting one.")

    return rec


def describe(rec: dict) -> str:
    return f"approved by {rec['authorized_by']} at {rec['at']}: {rec['reason']}"
