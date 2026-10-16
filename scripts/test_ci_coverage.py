#!/usr/bin/env python3
"""Every control suite in this repository is run by CI.

    python scripts/test_ci_coverage.py

Exit 0 = no suite exists that nothing reaches.

Why this file exists
--------------------
Alex Zamurko, 15 October 2026, on the new encoding check:

    "I inspected .github/workflows/ci.yml, and it does not invoke the new
     scripts/test_encoding_discipline.py check... A script being present in
     the repository does not establish that CI enforces it."

He named one suite. Checking the whole set found two: the encoding check he
spotted, and `test_exit_criteria.py`, which is the suite guarding the exit
criteria the bootstrap decision is read from. That one had been written on 12
October and had never run anywhere but on the implementing agent's machine.

This is the same shape as the defect that created the execution-layer job in
the first place. From the workflow's own comment, 17 September: "Until 17
September this workflow ran Go checks and nothing else, so the execution layer
was verified only when somebody remembered to type the command. 319 controls
that nothing ran on push." The job was added to close that, and then every
suite written afterwards had to be remembered into it by hand. A rule that
depends on remembering is a rule that lapses, and it lapsed twice.

So the rule is checked rather than remembered.

What this checks
----------------
Every `scripts/test_*.py` is named somewhere in `.github/workflows/ci.yml`.
This file included: a coverage check that nothing runs would be the joke it
is trying to prevent.

What this does NOT check
------------------------
That the step actually passes, that it is not inside a disabled job, or that
`if:` conditions let it run. Those are visible on the run page and this is a
check against forgetting, not against sabotage. Naming the limit is cheaper
than implying it is covered.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def main() -> int:
    suites = sorted(p.name for p in (REPO / "scripts").glob("test_*.py"))
    print("CI coverage of the control suites")
    print(f"  {len(suites)} suite(s) in scripts/")

    if not WORKFLOW.is_file():
        print(f"\n  FAIL: there is no workflow at "
              f"{WORKFLOW.relative_to(REPO).as_posix()}, so nothing runs any "
              f"of them\n  on push.")
        return 1

    text = WORKFLOW.read_text(encoding="utf-8")
    missing = [s for s in suites if s not in text]

    if not suites:
        print("\n  FAIL: no suites were found at all, which means this check "
              "is looking in the\n  wrong place and would pass for a "
              "repository with no controls in it.")
        return 1

    if missing:
        print()
        for m in missing:
            print(f"  FAIL: {m} is never invoked by ci.yml")
        print("\n  Each of these runs only when somebody remembers to type "
              "the command. That is\n  the state the execution-layer job was "
              "created to end, and it returns one\n  suite at a time unless "
              "something asks.")
        return 1

    print(f"  [ok] all {len(suites)} are named in "
          f"{WORKFLOW.relative_to(REPO).as_posix()}")
    print("\n  Note: this checks that each is invoked, not that each passes "
          "or that its job\n  is enabled. The run page says that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
