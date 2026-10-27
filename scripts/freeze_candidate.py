#!/usr/bin/env python3
"""Name the commit the exit evidence is about.

    python scripts/freeze_candidate.py                 # freeze HEAD
    python scripts/freeze_candidate.py --commit <sha>  # freeze a named one
    python scripts/freeze_candidate.py --show

Writes specs/frozen-candidate.json, which EC-2 and EC-4 read.

Why this exists
---------------
Alex Zamurko, 15 October 2026, on EC-4:

    "There is a second problem: requiring evidence to match the current HEAD
     creates a commit-identity conflict. Committing evidence after the tested
     commit changes HEAD, potentially invalidating the evidence it records...
     Match evidence to an explicitly frozen candidate SHA, not
     indiscriminately to the latest repository HEAD."

He is right, and the cost was already paid twice before he said it. On 12
October a full mutation sweep ran for two and a half hours against one commit;
a one-line commit afterwards moved HEAD, and EC-2 correctly reported the sweep
as describing a different commit. The sweep was not wrong. The binding was.

Binding evidence to HEAD means the act of recording evidence destroys it. That
is circular, and no amount of care avoids it, because the record has to be
committed and committing moves HEAD.

So the candidate is named once, deliberately, and the evidence is about that.
HEAD then moves as much as it likes while the evidence stays true.

What this does NOT claim
------------------------
Freezing a candidate here does not make the commit immutable; nothing in this
repository can, under MC1_ENFORCEMENT: CONVENTION_ONLY. It records which commit
the exit evidence is about, so that a reader can tell whether a given piece of
evidence describes it. Anyone who can edit this file can change the answer, and
the file says so rather than implying otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CANDIDATE = REPO / "specs" / "frozen-candidate.json"

PURPOSE = (
    "The commit the bootstrap exit evidence is about. EC-2 asks whether the "
    "mutation sweep describes it; EC-4 asks whether the recorded GitHub runs "
    "do. Named explicitly rather than taken from HEAD, because committing the "
    "evidence moves HEAD and would invalidate the evidence being committed. "
    "Written by scripts/freeze_candidate.py, never by hand. Under "
    "MC1_ENFORCEMENT: CONVENTION_ONLY this records a decision; it does not "
    "enforce one."
)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, encoding="utf-8")


def load() -> dict | None:
    if not CANDIDATE.is_file():
        return None
    try:
        return json.loads(CANDIDATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{CANDIDATE} is not valid JSON: {e}\n"
                 f"It is written by this script. Fix or remove it.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--commit", default="",
                   help="the commit to freeze; HEAD if omitted")
    p.add_argument("--reason", default="",
                   help="why this commit, for a reader who was not here")
    p.add_argument("--show", action="store_true",
                   help="print the current candidate and stop")
    a = p.parse_args()

    if a.show:
        d = load()
        if not d:
            print("no candidate is frozen")
            return 2
        print(f"frozen candidate  {d.get('commit')}")
        print(f"  frozen at       {d.get('frozen_at')}")
        print(f"  reason          {d.get('reason') or '(none recorded)'}")
        r = git("rev-parse", "HEAD")
        if r.returncode == 0:
            head = r.stdout.strip()
            print(f"  HEAD is         {head}"
                  + ("  (the same)" if head == d.get("commit")
                     else "  (moved since, which is expected and fine)"))
        return 0

    sha = a.commit.strip()
    if not sha:
        r = git("rev-parse", "HEAD")
        if r.returncode != 0:
            return fail(f"HEAD could not be resolved: {r.stderr.strip()}")
        sha = r.stdout.strip()
    elif not re.fullmatch(r"[0-9a-f]{40}", sha.lower()):
        r = git("rev-parse", sha)
        if r.returncode != 0:
            return fail(f"git does not know {sha!r}: {r.stderr.strip()}")
        sha = r.stdout.strip()
    sha = sha.lower()

    t = git("cat-file", "-t", sha)
    if t.returncode != 0 or t.stdout.strip() != "commit":
        return fail(f"{sha[:12]} is not a commit in this repository")

    # A candidate frozen while the tree is dirty names bytes that are not the
    # bytes anyone will test. The evidence would be about the commit and the
    # work would be about the working copy.
    st = git("status", "--porcelain")
    dirty = [ln[3:].strip() for ln in st.stdout.splitlines() if ln.strip()
             and not ln.strip().endswith("full-sweep.txt")]
    if dirty:
        return fail("the working tree differs from the commit being frozen:\n"
                    + "\n".join(f"      {d}" for d in dirty[:10])
                    + "\n\n  Freeze a candidate that matches what is on disk, "
                      "or the evidence will\n  describe a commit nobody is "
                      "actually running.")

    subj = git("log", "-1", "--format=%s", sha).stdout.strip()
    prev = load()
    CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE.write_text(json.dumps({
        "schema": "frozen-candidate/1",
        "purpose": PURPOSE,
        "commit": sha,
        "subject": subj,
        "frozen_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        "reason": a.reason,
        "supersedes": (prev or {}).get("commit"),
    }, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"frozen candidate  {sha}")
    print(f"  subject         {subj}")
    if prev and prev.get("commit") != sha:
        print(f"  supersedes      {prev.get('commit')}")
        print("\n  Evidence recorded against the previous candidate no longer "
              "describes the\n  frozen one. EC-2 and EC-4 will say so rather "
              "than carrying it over.")
    return 0


def fail(msg: str) -> int:
    print(f"  [REFUSED] {msg}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
