#!/usr/bin/env python3
"""Every control suite in this repository is actually run by CI.

    python scripts/test_ci_coverage.py

Exit 0 = every suite is invoked by a command CI will execute.
Exit 1 = one is not, or this check cannot establish that it is.

Why this file exists
--------------------
Alex Zamurko, 15 October 2026, on the new encoding check:

    "I inspected .github/workflows/ci.yml, and it does not invoke the new
     scripts/test_encoding_discipline.py check... A script being present in
     the repository does not establish that CI enforces it."

He named one suite. Checking the whole set found two: the encoding check he
spotted, and `test_exit_criteria.py`, the suite guarding the exit criteria the
bootstrap decision is read from, written on 12 October and never run anywhere
but on the implementing agent's machine.

That is the same shape as the defect that created the execution-layer job. From
the workflow's own comment, 17 September: "Until 17 September this workflow ran
Go checks and nothing else, so the execution layer was verified only when
somebody remembered to type the command. 319 controls that nothing ran on
push." A rule that depends on remembering is a rule that lapses, and it lapsed
twice. So the rule is checked rather than remembered.

The first version of this file, and why it was wrong
----------------------------------------------------
It read ci.yml as one string and asked whether each suite's filename appeared
anywhere in it. Alex Zamurko, 16 October 2026: the checker "must recognise
actual executable test commands, not comments or disabled steps."

He is right, and the failure is this layer's own signature defect sitting in
the file written to prevent it. A suite named only in a comment passed. Worse,
the comments in ci.yml name several suites by filename while explaining why
they were added, so deleting the step that runs `test_exit_criteria.py` would
have left this check green on the strength of the paragraph explaining how
important it was. The check was not establishing coverage. It was establishing
that somebody had once typed the name.

What this checks now
--------------------
The workflow is parsed as YAML, so comments are gone before anything is
matched: they are not data and the parser never yields them. Every job's steps
are walked, each `run:` block is read as shell, lines commented out inside it
are dropped, and `python scripts/<name>.py` invocations are extracted. A suite
is covered when a command that CI will execute names it.

Three answers, not two
----------------------
A step or job can carry an `if:` whose value depends on the event, the inputs
or the outcome of earlier steps. Deciding those here would mean evaluating
GitHub's expression language against a run that has not happened, and a wrong
guess in the permissive direction is exactly the failure this file exists to
prevent. So conditions known to run unconditionally are treated as reached,
and anything else is reported as CANNOT_ESTABLISH rather than counted.

In this repository that distinction is load-bearing: the mutation-sweep job
runs only on a manual dispatch with a flag set, so a suite invoked only there
is not run on push, and saying "covered" would be false.

Its own negative controls
-------------------------
The first version passed every day it existed and established nothing, so this
one is not trusted on its word either. SELF_CASES below are workflows written
to be wrong in one specific way each, and they run on every invocation, before
the real question is asked. If this file ever stops noticing a suite hidden in
a comment or behind a gate, it fails there rather than reporting coverage it
cannot see through.

What this does NOT check
------------------------
That a suite passes. That its job is not disabled at the repository level or by
a required-workflow setting. That a self-hosted runner exists for it. Those are
visible on the run page. This is a check against forgetting, not against
sabotage, and naming the limit is cheaper than implying it is covered.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

# GitHub step and job conditions that always evaluate true, or that mean the
# default behaviour. Anything outside this set is not decided here.
#
# `success()` is the implicit default when no `if:` is given, so a step
# carrying it explicitly is in the same position as one carrying nothing: it
# runs unless something before it failed, which is the normal state of a
# passing run.
UNCONDITIONAL = {"", "always()", "success()", "!cancelled()", "!failure()"}

# `python scripts/foo.py`, with any flags between, and tolerant of the
# ci-step.sh wrapper the real workflow puts in front of it:
#
#     bash .github/ci-step.sh "test_ledger" python scripts/test_ledger.py
#
# The wrapper is irrelevant to the question; what matters is that the
# interpreter is handed that file.
INVOCATION = re.compile(
    r"\bpython[0-9.]*\s+(?:-\S+\s+)*(?:scripts[/\\])([A-Za-z0-9_]+\.py)\b"
)


def condition(value: object) -> str:
    """Normalise an `if:` value to the bare expression inside ${{ }}."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    return " ".join(text.split())


def commands(run: str) -> list[str]:
    """The invocations in one `run:` block, minus anything commented out.

    A `#` inside a run block is a shell comment, not a YAML one, so the parser
    hands it over as data and it has to be dropped here. Only whole lines are
    dropped: a `#` mid-line can be inside a quoted string, and guessing at that
    would be the permissive direction again.
    """
    live = [ln for ln in run.splitlines() if not ln.lstrip().startswith("#")]
    return INVOCATION.findall("\n".join(live))


def scan(doc: dict) -> tuple[dict[str, list[str]], dict[str, list[tuple[str, str]]]]:
    """Walk a parsed workflow.

    Returns (reached, conditional). `reached` maps a filename to the places it
    is invoked by a command CI will run unconditionally. `conditional` maps a
    filename to the places it is invoked behind an `if:` this does not decide,
    with that condition, so the report can say which one.
    """
    reached: dict[str, list[str]] = {}
    conditional: dict[str, list[tuple[str, str]]] = {}

    for job_name, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        job_if = condition(job.get("if"))
        for i, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            step_if = condition(step.get("if"))
            where = f"{job_name} / {step.get('name') or f'step {i + 1}'}"
            blocker = next((c for c in (job_if, step_if)
                            if c not in UNCONDITIONAL), None)
            for name in commands(run):
                if blocker is None:
                    reached.setdefault(name, []).append(where)
                else:
                    conditional.setdefault(name, []).append((where, blocker))

    return reached, conditional


# Workflows written to be wrong, each in one specific way, so that this file's
# own answer can be shown to change when the thing it claims to detect is
# present. The first version of this check passed every day it existed and was
# establishing nothing; a check that has only ever said yes has not been shown
# able to say no.
#
# The first two are the defect Alex Zamurko found on 16 October, in both places
# a comment can hide: YAML comments, which the parser drops, and shell comments
# inside a run block, which it hands over as data.
SELF_CASES = [
    (
        "a suite named only in a YAML comment is not counted",
        """
jobs:
  j:
    steps:
      # python scripts/test_ghost.py
      - name: real
        run: python scripts/test_real.py
""",
        {"test_real.py"}, set(),
    ),
    (
        "a suite commented out inside a run block is not counted",
        """
jobs:
  j:
    steps:
      - name: real
        run: |
          # python scripts/test_ghost.py
          python scripts/test_real.py
""",
        {"test_real.py"}, set(),
    ),
    (
        "a suite in a job gated by an undecided condition is not counted",
        """
jobs:
  j:
    if: ${{ github.event_name == 'workflow_dispatch' }}
    steps:
      - name: gated
        run: python scripts/test_ghost.py
""",
        set(), {"test_ghost.py"},
    ),
    (
        "a suite in a step gated by an undecided condition is not counted",
        """
jobs:
  j:
    steps:
      - name: gated
        if: ${{ inputs.deep }}
        run: python scripts/test_ghost.py
""",
        set(), {"test_ghost.py"},
    ),
    (
        "!cancelled() counts as reached, and the ci-step.sh wrapper is seen "
        "through",
        """
jobs:
  j:
    steps:
      - name: wrapped
        if: ${{ !cancelled() }}
        run: bash .github/ci-step.sh "test_real" python scripts/test_real.py
""",
        {"test_real.py"}, set(),
    ),
]


def self_check(yaml_module) -> list[str]:
    """Run SELF_CASES. Returns the labels that did not behave as stated."""
    bad = []
    for label, text, want_reached, want_conditional in SELF_CASES:
        reached, conditional = scan(yaml_module.safe_load(text))
        if set(reached) != want_reached or set(conditional) != want_conditional:
            bad.append(f"{label}\n        reached={sorted(reached)} "
                       f"conditional={sorted(conditional)}")
    return bad


def main() -> int:
    suites = sorted(p.name for p in (REPO / "scripts").glob("test_*.py"))
    print("CI coverage of the control suites")
    print(f"  {len(suites)} suite(s) in scripts/")

    if not suites:
        print("\n  FAIL: no suites were found at all, which means this check "
              "is looking in the\n  wrong place and would pass for a "
              "repository with no controls in it.")
        return 1

    if not WORKFLOW.is_file():
        print(f"\n  FAIL: there is no workflow at "
              f"{WORKFLOW.relative_to(REPO).as_posix()}, so nothing runs any "
              f"of them\n  on push.")
        return 1

    try:
        import yaml
    except ImportError:
        print("\n  CANNOT_ESTABLISH: PyYAML is not installed, so the workflow "
              "cannot be parsed.\n  This check used to read the file as plain "
              "text, which is the defect it was\n  rewritten to remove, and "
              "falling back to that would answer the question\n  wrongly "
              "rather than not at all. Install from requirements-ci.txt.")
        return 1

    try:
        doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"\n  CANNOT_ESTABLISH: the workflow is not valid YAML, so what "
              f"it runs cannot be\n  read: {e}")
        return 1

    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        print("\n  CANNOT_ESTABLISH: the workflow has no `jobs:` mapping, so "
              "there are no steps\n  to read. An empty answer here is not a "
              "green one.")
        return 1

    # Before answering about this repository, show that the answer can be no.
    # Each case is a workflow written to be wrong in one specific way, and the
    # question is whether this file notices. Run every time rather than behind
    # a flag, because a self-check nobody runs is the thing this file is about.
    bad = self_check(yaml)
    if bad:
        print("\n  FAIL: this check does not detect what it claims to. Its "
              "own negative controls\n  did not behave as stated, so its "
              "answer about the real workflow cannot be\n  relied on:")
        for b in bad:
            print(f"      {b}")
        return 1
    print(f"  [ok] {len(SELF_CASES)} negative controls: comments, shell "
          f"comments and gated\n       steps are not counted as coverage")

    reached, conditional = scan(doc)
    missing = [s for s in suites if s not in reached]
    failures = 0

    for s in missing:
        failures += 1
        print()
        if s in conditional:
            print(f"  CANNOT_ESTABLISH: {s} is invoked only under a condition "
                  f"this check does\n  not evaluate, so whether CI runs it is "
                  f"not established here:")
            for where, cond in conditional[s]:
                print(f"      {where}")
                print(f"        gated by: {cond}")
            print("  Move it to a step that runs on push, or decide the "
                  "condition deliberately\n  and say so. An undecided "
                  "condition is not coverage.")
        else:
            print(f"  FAIL: {s} is never invoked by a command this workflow "
                  f"executes.")
            print("  It runs only when somebody remembers to type it. That is "
                  "the state the\n  execution-layer job was created to end, "
                  "and it returns one suite at a time\n  unless something "
                  "asks.")

    if failures:
        print(f"\n  {failures} suite(s) not established as reached on push.")
        return 1

    print(f"  [ok] all {len(suites)} are invoked by executable commands in "
          f"{WORKFLOW.relative_to(REPO).as_posix()}")
    if conditional:
        gated = sorted(set(conditional) - set(reached))
        if gated:
            print(f"       (also invoked under undecided conditions "
                  f"elsewhere: {', '.join(gated)})")
    print("\n  Note: this checks that each is invoked by a command CI will "
          "run, not that each\n  passes. The run page says that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
