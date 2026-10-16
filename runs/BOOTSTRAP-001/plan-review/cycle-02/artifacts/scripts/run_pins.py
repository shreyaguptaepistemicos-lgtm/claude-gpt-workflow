#!/usr/bin/env python3
"""Which artifacts govern a run, and which are under review. Never both.

Alex Zamurko, 10 September 2026, the Run-Pin and Review-Target Separation
Specification. Its governing invariant:

    No review process may require an artifact to remain byte-invariant for the
    duration of a run while simultaneously requiring that same artifact version
    to change in order to resolve review findings.

BOOTSTRAP-001 required exactly that. It pinned `specs/evidence-schema-v1.0.md`
as its only run-level spec, and the same file was the first of cycle 01's six
review targets. Cycle 01 raised findings that could only be repaired by editing
it, and editing it broke the run's own pin, so the runner refused to open
cycle 02 — the cycle whose purpose was to demonstrate those repairs and move
eighteen findings out of OPEN. The loop was stopped by its own correctness.

Amendments are history, not edits
---------------------------------
run.json is evidence of what was pinned when the run was created, and it stays
true about that. Rewriting it so a failing check passes is the move this whole
repository exists to prevent, and it would destroy the only record of what
cycle 01 was actually conducted under.

So a change to the pin set is appended to `pin-amendments.json` instead, with
the five fields the specification requires: reason, affected artifacts, prior
pin set, new pin set, effective cycle. The pin set governing any cycle is then
computed by replaying that history rather than read from a single mutable field.

That matters beyond tidiness. Cycle 01 was conducted under the original pins and
cycle 02 under the amended ones, and both statements have to stay recoverable.
B01-F07, still open by Alex Zamurko's deferral, is the finding that no check ties
a cycle's recorded protocol_sha256 and spec_sha256 back to the run. When that is
repaired it must tie each cycle to the pins in force AT THAT CYCLE, which is what
`pins_for_cycle` returns. Tying every cycle to the latest pin set would
retroactively invalidate cycle 01, which is the same defect in a new place.

What this does not do
---------------------
It does not decide whether an amendment was wise. It records that one was made,
by whom, and why, and it refuses an amendment whose prior_pin_set does not match
what the history actually shows, so the chain cannot be quietly rewritten in the
middle. Under MC1_ENFORCEMENT: CONVENTION_ONLY that is drift detection, not
prevention.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "run-pin-amendments/1"
MIN_REASON = 30


class PinError(Exception):
    """The pin history cannot be read, or does not describe a coherent chain."""


def amendments_path(run_dir: Path) -> Path:
    return run_dir / "pin-amendments.json"


def initial_pin_set(run: dict) -> list[str]:
    """What run.json pinned at init: the protocol and every spec file."""
    out = [run["protocol"]["path"]]
    out += [e["path"] for e in run.get("spec_files", [])]
    return sorted(set(out))


def load_amendments(run_dir: Path) -> list[dict]:
    p = amendments_path(run_dir)
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PinError(f"pin-amendments.json is not valid JSON: {e}")
    if d.get("schema") != SCHEMA:
        raise PinError(f"pin-amendments.json declares schema {d.get('schema')!r}, "
                       f"expected {SCHEMA!r}")
    items = d.get("amendments")
    if not isinstance(items, list):
        raise PinError("pin-amendments.json has no amendments list")
    return items


def validate_chain(run: dict, items: list[dict]) -> None:
    """Each amendment must name the five required fields and follow the last.

    The prior_pin_set check is the load-bearing one. Without it an amendment
    could assert any starting point, and the recorded history would no longer
    reconstruct what actually governed each cycle: someone could insert a pin
    set that never existed and every later replay would agree with them.
    """
    required = ("reason", "affected_artifacts", "prior_pin_set", "new_pin_set",
                "effective_cycle", "authorized_by", "at")
    current = initial_pin_set(run)
    last_cycle = 0
    for i, a in enumerate(items):
        missing = [k for k in required
                   if a.get(k) in (None, "", [], {})]
        if missing:
            raise PinError(
                f"amendment {i} is missing {', '.join(missing)}.\n"
                "  The specification requires reason, affected artifacts, prior "
                "pin set, new pin\n  set and effective cycle. Attribution and a "
                "timestamp are required too: a pin\n  change with nobody's name "
                "on it is the implementing agent changing what governs\n  its own "
                "review.")
        if len(str(a["reason"]).strip()) < MIN_REASON:
            raise PinError(
                f"amendment {i}'s reason is {len(str(a['reason']).strip())} "
                f"characters; at least {MIN_REASON} are required.")
        if sorted(a["prior_pin_set"]) != current:
            raise PinError(
                f"amendment {i} does not follow the pin history.\n"
                f"    it claims the prior set was  {sorted(a['prior_pin_set'])}\n"
                f"    the history says it was      {current}\n"
                "  An amendment that starts from a set that never existed makes "
                "every later\n  replay agree with a history nobody lived.")
        if int(a["effective_cycle"]) <= last_cycle:
            raise PinError(
                f"amendment {i} takes effect at cycle "
                f"{a['effective_cycle']}, which is not after the previous "
                f"amendment's cycle {last_cycle}. Amendments apply forward.")
        affected = set(a["affected_artifacts"])
        changed = set(current) ^ set(a["new_pin_set"])
        if affected != changed:
            raise PinError(
                f"amendment {i}'s affected_artifacts do not match what it "
                "changes.\n"
                f"    declared  {sorted(affected)}\n"
                f"    actual    {sorted(changed)}\n"
                "  The declared list is what a reader checks against; if it can "
                "differ from the\n  real change, the record describes an "
                "amendment that did not happen.")
        current = sorted(set(a["new_pin_set"]))
        last_cycle = int(a["effective_cycle"])


def pins_for_cycle(run: dict, items: list[dict], cycle_n: int) -> list[str]:
    """The run-level governing pin set in force for cycle `cycle_n`.

    An amendment effective at cycle k governs cycle k and every cycle after it,
    and does not reach back. Cycle 01 keeps the pins it was conducted under.
    """
    pins = initial_pin_set(run)
    for a in items:
        if int(a["effective_cycle"]) <= cycle_n:
            pins = sorted(set(a["new_pin_set"]))
    return pins


def governing_pins(run: dict, run_dir: Path, cycle_n: int) -> list[str]:
    items = load_amendments(run_dir)
    validate_chain(run, items)
    return pins_for_cycle(run, items, cycle_n)


def separation_violations(pins: list[str], targets: list[str]) -> list[str]:
    """Artifacts asked to be invariant and under review at the same time.

    §2 of the specification: the same artifact version must not serve as both an
    immutable run-governing input and a mutable review candidate. Without
    explicit ACTIVE/CANDIDATE version separation an artifact belongs to exactly
    one role.
    """
    return sorted(set(pins) & set(targets))
