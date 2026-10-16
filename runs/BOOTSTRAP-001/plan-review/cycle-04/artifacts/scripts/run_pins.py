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

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "run-pin-amendments/1"
MIN_REASON = 30


class PinError(Exception):
    """The pin history cannot be read, or does not describe a coherent chain."""


def spec_digest(entries: list[dict]) -> str:
    """One digest over a set of pinned artifacts.

    SHA-256 of "path:sha256\\n" lines, sorted by path. Defined so it is
    reproducible by anyone auditing a run rather than only by the script that
    happened to write it.

    B01-F07. It lived in run_review.py, which meant the MC-2 gate could not
    check a recorded spec digest without either importing the runner it is
    invoked by, or growing a second implementation of this format. Two
    implementations of one rule is B02-F03, where the schema and the ledger each
    had their own idea of a valid identifier and quietly disagreed.

    Here because a digest over a pin set is a fact about the pin set.
    """
    body = "".join(f"{e['path']}:{e['sha256']}\n"
                   for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- run metadata

# MC-1 names the status; these are the values it can take. Enumerated so a typo
# or an invented reassurance is refused rather than recorded: a run claiming
# "ENFORCED" would read as a stronger guarantee than anything here supports.
MC1_VALUES = ("CONVENTION_ONLY", "TECHNICALLY_ENFORCED")


def mc1_enforcement_problem(run: dict) -> str | None:
    """None if run.json records a usable MC1_ENFORCEMENT, else why not.

    B01-F14, the half cycle 03 found still open. The runner validated this in
    load_run, and the controller read run.json separately through
    run_classification and looked only at the bootstrap label. Codex removed
    mc1_enforcement from a normal approved run after a valid cycle and the
    controller printed an unqualified "LOOP_STATUS: CONVERGED". The field was
    mandatory to create and freeze a run, and optional to conclude one.

    Codex asked for the rule to be SHARED rather than implemented twice:
    "Share mandatory run-metadata validation across authoritative consumers."
    Two copies of a rule is B02-F03, where the schema and the ledger each had
    their own idea of a valid identifier and disagreed.

    It returns a message instead of raising because the two callers report
    differently: the runner refuses an operation, the controller refuses to
    state an outcome. Sharing the rule should not mean sharing an exception
    type.

    It lives here rather than in a module of its own because a new file would
    join the gate's covered set and invalidate the standing bootstrap approval.
    If the run-metadata rules grow past this one field, they deserve their own
    home and that re-approval.
    """
    status = str(run.get("mc1_enforcement", "")).strip()
    if not status:
        return ("run.json records no mc1_enforcement.\n"
                "  MC-1 requires every run to record the enforcement status it "
                "was conducted under.\n  A reader of this evidence would have to "
                "go looking elsewhere, and the answer\n  would be today's rather "
                "than the run's.\n"
                "  If this run predates the field, add it with a note saying it "
                "was reconstructed,\n  rather than writing it as though it had "
                "always been there.")
    if status not in MC1_VALUES:
        return (f"run.json records mc1_enforcement {status!r}, which is not a "
                f"recognised status.\n  Expected one of: "
                f"{', '.join(MC1_VALUES)}")
    return None


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

    B02-F05, Alex Zamurko 10 September: "constrain amendments by role. The
    governing protocol cannot be removed; added pins must be validated; only
    explicitly permitted pin roles may change." The first version accepted any
    structurally valid change, so an amendment could drop the protocol out of
    the governing set entirely, or add a path that no check ever looked at
    because the pin check iterated only what run.json originally recorded.

    It does NOT check amendments against cycles that have already been frozen.
    It took a `frozen` argument that promised exactly that and then ignored it,
    so the docstring described a check the body did not perform. The real one is
    check_frozen_assignments, and the argument is gone rather than left here
    looking like coverage.
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

        # B02-F05, the half cycle 03 found still open. Both checks above look
        # only at `added`, so any other key in the map went unexamined, and
        # pin_hashes_for_cycle applied the whole dictionary. Codex: "An
        # amendment can change the protocol bytes accepted by the pin checker
        # without declaring a protocol change, without removing the protocol
        # path and without changing run.json."
        #
        # Keeping the protocol's PATH is not keeping its version. The role
        # constraint this file exists to enforce was bypassable through the very
        # hash mechanism added to enforce it.
        stray = sorted(set(hashes) - set(added))
        if stray:
            raise PinError(
                f"amendment {i} supplies hashes for artifact(s) it does not "
                "add:\n    " + "\n    ".join(stray) +
                "\n  added_pin_hashes binds the bytes of NEW pins only. A hash "
                "for a retained artifact\n  is a version change arriving as a "
                "dictionary key rather than being declared as one.\n"
                "  If the intent is to change what governs, say so in "
                "affected_artifacts and let the\n  role constraints apply to it.")

        current = sorted(set(a["new_pin_set"]))
        last_cycle = int(a["effective_cycle"])


def frozen_assignments(run_dir: Path) -> list[dict]:
    """What every already-frozen cycle in the RUN recorded as governing it.

    B02-F06, the half cycle 03 found still open. This used to take one review
    directory, and freeze handed it the directory it happened to be working in.
    The amendment history is a property of the whole run, so freezing
    implementation-review/cycle-01 never looked at plan-review/cycle-01. Codex
    froze a plan cycle under protocol plus spec, appended an amendment effective
    at cycle 1 removing the spec, froze the implementation cycle, and the
    implementation freeze exited 0. The earlier frozen assignment was never
    examined on that path.

    Each record keeps the review it came from. A map keyed by cycle number would
    let implementation-review/cycle-01 overwrite plan-review/cycle-01 and
    silently discard one of the two records this check exists to compare
    against — and those two are precisely the pair that disagree when an
    amendment has been backdated across loops.

    The recorded hashes come back as well as the paths. Cycles frozen before
    either field existed have neither, and are absent here rather than
    retro-checked: an amendment cannot be judged against a record nobody kept. A
    cycle that recorded paths but not hashes is checked on paths alone. Both
    gaps are real, they shrink as cycles accumulate, and saying otherwise would
    overstate what this establishes.
    """
    out: list[dict] = []
    if not run_dir.is_dir():
        return out
    for review in sorted(run_dir.glob("*-review")):
        if not review.is_dir():
            continue
        for d in sorted(review.glob("cycle-*")):
            t = d / "target.json"
            if not t.is_file():
                continue
            try:
                data = json.loads(t.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            pins = data.get("governing_pins")
            if not isinstance(pins, list) or data.get("cycle") is None:
                continue
            h = data.get("governing_pin_hashes")
            out.append({
                "review": review.name,
                "cycle": int(data["cycle"]),
                "where": f"{review.name}/{d.name}",
                "paths": sorted(pins),
                "hashes": dict(h) if isinstance(h, dict) and h else None,
            })
    return out


def check_frozen_assignments(run: dict, items: list[dict],
                             frozen: list[dict]) -> None:
    """Refuse amendments that would change what a completed cycle ran under.

    Alex Zamurko ruled that once a cycle exists its effective pin set is fixed
    and later amendments apply only prospectively. Comparing each amendment
    against the previous one, as the first version did, only ensured the numbers
    increased. It said nothing about cycles that had already happened.

    The effective-cycle coordinate, written down because cycle 03 found it
    undefined across the two loops. `effective_cycle` is a RUN-level ordinal.
    Nothing in an amendment names a review type, and the history lives at the
    run root, so an amendment effective at cycle k governs cycle k onward in
    every review directory the run has. Reading it as "plan-review's cycle k"
    is what let the implementation loop freeze against a history contradicting a
    plan cycle already conducted. One consequence follows and is worth stating:
    two review directories that recorded different sets for the same cycle
    number cannot both be right, and at least one of them is refused here.

    Stated at its real strength: the frozen cycle records what governed it, and
    an amendment whose replay contradicts that record is refused. That is
    detection, and it holds while the checks run faithfully. It is not
    protection — under MC1_ENFORCEMENT: CONVENTION_ONLY nothing stops someone
    editing the recorded set in target.json, at which point the two agree again
    and this check has nothing to say.
    """
    for rec in sorted(frozen, key=lambda r: (r["cycle"], r["review"])):
        n, where = rec["cycle"], rec["where"]
        replayed = pins_for_cycle(run, items, n)
        if replayed != rec["paths"]:
            raise PinError(
                f"the amendment history no longer reproduces what "
                f"{where} recorded as governing it.\n"
                f"    {where} recorded  {rec['paths']}\n"
                f"    replay now gives  {replayed}\n"
                "  A completed cycle was conducted under a specific set. An "
                "amendment that changes\n  it is rewriting the conditions of a "
                "review that already happened, which is what\n  the effective "
                "cycle boundary exists to prevent.")

        recorded = rec["hashes"]
        if recorded is None:
            continue

        # The second half of B02-F06. This compared path lists and dropped
        # governing_pin_hashes on the floor, so a changed digest with unchanged
        # membership passed: same names, different documents. A pin set is a set
        # of versions, and checking only the names checks the easier thing.
        now = pin_hashes_for_cycle(run, items, n)
        moved = [p for p in sorted(recorded)
                 if str(now.get(p, "")) != str(recorded[p])]
        if moved:
            lines = "\n".join(
                f"    {p}\n      {where} recorded  {recorded[p]}\n"
                f"      replay now gives  {now.get(p) or '(absent)'}"
                for p in moved)
            raise PinError(
                f"the amendment history reproduces {where}'s governing paths "
                f"but not its versions.\n" + lines +
                "\n  Membership is unchanged, which is why the path check above "
                "passed. Same names and\n  different bytes is a different set "
                "of documents to have reviewed against, and the\n  cycle that "
                "already happened cannot be re-conducted against them.")


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
    """The effective pin set, with the whole history checked before it is used.

    The frozen check is no longer optional. It was reachable only when a caller
    remembered to pass a review directory, and the caller that forgot is how
    B02-F06 survived its first repair. A history that contradicts a completed
    cycle is not a history any caller should be handed an answer from.
    """
    items = load_amendments(run_dir)
    validate_chain(run, items)
    check_frozen_assignments(run, items, frozen_assignments(run_dir))
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

    # B02-F05. `out.update(...)` applied every key the amendment carried, which
    # is what turned an unvalidated dictionary entry into a governing hash.
    # Only the paths an amendment actually adds are taken from it.
    #
    # Deliberately not relying on validate_chain having refused the stray keys
    # first. Replay is reachable from callers that have not validated, and a
    # function that is safe only because something else ran is the shape of most
    # of the findings in this ledger.
    seen = set(initial_pin_set(run))
    for a in items:
        proposed = set(a["new_pin_set"])
        if int(a["effective_cycle"]) <= cycle_n:
            added = proposed - seen
            out.update({p: h
                        for p, h in (a.get("added_pin_hashes") or {}).items()
                        if p in added})
        seen = proposed

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
