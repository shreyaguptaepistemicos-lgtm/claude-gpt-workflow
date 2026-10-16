#!/usr/bin/env python3
"""Assemble the §7 human review package for a run.

    python scripts/approval_package.py --run BOOTSTRAP-002 --type plan
    python scripts/approval_package.py --run BOOTSTRAP-002 --type plan --out PACKAGE.md

Exit 0 = a package was written, and it states which §7 items it could not fill.
Exit 1 = refused; nothing written.

Why this exists
---------------
§7 requires a human to review the plan after CONVERGED, HUMAN_ADJUDICATION_REQUIRED,
STALLED or MAX_4_REACHED, and lists ten things the package must contain. Nothing
built them. The consequence was not that approval was hard, it was that approval
had no defined subject: a human was being asked to approve a directory.

Every figure here is taken from the tool that owns it, by running that tool and
quoting what it said. None of it is recomputed locally. That is the whole design:
a package that recomputed loop status would be a second controller, and two
implementations of one rule is the defect this layer keeps finding in itself. If
a tool refuses, the refusal is what the package records — not a gap, and not a
guess at what the answer would have been.

What it does not do
-------------------
It does not decide anything, and it writes nothing into any ledger. The decision
is recorded by `bootstrap_gate.py record`, which is a separate act by a separate
person.

It cannot produce the SPEC → CODE → TEST mapping of §7 for a bootstrap run,
because that mapping is the output of a §1 plan audit and a bootstrap run has no
plan. It says so rather than leaving the heading out, because a reviewer who
cannot see what is missing cannot weigh it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
# C01-F05: the bootstrap classification rule is shared with the runner and the
# controller rather than spelled out here. This file had its own
# `.startswith("EXEMPT")`, which made a missing or unrecognised label produce a
# package carrying no qualification at all.
import run_pins  # noqa: E402
# For `authoritative_items` only: what a cycle's review reported, read by the
# controller's own reader so this file cannot develop a second opinion about
# it. See the reconciliation under SELF-F01 below.
import loop_state  # noqa: E402

# The ten items §7 names, in its order. Presence is reported against this list
# rather than against whatever the package happened to manage, so an item that
# silently stopped being produced shows up as absent instead of disappearing.
SECTION_7_ITEMS = (
    "final plan",
    "final plan hash",
    "loop status",
    "valid iteration count",
    "SPEC -> CODE -> TEST mapping",
    "resolved findings",
    "disputes",
    "unresolved findings",
    "MC-1 enforcement status",
    "MC-2 conformance results for every valid cycle",
)


class Refused(Exception):
    """Exit 1, write nothing."""


def run_tool(*args: str) -> tuple[int, str]:
    """Run one of this repo's tools and return exactly what it said."""
    r = subprocess.run([sys.executable, *args], cwd=str(REPO),
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).rstrip()


def quote(text: str) -> str:
    return "```text\n" + (text if text.strip() else "(no output)") + "\n```"


def load_run(run_id: str) -> dict:
    p = REPO / "runs" / run_id / "run.json"
    if not p.is_file():
        raise Refused(f"no run.json for {run_id}. A package describes a run; "
                      f"this one has no record.\n  expected {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"{p} is not valid JSON: {e}")


def cycles(review: Path) -> list[Path]:
    return sorted(d for d in review.glob("cycle-*") if d.is_dir())


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="approval_package.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--type", required=True, choices=("plan", "implementation"))
    ap.add_argument("--out", default="",
                    help="default: runs/<run>/<type>-review/APPROVAL-PACKAGE.md")
    a = ap.parse_args()

    run = load_run(a.run)
    review = REPO / "runs" / a.run / f"{a.type}-review"
    if not review.is_dir():
        raise Refused(f"no {a.type} review for {a.run}: {review} does not exist")

    cy = cycles(review)
    if not cy:
        raise Refused(f"{review} has no frozen cycles. There is nothing to "
                      "approve yet.")

    present: dict[str, bool] = {k: False for k in SECTION_7_ITEMS}
    out: list[str] = []
    W = out.append

    W(f"# Human review package — {a.run}, {a.type} review")
    W("")
    W("Assembled by `scripts/approval_package.py` from the run's own records. "
      "Every figure below is quoted from the tool that owns it; none is "
      "recomputed here.")
    W("")
    W("**This package decides nothing.** The decision is recorded separately, "
      "by a person, with `bootstrap_gate.py record`. §7.3 permits exactly three "
      "outcomes: `APPROVE`, `RETURN_FOR_REWORK`, `REJECT`.")
    W("")

    # ---- MC-1, §7 item 9. Read from the run, not assumed. ----
    W("## MC-1 enforcement status")
    W("")
    mc1 = run.get("mc1_enforcement")
    if mc1:
        present["MC-1 enforcement status"] = True
        W(f"`{mc1}`")
        if mc1 == "CONVENTION_ONLY":
            W("")
            W("Every check in this layer is detection that holds while the "
              "checks run faithfully and nobody edits the records they read. "
              "The same writable code performs the checks on itself. Nothing "
              "here is technically enforced.")
    else:
        W("**Absent from run.json.** The run does not record one, so this "
          "package cannot state it.")
    prov = run.get("mc1_enforcement_provenance")
    if prov:
        W("")
        W("Reconstructed rather than recorded at the time:")
        W("")
        W(quote(json.dumps(prov, indent=2)))
    W("")

    # C01-F05: one classification rule, shared with the runner and the
    # controller. The banner used to hang on `.startswith("EXEMPT")`, so a run
    # whose label was missing or unrecognised produced a package with no
    # qualification at all — which is the strongest thing this document can
    # say, reached by saying nothing.
    _kind, _problem = run_pins.run_kind(run)
    if _problem:
        W("> **This run's classification is not established.** " + " ".join(
            _problem.split()) + " Nothing in this package may be cited as a "
            "protocol result until that is recorded.")
        W("")
    elif _kind == run_pins.DEVELOPMENT:
        W("> **Development evidence, not a protocol outcome.** This run is "
          "marked `NOT_A_PROTOCOL_CYCLE`. Nothing in this package may be cited "
          "as a protocol result.")
        W("")

    # ---- loop status + valid iteration count, §7 items 3 and 4 ----
    W("## Loop status and valid iteration count")
    W("")
    args_loop = [str(SCRIPTS / "loop_state.py"), "--review", str(review)]
    # Whether the authoritative run was refused and the development one used
    # instead. The findings section below asks the same controller for the same
    # boundary and must ask it the same way, or it would be reporting a
    # different run's arithmetic than the status above it.
    _loop_dev = False
    rc, text = run_tool(*args_loop)
    if rc != 0 and "--development" in text:
        _loop_dev = True
    if rc != 0 and "--development" in text:
        W("The controller refuses to state an authoritative loop result for "
          "this run, and says why:")
        W("")
        W(quote(text))
        W("")
        W("Recomputed with `--development`. The result is labelled and is not "
          "a protocol outcome:")
        W("")
        rc, text = run_tool(*args_loop, "--development")
    if rc == 0:
        present["loop status"] = True
        present["valid iteration count"] = "-> n=" in text or "VALID" in text
    W(quote(text))
    W("")

    # ---- findings, §7 items 6, 7, 8. Presented separately, per §7.2. ----
    W("## Findings")
    W("")
    rc, led = run_tool(str(SCRIPTS / "ledger.py"), "show", "--review", str(review))
    ledger_json = review / "ledger.json"
    # SELF-F01, Alex Zamurko's ruling of 5 October: "Require the ledger whenever
    # frozen review cycles exist. If the ledger is missing, unreadable, or
    # inconsistent, return an explicit failure state such as CANNOT_ESTABLISH.
    # Never translate missing evidence into zero findings."
    #
    # Until now this branch wrote a paragraph saying no review had reported and
    # produced the package anyway. The paragraph was accurate and the package
    # was the problem: a document headed "approval package" with nothing under
    # the findings headings reads as a clean result to anyone who skims it, and
    # the gate is read by people in a hurry. Absence of evidence had become
    # evidence of absence, one heading at a time.
    #
    # `show` exits 0 on a review with no ledger, saying so in prose, so the
    # file's existence is checked separately. That zero was read as an answer it
    # was not giving once before, and it crashed this tool rather than lying,
    # which is the luckier of the two outcomes.
    _bad = ("could not be read" if rc != 0 else
            "is missing" if not ledger_json.is_file() else "")
    if not _bad:
        try:
            _led = json.loads(ledger_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            _bad = f"is not readable as a ledger: {e}"
        else:
            # BOOTSTRAP-003, D01's review of SELF-F01: "a readable ledger
            # containing `{"findings": {}}` beside a valid review reporting a
            # finding still produces an approval package with exit 0... the
            # unresolved-findings section says 'None' and its coverage item is
            # marked present. Reconcile findings before asserting empty
            # categories."
            #
            # The repair stopped at missing and unparseable, which are the two
            # ways a ledger can fail to be read. A ledger that reads perfectly
            # and disagrees with the reviews beside it is the third, and it is
            # the one that produces a confident wrong answer instead of an
            # error.
            #
            # The recorded findings come from loop_state's own reader rather
            # than a second one written here. A second implementation of "what
            # did this cycle report" is free to disagree with the first, which
            # is the defect this layer has found in itself repeatedly.
            _held = set(_led.get("findings", {}))
            _absent = {}
            # authoritative_items refuses a cycle whose record it cannot read
            # at all, and that refusal used to leave here as an unhandled
            # exception: the operator got a Python stack trace naming a line
            # number instead of a stated reason, and the one reader this tool
            # has is the person deciding. A crash and a refusal are not the
            # same act. Both withhold the document, only one says why.
            try:
                for _c in cy:
                    for _item in loop_state.authoritative_items(_c):
                        _fid = _item.get("id")
                        if _fid and _fid not in _held:
                            _absent.setdefault(_c.name, []).append(_fid)
            except loop_state.CannotCalculate as e:
                raise Refused(
                    "FINDINGS_STATE: CANNOT_ESTABLISH\n"
                    "  A frozen cycle's own record of what the reviewer found "
                    "cannot be read, so\n  there is nothing to reconcile the "
                    "ledger against. The controller says:\n\n" + quote(str(e)))
            if _absent:
                _bad = ("holds none of what the reviews beside it reported: "
                        + "; ".join(f"{k} reported {', '.join(v)}"
                                    for k, v in sorted(_absent.items())))
    if _bad:
        raise Refused(
            f"FINDINGS_STATE: CANNOT_ESTABLISH\n"
            f"  {review.name} has {len(cy)} frozen cycle(s) and its ledger "
            f"{_bad}.\n"
            "  A package cannot be produced. With cycles frozen, the ledger is "
            "the only record of\n  what a reviewer found, so without it this "
            "tool cannot distinguish a review that\n  found nothing from a "
            "review that never reported. Those are opposite states and a\n"
            "  package that stays quiet presents the second as the first.\n"
            "  Record the review first, or repair the ledger, then build the "
            "package.\n\n"
            + quote(led))
    else:
        # Marked present only on the branch that actually produced them. The
        # coverage table is only worth reading if it cannot be satisfied by a
        # heading with nothing under it.
        present["resolved findings"] = True
        present["unresolved findings"] = True
        present["disputes"] = True
        W("§7.2 requires disputes and unresolved findings to be presented "
          "separately. They are separate headings below; the full ledger "
          "follows both.")
        W("")
        data = json.loads((review / "ledger.json").read_text(encoding="utf-8"))

        # SELF-F01, third pass. Alex Zamurko, 8 October: "The package must
        # derive finding state from the controller's reconstructed state, not
        # stale cached ledger state."
        #
        # This used to read `f["state"]`, the value the ledger caches when an
        # event is written. That value is not recomputed when a cycle becomes
        # invalid, so BOOTSTRAP-003 cycle 02 invalidated the cycle carrying a
        # demonstration, left the stale RESOLVED in place, and watched the
        # controller say OPEN and CONTINUE while this package said "None"
        # under unresolved findings and counted one resolved. The reporting
        # layer presented a cleaner state than the authoritative one, which is
        # the worst direction for the error to point.
        #
        # The sets now come from the controller's own boundary walk, asked for
        # in JSON rather than restated here or parsed out of its prose. If it
        # cannot establish a state, neither can this package.
        _lj = run_tool(*args_loop, "--json",
                       *(["--development"] if _loop_dev else []))
        if _lj[0] != 0:
            raise Refused(
                "FINDINGS_STATE: CANNOT_ESTABLISH\n"
                "  The controller cannot establish the loop state for this "
                "review, so there is no\n  authoritative state to sort the "
                "findings into. The ledger's own `state` fields are\n  not an "
                "answer: they are what was true when each event was written, "
                "and a cycle\n  invalidated since leaves them saying so "
                "anyway.\n\n" + quote(_lj[1]))
        try:
            _proj = json.loads(_lj[1])
        except json.JSONDecodeError as e:
            raise Refused(
                f"FINDINGS_STATE: CANNOT_ESTABLISH\n"
                f"  The controller's machine-readable result could not be "
                f"read: {e}")
        # SELF-F04. The controller exits 0 when no cycle is valid, because
        # "no valid cycle exists" is an answer rather than a failure, and it
        # reports no sets in that case. Read through `.get(..., [])` below,
        # absent sets would have become empty ones, and the package would have
        # printed None under unresolved findings for a run whose boundary was
        # never walked. That is SELF-F01's defect arriving by a different road,
        # which is why it is tested here and not assumed away.
        if not _proj.get("sets_established"):
            raise Refused(
                "FINDINGS_STATE: CANNOT_ESTABLISH\n"
                "  The controller established no finding sets for this review, "
                "and said so.\n  It reports: "
                + str(_proj.get("detail", "(no detail given)")) +
                "\n\n  No category is printed from that. An absent set is not "
                "an empty one, and a\n  package that showed them as empty "
                "would be describing a boundary nobody walked.")
        by_state: dict[str, list[str]] = {
            "OPEN": list(_proj.get("open", [])),
            "RESOLVED": list(_proj.get("resolved", [])),
            "DISPUTED": list(_proj.get("disputed", [])),
        }
        # A finding in the ledger that the governing boundary places in none of
        # the three. The controller refuses that case for findings a review
        # reported, so reaching it here means something it does not police, and
        # the honest thing is to show it rather than drop it.
        _placed = (set(by_state.get("OPEN", ())) | set(by_state.get("RESOLVED", ()))
                   | set(by_state.get("DISPUTED", ())))
        _unplaced = [k for k in sorted(data.get("findings", {}))
                     if k not in _placed]
        W(f"States below are reconstructed by the controller at its governing "
          f"boundary, n={_proj.get('governing_boundary', '?')}, not read from "
          f"the ledger's cached fields.")
        W("")
        if _unplaced:
            W("> **" + ", ".join(_unplaced) + "** "
              + ("is" if len(_unplaced) == 1 else "are")
              + " in the ledger and in none of the three sets at that "
                "boundary. Not counted below, and named here rather than "
                "omitted.")
            W("")

        W("### Unresolved findings — the human decides each one")
        W("")
        W("§7.2: the human determines whether each requires correction, is "
          "explicitly waived or accepted, or causes rejection of the plan.")
        W("")
        openers = by_state.get("OPEN", [])
        if not openers:
            W("None.")
        for fid in openers:
            f = data["findings"][fid]
            line = f"- **{fid}** · {f.get('class','?')}"
            if f.get("requirement_id"):
                line += f" · {f['requirement_id']}"
            W(line)
            if f.get("repair_status"):
                extra = ", ".join(x for x in (f.get("external_verification_run"),
                                              f.get("human_closure_record")) if x)
                W(f"  - repair status: `{f['repair_status']}`"
                  + (f" ({extra})" if extra else "")
                  + " — descriptive, not a lifecycle state")
            W(f"  - found by: `{f.get('source', 'UNRECORDED')}`")
        W("")

        W("### Disputes — the human adjudicates")
        W("")
        W("§7.1: a dispute is a Codex finding plus a Claude "
          "`REJECT_WITH_REASON`.")
        W("")
        disputed = by_state.get("DISPUTED", [])
        W("None." if not disputed else "")
        for fid in disputed:
            f = data["findings"][fid]
            W(f"- **{fid}** · {f.get('class','?')}")
            for e in f.get("history", []):
                if e.get("event", "").startswith("REJECT"):
                    W(f"  - reason: {e.get('note','(none recorded)')}")
        W("")

        W("### Resolved findings")
        W("")
        res = by_state.get("RESOLVED", [])
        W(f"{len(res)} resolved." if res else "None.")
        if res:
            W("")
            W("`RESOLVED` under §5 means a repair was demonstrated in a later "
              "review target. It does not mean the repair was re-verified "
              "afterwards.")
        W("")
        W("<details><summary>Full ledger</summary>")
        W("")
        W(quote(led))
        W("")
        W("</details>")
    W("")

    # ---- implementer-disclosed defects, outside §7 and outside the ledger ----
    # Alex Zamurko, 5 October 2026: "it should also appear in the approval
    # package under known unresolved implementer-disclosed defects, separately
    # from the '2 OPEN reviewer findings'."
    #
    # Its own heading, below the findings and not inside them, because the two
    # have different provenance and merging them would let a self-disclosure
    # read as something a reviewer established. Not added to SECTION_7_ITEMS
    # either: that list is the protocol's, and extending it here would be this
    # tool legislating.
    W("## Implementer-disclosed defects")
    W("")
    W("Found by the implementing agent, not raised by any reviewer, and "
      "therefore not in the ledger above. They carry no cycle-generated "
      "identifier because no cycle produced them.")
    W("")
    reg = REPO / "registers" / "implementer-disclosed.json"
    _register_unreadable = ""
    try:
        _rg = json.loads(reg.read_text(encoding="utf-8"))
        _entries = _rg.get("entries", {})
    except (OSError, json.JSONDecodeError) as e:
        # Said out loud rather than skipped. The defect this section exists for
        # is silence being read as nothing to report, and a missing register
        # would reproduce it one level up.
        #
        # This used to say the same thing and then exit 0, on the reasoning
        # that the register is the implementing agent's own disclosure rather
        # than protocol evidence. The comment flagged that as "a distinction
        # worth a ruling if the reader disagrees with it", and on 14 October
        # 2026 Alex Zamurko gave the ruling: "A failed dependency must prevent
        # approval with a clear explanation... return CANNOT_ESTABLISH with a
        # non-zero exit status. Never substitute an empty register when
        # loading fails."
        #
        # So the package is still written, because a reader needs to see why,
        # and the exit status now says it cannot be approved from. Writing a
        # package and returning zero is the thing that would let an unreadable
        # dependency pass as an absent one.
        W(f"**REGISTER_STATE: CANNOT_ESTABLISH — {e}**")
        W("")
        W("That is not a statement that there are no implementer-disclosed "
          "defects. It is this tool unable to tell you either way, and this "
          "package must not be approved from while that is true.")
        _entries = None
        _register_unreadable = str(e)
    if _entries is not None:
        # The state glossary is read from the register rather than restated
        # here. Two copies of a definition are two definitions, and the one in
        # this file would be the one nobody updates.
        _gloss = _rg.get("states", {})
        _live = {k: v for k, v in sorted(_entries.items())
                 if v.get("state") != "RESOLVED"}
        if not _live:
            W("None outstanding.")
        for _k, _v in _live.items():
            _st = _v.get("state", "?")
            W(f"### {_k} — `{_st}`")
            W("")
            W(_v.get("description", "(no description)"))
            W("")
            W(f"- affected: {_v.get('affected_component', '?')}")
            W(f"- severity: {_v.get('severity', '?')}")
            W(f"- discovered: {_v.get('discovery_source', '?')}")
            W(f"- repair: {_v.get('proposed_repair', '?')}")
            W("")
            # This printed the REPAIRED_UNREVIEWED gloss under every entry
            # whatever its state, so an OPEN defect with no repair at all was
            # followed by a paragraph beginning "a repair has landed". The
            # same shape as the rest of this run's findings: a label that was
            # right for the case it was written against and was then applied
            # to every case.
            if _st in _gloss:
                W(f"`{_st}` means {_gloss[_st]}. It is not a resolution.")
            W("")

        # Resolved entries used to leave no trace at all. A reader following a
        # particular disclosure through successive packages would find it
        # simply gone, with nothing to say whether it had been resolved or
        # quietly deleted from the register. The ledger above prints a count of
        # its resolved findings for the same reason; this is the register's.
        _done = {k: v for k, v in sorted(_entries.items())
                 if v.get("state") == "RESOLVED"}
        if _done:
            W(f"### Resolved and no longer outstanding — {len(_done)}")
            W("")
            W("Listed by identifier only. `RESOLVED` here means an independent "
              "review examined the repair in a later target and found it held, "
              "and the register carries that reviewer's own limits with it.")
            W("")
            for _k, _v in _done.items():
                _hist = _v.get("history", [])
                _by = _hist[-1].get("by", "?") if _hist else "?"
                W(f"- **{_k}** · resolved per {_by}")
            W("")
    W("")

    # ---- MC-2 for every valid cycle, §7 item 10 ----
    W("## MC-2 conformance, every cycle")
    W("")
    W("The gate is run now, against the frozen evidence, rather than quoted "
      "from a stored result. A recorded PASS is a claim about the past; this "
      "is the gate's answer today.")
    W("")
    all_seen = True
    for c in cy:
        rc, text = run_tool(str(SCRIPTS / "validate_cycle.py"), str(c))
        verdict = next((l for l in text.splitlines()
                        if "MC2_CONFORMANCE" in l), "(no verdict line)")
        W(f"### {c.name} — `{verdict.strip()}`")
        W("")
        W("<details><summary>full gate output</summary>")
        W("")
        W(quote(text))
        W("")
        W("</details>")
        W("")
        if "PASS" not in verdict:
            all_seen = False
    present["MC-2 conformance results for every valid cycle"] = True
    if not all_seen:
        W("> At least one cycle does not currently pass. A package is still "
          "produced: whether that blocks approval is the human's decision, not "
          "this tool's.")
        W("")

    # ---- the reviewed artifacts, §7 items 1 and 2 ----
    W("## What is being approved")
    W("")
    latest = cy[-1]
    tj = latest / "target.json"
    ts = latest / "target.sha256"
    if tj.is_file() and ts.is_file():
        present["final plan"] = True
        present["final plan hash"] = True
        target = json.loads(tj.read_text(encoding="utf-8"))
        W(f"From `{latest.name}`, the most recent frozen cycle.")
        W("")
        W(f"Target digest: `{ts.read_text(encoding='utf-8').strip()}`")
        W("")
        files = target.get("plan_files") or target.get("artifacts") or []
        W(f"{len(files)} artifact(s):")
        W("")
        for f in files:
            W(f"- `{f.get('path','?')}` · `{f.get('sha256','?')}`")
        W("")
        W("The bytes reviewed are preserved under "
          f"`{latest.name}/artifacts/`. They are what the reviewer saw, and "
          "they do not change when the working tree does.")
    else:
        W(f"**`{latest.name}` has no target.json / target.sha256.** This "
          "package cannot say what was reviewed.")
    W("")

    # ---- what §7 asked for and what is here ----
    W("## §7 coverage")
    W("")
    W("Checked against §7's list rather than against what this package "
      "managed to produce, so an item that stopped being generated shows as "
      "absent instead of vanishing.")
    W("")
    for k in SECTION_7_ITEMS:
        W(f"- {'[x]' if present[k] else '[ ]'} {k}")
    W("")
    missing = [k for k in SECTION_7_ITEMS if not present[k]]
    if missing:
        W(f"**{len(missing)} of {len(SECTION_7_ITEMS)} not present.**")
        W("")
        # Each reason is keyed by the exact item string, so the text naming an
        # item and the table listing it cannot drift apart. They already had:
        # the table said "SPEC -> CODE -> TEST mapping" and the explanation
        # said "SPEC → CODE → TEST mapping", and a control looking for the
        # second under the first found nothing.
        WHY = {
            "SPEC -> CODE -> TEST mapping":
                "the output of a §1 plan audit. A bootstrap run reviews code "
                "directly and has no plan, so there is no mapping to produce. "
                "Named here rather than omitted, because a reviewer who cannot "
                "see what is missing cannot weigh it.",
            "resolved findings":
                "no review has been recorded for this run yet, so there is no "
                "ledger to read them from.",
            "unresolved findings":
                "no review has been recorded for this run yet. This is not the "
                "same as there being none.",
            "disputes":
                "no review has been recorded for this run yet, so no "
                "disposition has been rejected.",
        }
        for k in missing:
            W(f"- *{k}*: "
              + WHY.get(k, "not produced. See the section above for why."))
        W("")

    W("---")
    W("")
    W("## Recording the decision")
    W("")
    W("§7.3 permits `APPROVE`, `RETURN_FOR_REWORK`, `REJECT`. Nothing in this "
      "file records one.")
    W("")
    W(quote("python scripts/bootstrap_gate.py record \\\n"
            "    --decision APPROVE|RETURN_FOR_REWORK|REJECT \\\n"
            "    --decided-by \"<name>\" \\\n"
            "    --note \"<where the decision was made, and on what>\""))

    dest = Path(a.out).resolve() if a.out else (review / "APPROVAL-PACKAGE.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")

    # --out may name a path outside the repository, which is its main use: a
    # caller that wants the package without writing into the review it
    # describes. This line used to call relative_to(REPO) unconditionally and
    # raise for exactly that case, so the flag was in --help and had never
    # worked. Nothing caught it because the one caller passing --out did not
    # exist: the suite used the default and rewrote the committed package.
    try:
        shown = dest.relative_to(REPO).as_posix()
    except ValueError:
        shown = str(dest)
    print(f"wrote {shown}")
    print(f"  §7 items present  {sum(present.values())}/{len(SECTION_7_ITEMS)}")
    for k in missing:
        print(f"  not present       {k}")

    # Alex Zamurko, 14 October 2026, ruling on the open question above: "A
    # failed dependency must prevent approval with a clear explanation."
    if _register_unreadable:
        print(f"\n  REGISTER_STATE: CANNOT_ESTABLISH")
        print(f"  the implementer-disclosed register could not be read: "
              f"{_register_unreadable}")
        print(f"  The package was written so the reason is visible, and this "
              f"exits non-zero\n  because a package whose disclosure section "
              f"could not be assembled is not\n  one to approve from. An "
              f"unreadable register is not an empty one.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        sys.exit(1)
