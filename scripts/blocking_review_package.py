#!/usr/bin/env python3
"""Assemble what a protocol reviewer needs to examine the blocking defects.

    python scripts/blocking_review_package.py

Writes specs/BLOCKING-REVIEW-PACKAGE.md. Exit 0 = every item was assembled
from a source. Exit 1 = at least one claim could not be sourced, and the
document says which rather than omitting it.

Why a generator and not a document
-----------------------------------
A hand-written package is true on the day it is written. This one is
assembled from the files that decide the answers, so it cannot drift from
them without the drift being visible: the classification, the ledgers, the
register, the mutation set, the suites, and the recorded execution evidence.

What the reviewer is being asked for, and why it cannot come from here
-----------------------------------------------------------------------
Ten defects are classified blocking. EC-1 and EC-4 both report them open and
both read `independently_examined_in_cycle`, which is filled when a protocol
cycle examines the repair.

No protocol cycle has ever been run. All three bootstrap runs are marked
NOT_A_PROTOCOL_CYCLE, and by Alex Zamurko's instruction of 10 September 2026
their evidence "can never accidentally count as authoritative protocol
evidence". scripts/reconcile_blocking.py establishes the position of each
item against the controller's own walk and refuses to write any of it into
that field.

So this document is the input to a review that has not happened, not a
substitute for it. Everything in it was written by the party whose work is
being reviewed, which is exactly why it is assembled mechanically and why
every section ends by saying what it does not establish.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
SPECS = REPO / "specs"
PROBE = REPO / "_probe"
OUT = SPECS / "BLOCKING-REVIEW-PACKAGE.md"

sys.path.insert(0, str(PROBE))


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def mutations_for(fid: str) -> list[str]:
    """Mutation entries whose name begins with this identifier.

    Imported rather than parsed. The tuples are the authority on what is
    watched, and a regex over the source would be a second reading of the
    same list, free to disagree with the first.
    """
    try:
        import mutate_repairs
    except Exception as e:  # noqa: BLE001 - reported, not swallowed
        return [f"!! the mutation set could not be read: {e}"]
    out = []
    for m in getattr(mutate_repairs, "MUTATIONS", []):
        name = str(m[0])
        # "SELF-F29  a declared finding ..." and "D02-F01b  a fenced block".
        # The boundary matters: D02-F01 must not claim D02-F01b's entry, so
        # the character after the identifier has to be a space.
        if name.startswith(fid + " "):
            out.append(f"{name}   [{m[4]}]")
    return out


def controls_for(fid: str) -> list[str]:
    """Suites whose text names this identifier, with one example line.

    Naming is what the project's own convention gives us. A suite that holds
    a control for a finding says the identifier, because that is how the
    mutation probe attributes a red run to a repair. It is a convention and
    not a guarantee, and the section says so.
    """
    hits = []
    for s in sorted(SCRIPTS.glob("test_*.py")):
        try:
            text = s.read_text(encoding="utf-8")
        except OSError:
            continue
        if fid not in text:
            continue
        line = next((ln.strip() for ln in text.splitlines()
                     if fid in ln and ln.strip().startswith(("#", "ok(", '"'))),
                    "")
        hits.append(f"{s.name}" + (f"   {line[:90]}" if line else ""))
    return hits


def evidence_for(fid: str, candidate: str, runs: list[dict]) -> list[str]:
    """Recorded runs whose preserved output names this identifier.

    Read out of the preserved log, not out of the record's `covers` field.
    That is EC-4's own rule since 15 October, and the reason is that a
    coverage claim is a thing somebody typed.
    """
    out = []
    for r in runs:
        log = REPO / str(r.get("log", ""))
        if not log.is_file():
            continue
        try:
            body = log.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(body).hexdigest() != r.get("log_sha256"):
            out.append(f"run {r.get('run_id')}: its preserved log no longer "
                       f"matches the digest recorded with it")
            continue
        if fid not in body.decode("utf-8", "replace"):
            continue
        same = str(r.get("commit", "")).lower() == candidate.lower()
        out.append(
            f"run {r.get('run_id')} on {str(r.get('commit'))[:12]}"
            + ("" if same else "   NOT the frozen candidate, so EC-4 does "
                               "not count it")
            + f"\n      {r.get('url')}")
    return out


def main() -> int:
    blocking = load(SPECS / "blocking-defects.json").get("blocking") or {}
    if not blocking:
        print("  nothing is classified as blocking")
        return 1
    register = load(REPO / "registers" / "implementer-disclosed.json")
    entries = register.get("entries") or {}
    ledgers = {p.parent.parent.name: load(p)
               for p in sorted((REPO / "runs").glob("*/plan-review/"
                                                    "ledger.json"))}
    cand = str(load(SPECS / "frozen-candidate.json").get("commit", ""))
    runs = load(REPO / "evidence" / "execution-evidence.json").get("runs") or []

    gaps: list[str] = []
    w: list[str] = []
    W = w.append

    W("# The blocking defects, assembled for a protocol review")
    W("")
    W("Generated by `scripts/blocking_review_package.py`. Do not edit: every")
    W("line below is read from the file that decides it, so an edit here")
    W("would be a claim nothing checks.")
    W("")
    W(f"Frozen candidate: `{cand or 'none'}`")
    W("")
    W("## What is being asked")
    W("")
    W("Ten defects are classified blocking by Alex Zamurko. EC-1 and EC-4")
    W("both report them open, and both read "
      "`independently_examined_in_cycle`,")
    W("which is filled when a protocol cycle examines the repair.")
    W("")
    W("No protocol cycle has ever been run. All three bootstrap runs are")
    W("marked `NOT_A_PROTOCOL_CYCLE`, and on his instruction of 10 September")
    W("2026 their evidence \"can never accidentally count as authoritative")
    W("protocol evidence\". So no amount of further work inside them can")
    W("close any of these ten, and `scripts/reconcile_blocking.py` refuses")
    W("to write a cycle number taken from a development walk.")
    W("")
    W("This document is the input to that review. It was assembled by the")
    W("party whose work is under review, which is why it is generated rather")
    W("than written and why each item ends with what it does not establish.")
    W("")

    for fid in sorted(blocking):
        item = blocking[fid]
        where = str(item.get("where", ""))
        W(f"## {fid}")
        W("")
        W(f"- classified blocking for **{item.get('condition', '?')}**, "
          f"ruled {item.get('ruled', 'see the classification file')}")
        W(f"- recorded in: {where}")
        W("")
        W("**Why it is blocking, in Alex Zamurko's words**")
        W("")
        W("> " + str(item.get("why", "(no reason recorded)")))
        W("")

        run_name = next((r for r in ledgers
                         if fid in (ledgers[r].get("findings") or {})), "")
        if run_name:
            f = ledgers[run_name]["findings"][fid]
            W(f"**What the ledger holds** ({run_name})")
            W("")
            W(f"- class: {f.get('class', '-')}, raised in cycle "
              f"{f.get('cycle_raised', '?')}")
            hist = f.get("history") or []
            W(f"- history: " + ", ".join(
                f"{h.get('event')}({h.get('cycle')})" for h in hist) or "-")
            rs = f.get("repair_status")
            if rs:
                W(f"- repair_status: `{rs}`. ledger.py lists this in")
                W("  NON_AUTHORITATIVE_FIELDS, so it records what somebody")
                W("  wrote about the repair and establishes nothing about")
                W("  whether a reviewer examined it.")
            W("")
        elif fid in entries:
            e = entries[fid]
            W("**What the register holds**")
            W("")
            W(f"- state: `{e.get('state', '?')}`")
            W(f"- {str(e.get('description', ''))[:600]}")
            W("")
            W("**The repair as proposed**")
            W("")
            W(str(e.get("proposed_repair", "(none recorded)"))[:900])
            W("")
            if e.get("residual"):
                W("**What the repair leaves behind**")
                W("")
                W(str(e["residual"])[:700])
                W("")
        else:
            gaps.append(f"{fid}: no ledger and no register entry holds it")
            W("**NOT SOURCED.** No ledger and no register entry holds this")
            W("identifier, so nothing below can be derived for it.")
            W("")

        ctrls = controls_for(fid)
        W("**Controls that name it**")
        W("")
        if ctrls:
            for c in ctrls:
                W(f"- `{c}`")
        else:
            gaps.append(f"{fid}: no suite names it")
            W("- **none.** No suite in `scripts/` mentions this identifier.")
            W("  That does not prove the repair is untested, because a")
            W("  control can hold a rule without naming the finding, but it")
            W("  does mean a reviewer has nothing to follow from here.")
        W("")

        muts = mutations_for(fid)
        W("**Mutations watching it**")
        W("")
        if muts:
            for m in muts:
                W(f"- {m}")
        else:
            gaps.append(f"{fid}: no mutation names it")
            W("- **none names it.** No entry in the mutation set begins with")
            W("  this identifier. That is not the same as the repair being")
            W("  unwatched: a mutation can guard a rule under the identifier")
            W("  of the cycle that raised it rather than the finding's own,")
            W("  and the controls listed above may well be the ones that go")
            W("  red. What it does mean is that a reviewer following this")
            W("  identifier through the mutation set finds nothing, and that")
            W("  the sweep's output never mentions it, which is why no")
            W("  execution evidence can name it either.")
            W("")
            W("  EC-2's reserved judgement is whether the mutation set")
            W("  covers the repairs that matter. This is one of the places")
            W("  that question lands.")
        W("")

        ev = evidence_for(fid, cand, runs)
        W("**Execution evidence naming it**")
        W("")
        if ev:
            for x in ev:
                W(f"- {x}")
        else:
            W("- none. No recorded run's preserved output names it.")
        W("")
        W("**What this section does not establish**")
        W("")
        W("That the repair is correct, that the controls are good controls,")
        W("or that the mutation aims at the right line. All three were")
        W("written by the implementing agent. A green sweep shows the")
        W("repairs are watched, not that they are right, and that")
        W("distinction is the whole reason this review is being asked for.")
        W("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(w) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO).as_posix()}, {len(blocking)} item(s)")

    if gaps:
        print(f"\n  {len(gaps)} item(s) could not be fully sourced, and the")
        print("  document says so rather than omitting them:")
        for g in gaps:
            print(f"    {g}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
