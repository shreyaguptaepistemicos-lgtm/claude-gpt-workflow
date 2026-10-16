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


class NotAuthorized(Exception):
    """No usable approval for this action. The caller refuses and changes nothing."""


def _fail(path: Path, why: str, bindings: dict[str, str], kind: str) -> None:
    lines = [why, "",
             f"  Expected an approval record at:  {path}", "",
             "  It has to be written by someone other than the implementing "
             "agent, and name:",
             f"    schema          {kind}/1",
             "    authorized_by   the person approving, by name",
             f"    reason          why, in at least {MIN_REASON} characters",
             "    at              when, ISO 8601"]
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

    if rec.get("schema") != f"{kind}/1":
        raise NotAuthorized(
            f"the approval record declares schema {rec.get('schema')!r}, "
            f"expected {kind + '/1'!r}.\n"
            "  An approval for one kind of decision does not authorize another.")

    who = str(rec.get("authorized_by", "")).strip()
    if not who:
        raise NotAuthorized(
            "the approval record names no one in authorized_by.\n"
            "  An unattributed approval is indistinguishable from the "
            "implementing agent\n  approving its own action, which is the thing "
            "this record exists to prevent.")

    reason = str(rec.get("reason", "")).strip()
    if len(reason) < MIN_REASON:
        raise NotAuthorized(
            f"the approval record's reason is {len(reason)} characters; at least "
            f"{MIN_REASON} are required.\n"
            "  The reason is what a later reader uses to judge whether the "
            "decision was sound.\n  A placeholder leaves the record looking "
            "complete while saying nothing.")

    if not str(rec.get("at", "")).strip():
        raise NotAuthorized("the approval record has no `at` timestamp, so it "
                            "cannot be placed in the sequence of events.")

    wrong = []
    for field, expected in bindings.items():
        got = str(rec.get(field, "")).strip()
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
