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
import re
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


def validate_chain(run: dict, items: list[dict],
                   frozen: dict[int, list[str]] | None = None) -> None:
    """Each amendment must name the five required fields and follow the last.

    The prior_pin_set check is the load-bearing one. Without it an amendment
    could assert any starting point, and the recorded history would no longer
    reconstruct what actually governed each cycle: someone could insert a pin
    set that never existed and every later replay would agree with them.

    B02-F05, Alex Zamurko 10 September: "constrain amendments by role. The
    governing protocol cannot be removed; added pins must be validated; only
    explicitly permitted pin roles may change." The first version accepted any
    structurally valid change, so an amendment could drop the protocol out of
    the governing set entirely, or add a path that no check ever looked at
    because the pin check iterated only what run.json originally recorded.

    B02-F06: `frozen` maps an existing cycle number to the pin set recorded in
    its target.json at freeze. An amendment that would change one of those is
    refused. Comparing amendments only against each other made "applies forward"
    mean nothing more than "the numbers increase", so an amendment appended
    after a review could still rewrite what governed it.
    """
    required = ("reason", "affected_artifacts", "prior_pin_set", "new_pin_set",
                "effective_cycle", "authorized_by", "at")
    protocol_path = run["protocol"]["path"]
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
        # B02-F05, role constraint one. The protocol is what every review is
        # conducted against; a run without it in the governing set is a run
        # measuring against nothing. Amendments move artifacts between roles,
        # they do not dissolve the role.
        if protocol_path not in a["new_pin_set"]:
            raise PinError(
                f"amendment {i} removes the governing protocol from the pin "
                f"set:\n    {protocol_path}\n"
                "  An amendment may change which specs govern a run. It may not "
                "leave the run\n  without the document its reviews are conducted "
                "against.")

        # B02-F05, role constraint two. A path added to the governing set has to
        # arrive with the bytes it names. Amendments carried paths only, and the
        # pin check walked run.json's original entries, so an added pin was
        # never hashed and never checked: naming it was enough.
        added = sorted(set(a["new_pin_set"]) - set(current))
        hashes = a.get("added_pin_hashes") or {}
        missing_hash = [p for p in added if not str(hashes.get(p, "")).strip()]
        if missing_hash:
            raise PinError(
                f"amendment {i} adds governing artifact(s) without binding them "
                "to their bytes:\n    " + "\n    ".join(missing_hash) +
                "\n  Give added_pin_hashes as a path to sha256 map. A pin that "
                "names a file without\n  naming its contents is a pin nothing "
                "can verify.")
        bad_hash = [p for p in added
                    if not re.fullmatch(r"[0-9a-f]{64}", str(hashes.get(p, "")))]
        if bad_hash:
            raise PinError(
                f"amendment {i} supplies something other than a sha256 for: "
                + ", ".join(bad_hash))

        current = sorted(set(a["new_pin_set"]))
        last_cycle = int(a["effective_cycle"])


def frozen_assignments(review_dir: Path) -> dict[int, list[str]]:
    """What each already-frozen cycle recorded as governing it.

    B02-F06. Written into target.json at freeze from this point on. Cycles
    frozen before the field existed are absent from this map and are not
    retro-checked: an amendment cannot be judged against a record nobody kept.
    That gap is real and shrinks to nothing as cycles accumulate, but it is a
    gap, and saying otherwise would overstate what this establishes.
    """
    out: dict[int, list[str]] = {}
    if not review_dir.is_dir():
        return out
    for d in sorted(review_dir.glob("cycle-*")):
        t = d / "target.json"
        if not t.is_file():
            continue
        try:
            data = json.loads(t.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pins = data.get("governing_pins")
        if isinstance(pins, list) and data.get("cycle") is not None:
            out[int(data["cycle"])] = sorted(pins)
    return out


def check_frozen_assignments(run: dict, items: list[dict],
                             frozen: dict[int, list[str]]) -> None:
    """Refuse amendments that would change what a completed cycle ran under.

    Alex Zamurko ruled that once a cycle exists its effective pin set is fixed
    and later amendments apply only prospectively. Comparing each amendment
    against the previous one, as the first version did, only ensured the numbers
    increased. It said nothing about cycles that had already happened.

    Stated at its real strength: the frozen cycle records what governed it, and
    an amendment whose replay contradicts that record is refused. That is
    detection, and it holds while the checks run faithfully. It is not
    protection — under MC1_ENFORCEMENT: CONVENTION_ONLY nothing stops someone
    editing the recorded set in target.json, at which point the two agree again
    and this check has nothing to say.
    """
    for n, recorded in sorted(frozen.items()):
        replayed = pins_for_cycle(run, items, n)
        if replayed != recorded:
            raise PinError(
                f"the amendment history no longer reproduces what cycle "
                f"{n:02d} recorded as governing it.\n"
                f"    cycle {n:02d} recorded  {recorded}\n"
                f"    replay now gives    {replayed}\n"
                "  A completed cycle was conducted under a specific set. An "
                "amendment that changes\n  it is rewriting the conditions of a "
                "review that already happened, which is what\n  the effective "
                "cycle boundary exists to prevent.")


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


def governing_pins(run: dict, run_dir: Path, cycle_n: int,
                   review_dir: Path | None = None) -> list[str]:
    items = load_amendments(run_dir)
    validate_chain(run, items)
    if review_dir is not None:
        check_frozen_assignments(run, items, frozen_assignments(review_dir))
    return pins_for_cycle(run, items, cycle_n)


def pin_hashes_for_cycle(run: dict, items: list[dict],
                         cycle_n: int) -> dict[str, str]:
    """path -> sha256 for the whole effective set, not only run.json's entries.

    B02-F05. check_pins_still_hold walked the protocol and run["spec_files"],
    which meant an artifact introduced by an amendment was in the governing set
    and checked by nothing. The hash for an added pin comes from the amendment
    that introduced it, which is why added_pin_hashes is mandatory there.
    """
    out = {run["protocol"]["path"]: run["protocol"]["sha256"]}
    for e in run.get("spec_files", []):
        out[e["path"]] = e["sha256"]
    for a in items:
        if int(a["effective_cycle"]) <= cycle_n:
            out.update(a.get("added_pin_hashes") or {})
    return {p: h for p, h in out.items()
            if p in set(pins_for_cycle(run, items, cycle_n))}


def separation_violations(pins: list[str], targets: list[str]) -> list[str]:
    """Artifacts asked to be invariant and under review at the same time.

    §2 of the specification: the same artifact version must not serve as both an
    immutable run-governing input and a mutable review candidate. Without
    explicit ACTIVE/CANDIDATE version separation an artifact belongs to exactly
    one role.
    """
    return sorted(set(pins) & set(targets))
