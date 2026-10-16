#!/usr/bin/env python3
"""Every mutation the probe holds can still find the line it aims at.

    python scripts/test_probe_anchors.py

Exit 0 = no repair has quietly stopped being watched.

Why this file exists
--------------------
The mutation probe breaks a repair on purpose and requires a named control to
go red. Each entry carries the exact source line it replaces. When somebody
edits that line, the entry does not move with it, and the mutation can no
longer be applied at all.

Nothing noticed, because noticing took a full sweep, and a full sweep takes
two and a half hours and had not completed since 12 October. The first one
that did, on 15 October, reported four repairs as not demonstrably held:

    BROKEN PROBE   EC-4b       anchor gone since 12 October
    BROKEN PROBE   SELF-F07d   anchor gone the same afternoon
    BROKEN PROBE   EC-4e       anchor gone the same afternoon
    WRONG CONTROL  D04-F01     expected text that no control ever printed

Three were a line edited without its mutation. The fourth never worked: the
text it waited for appears nowhere in the suite it names, so it could not have
passed on any day since it was written.

The probe reported all four honestly rather than counting them as catches,
which is the instrument working. What was missing is that the answer took two
and a half hours to arrive, so in practice nobody asked.

This asks in under a second, and CI asks on every push.

What it checks
--------------
For each mutation: the file exists, the anchor appears in it exactly once, the
replacement differs from the anchor, and the named control suite exists.

What it does NOT check
----------------------
Whether the named control actually goes red when the mutation is applied, or
whether the expected text appears in its failure output. Both need the suite
to run, which is the sweep's job. D04-F01's defect was of that kind and this
file would not have caught it.

So this closes three of the four, and says plainly that it does not close the
fourth. A control that implied otherwise would be the thing this repository
keeps finding.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "_probe"))


def main() -> int:
    try:
        import mutate_repairs as probe
    except Exception as e:                                    # noqa: BLE001
        print(f"  FAIL: the probe's own source will not import: {e!r}")
        return 1

    bad: list[str] = []
    seen: dict[str, int] = {}
    print("probe anchors")
    print(f"  {len(probe.MUTATIONS)} mutation(s) in the set")

    if not probe.MUTATIONS:
        print("\n  FAIL: the mutation set is empty, so this check would pass "
              "for a repository\n  with nothing watched at all.")
        return 1

    for m in probe.MUTATIONS:
        name, fname, anchor, replacement, suite, _expect = m[:6]
        seen[name] = seen.get(name, 0) + 1
        rel = probe.rel_of(fname)
        src = REPO / rel
        if not src.is_file():
            bad.append(f"{name}: aims at {rel}, which is not there")
            continue
        text = src.read_text(encoding="utf-8")
        # The probe masks its own mutation table when a mutation is aimed at
        # the probe, because the entry quotes the line it replaces and would
        # otherwise be found twice. The same masking has to happen here or
        # every self-aimed line reports a false duplicate.
        hay = (probe.outside_own_table(text) if rel == probe.OWN_REL
               else text)
        n = hay.count(anchor)
        if n == 0:
            bad.append(f"{name}: its anchor is no longer in {rel}. The line "
                       f"it guards was\n    edited and this entry was not "
                       f"moved with it, so the repair is\n    unwatched.")
        elif n > 1:
            bad.append(f"{name}: its anchor appears {n} times in {rel}, so "
                       f"which one gets\n    mutated is an accident.")
        if anchor == replacement:
            bad.append(f"{name}: its replacement is identical to its anchor, "
                       f"so applying it\n    changes nothing and the control "
                       f"cannot go red.")
        if not (REPO / "scripts" / suite).is_file():
            bad.append(f"{name}: names the control suite {suite}, which is "
                       f"not there.")

    for name, count in sorted(seen.items()):
        if count > 1:
            bad.append(f"{name}: appears {count} times in the set, so a "
                       f"filtered run naming it\n    does more than it says.")

    if bad:
        print()
        for b in bad:
            print(f"  FAIL: {b}")
        print(f"\n  {len(bad)} problem(s). A mutation that cannot be applied "
              f"is not a repair that\n  is watched, and the sweep takes two "
              f"and a half hours to say so.")
        return 1

    print("  [ok] every anchor is present exactly once, every replacement "
          "differs from it,")
    print("       and every named control suite exists")
    print("\n  Note: this does not run the controls. Whether each goes red "
          "for the right\n  reason is the sweep's question, and the sweep is "
          "the only thing that answers it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
