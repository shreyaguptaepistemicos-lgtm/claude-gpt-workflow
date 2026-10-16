#!/usr/bin/env python3
"""Refresh the control counts the bootstrap prompts assert.

    python scripts/refresh_counts.py

Exit 0 = every suite ran to completion and the prompts now match.
Exit 1 = a suite did not exit cleanly; nothing was written.

Why this is a script and not a paste
------------------------------------
It was a here-string pasted into PowerShell, and on 12 September it recorded a
count from a suite that had crashed. `test_run_review.py` raised
FileNotFoundError two thirds of the way through, emitted 29 `[ok]` lines instead
of 95, and produced no FAIL line — so a grep for failures read clean. The
refresh then wrote 29 into both prompts, `test_prompts.py` compared 29 against
29 and passed, and the commit gate let it through.

Three separate checks agreed, and all three were measuring the same crash.

So: a suite that exits non-zero is not a measurement. Its count is whatever it
managed before dying, and writing that number into a document whose stated
purpose is to tell a reviewer how well controlled these components are would
understate them by two thirds. The prompt says it itself — "an inflated one
would misrepresent how well controlled these components are to the reviewer
being asked to trust them" — and the same is true of a deflated one.

Nothing is written unless every suite exits 0.

Why SUITES is five and not eight
--------------------------------
There are eight `test_*.py` files. Three are deliberately outside this count,
and the omission is written here rather than left to be inferred.

`test_prompts.py` is excluded because it is the consumer of this number. It
reads the counts these five produce and compares them against the prompts. A
suite that checked its own count would agree with itself, which is the defect
this script exists to prevent.

`test_convert_protocol.py` and `test_protocol_pin.py` are excluded because they
control protocol document handling — conversion fidelity, version pinning,
reference consistency — and none of those files are in the review target. The
number the prompts assert is a count of controls over the execution layer being
reviewed, not over the repository. Both were run by hand on 14 September and
both were green; they simply are not what this number measures.

If either ever covers a file in the review target, it belongs in SUITES.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SUITES = ("test_validate_cycle", "test_run_review", "test_ledger",
          "test_bootstrap_gate", "test_interfaces")


# Three shapes, because the first run predates there being a second:
#
#   bootstrap-review.md                    BOOTSTRAP-001, cycle 01
#   bootstrap-review-cycle-NN.md           BOOTSTRAP-001, cycle NN
#   bootstrap-review-RRR-cycle-NN.md       BOOTSTRAP-RRR,  cycle NN
#
# The run segment is required to be three digits so that it cannot be confused
# with the cycle segment of the second form, which is two.
PROMPT_NAME = re.compile(
    r"^bootstrap-review(?:-(?P<run>\d{3}))?(?:-cycle-(?P<cycle>\d{2}))?\.md$")


def run_and_cycle_for_prompt(p: Path) -> tuple[str, int]:
    """Which run and which cycle a bootstrap prompt was written for.

    The run half of this did not exist until 16 September, and its absence was
    not visible while there was only one run to be wrong about. `frozen_input`
    globbed `runs/*/`, so it answered "which run has a cycle with this number",
    not "which run is this prompt's". With one run those are the same sentence.

    With two they are not. A prompt written for BOOTSTRAP-002 cycle 01 would
    have matched BOOTSTRAP-001's cycle-01 input, been declared frozen, and never
    received today's control counts — so it would have gone to a reviewer
    stating the counts of a different run's first cycle, and `test_prompts.py`
    would have confirmed it against that same wrong input, because it asks this
    module rather than deciding for itself.

    Two checks agreeing while both read the wrong run. That is the shape this
    file's own docstring is about, one axis over.
    """
    m = PROMPT_NAME.match(p.name)
    if not m:
        # Not a name this function can read. Returning a guess here is how the
        # above happened, so it refuses instead.
        raise ValueError(
            f"{p.name} is not a bootstrap prompt name this tool can attribute "
            f"to a run and cycle. Expected one of:\n"
            f"    bootstrap-review.md\n"
            f"    bootstrap-review-cycle-NN.md\n"
            f"    bootstrap-review-RRR-cycle-NN.md")
    run = f"BOOTSTRAP-{m.group('run') or '001'}"
    cycle = int(m.group("cycle") or 1)
    return run, cycle


def cycle_for_prompt(p: Path) -> int:
    """Which review cycle a bootstrap prompt was written for."""
    return run_and_cycle_for_prompt(p)[1]


# The Finding ID prefix letter each bootstrap run raises under.
#
# This is a convention, not a derivation, and it is written down here rather
# than inferred so that it is one decision in one place. `B` was never defined
# as "run one"; it meant "bootstrap", and the two digits after it are the cycle.
# With a second run that reading stops being enough: BOOTSTRAP-002 cycle 01
# would also raise B01-Fnn, and while the two ledgers are separate files and
# would each accept it, the identifiers do not stay in the ledgers. They are
# quoted in the handover, the cycle summaries and Slack, where nothing carries
# the run alongside them and B01-F02 would name two different defects.
#
# The ledger itself is indifferent: check_id takes the grammar from the schema,
# which permits up to two letters, and validates only that the digits match the
# cycle. So this constrains the prompts, not the recording.
RUN_LETTER = {
    "BOOTSTRAP-001": "B",
    "BOOTSTRAP-002": "C",
    "BOOTSTRAP-003": "D",
}


def letter_for_run(run: str) -> str | None:
    """The prefix letter for a run, or None if the run has not been given one.

    None rather than a computed default: a letter invented at read time is a
    second convention, and the point of the table above is that there is one.
    """
    return RUN_LETTER.get(run)


def frozen_input(p: Path) -> Path | None:
    """That cycle's composed input, if the cycle has been frozen.

    A frozen cycle is finished. Its prompt describes a review that has already
    happened, and the number of controls that existed at the time is part of
    what happened.

    This existed for a day without it, and rewrote all three prompts on every
    run. `bootstrap-review-cycle-03.md` ended up asserting 298 controls for a
    cycle conducted against 263, and `test_prompts.py` confirmed the new figure
    because it compared the rewritten document against the same suites that had
    just been rewritten into it. Two checks agreeing, both measuring today.

    That is the 12 September incident in the docstring above, with the crash
    swapped for a clock. Editing a finished cycle's prompt to agree with the
    present is the same act as backdating an amendment: it makes the record
    describe now rather than then.
    """
    run, n = run_and_cycle_for_prompt(p)
    ci = REPO / "runs" / run / "plan-review" / f"cycle-{n:02d}" / "codex-input.md"
    return ci if ci.is_file() else None


def main() -> int:
    counts: dict[str, int] = {}
    broken: list[str] = []

    for name in SUITES:
        out = subprocess.run([sys.executable, f"scripts/{name}.py"],
                             cwd=str(REPO), capture_output=True, text=True)
        text = out.stdout + out.stderr
        n = text.count("[ok]")
        counts[f"scripts/{name}.py"] = n
        if out.returncode != 0:
            tail = [l for l in text.splitlines() if l.strip()][-1:] or ["(no output)"]
            broken.append(f"{name}: exit {out.returncode}, {n} control(s) "
                          f"before stopping\n      {tail[0][:140]}")

    for rel, n in sorted(counts.items()):
        print(f"  {rel:<34}{n}")
    print(f"  {'total':<34}{sum(counts.values())}")

    if broken:
        print()
        print("NOT WRITING. A suite that did not exit cleanly is not a count:")
        for b in broken:
            print(f"    {b}")
        print()
        print("  Its total is whatever it reached before stopping. Recording "
              "that would understate")
        print("  the controls to the reviewer being asked to trust them, and a "
              "crash reports no")
        print("  failure, so nothing else would notice.")
        return 1

    new_total = sum(counts.values())
    changed = []
    kept: list[str] = []
    for p in sorted((REPO / "specs" / "prompts").glob("bootstrap-review*.md")):
        # A name this tool cannot attribute to a run is not a name it may
        # rewrite. Treating it as unfrozen would edit a prompt on a guess, and
        # the guess it used to make silently was "cycle 01 of whichever run
        # sorts first".
        try:
            ci = frozen_input(p)
        except ValueError as e:
            print()
            print(f"NOT WRITING. {e}")
            return 1
        if ci is not None:
            kept.append(f"{p.name} (cycle {cycle_for_prompt(p):02d} is frozen)")
            continue
        original = p.read_text(encoding="utf-8")
        text = original

        # The total this file states, read from the file rather than inferred.
        #
        # On 14 September this step did not exist, the five numbers moved to
        # 24/99/73/42/29, and the sentence two lines below still read "Those
        # counts total 263". test_prompts.py checked the five and not the prose,
        # so it passed while the page contradicted itself.
        #
        # The first attempt at this repair inferred the old total by summing the
        # per-suite numbers already in the file. That only works when both go
        # stale in the same run. They had not: an earlier refresh had updated
        # the five, so the sum came to 267, matched the new total, and the
        # orphaned 263 was left untouched. Reading the stated number instead
        # makes the repair independent of how many times it has run before.
        m_total = re.search(r"\btotals?\s+(\d+)\b", text)
        stale = int(m_total.group(1)) if m_total else 0

        for rel, n in counts.items():
            text = re.sub(rf"^({re.escape(rel)}\s+)\d+( controls)",
                          rf"\g<1>{n}\g<2>", text, flags=re.M)

        # Replace it wherever it appears as a standalone number, not only in the
        # sentence that happens to say "total". The cycle-03 prompt states it
        # twice, in different words, and a rewriter that knew only the first
        # phrasing would leave the second stale and silent, which is the shape
        # of the defect this whole file exists to prevent.
        if stale and stale != new_total:
            text = re.sub(rf"\b{stale}\b", str(new_total), text)

        if text != original:
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            changed.append(p.name)

    print()
    print(f"updated: {', '.join(changed) if changed else 'nothing to change'}")
    if kept:
        print(f"left alone: {', '.join(kept)}")
        print("  A finished cycle's prompt states the controls that existed "
              "when it ran.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
