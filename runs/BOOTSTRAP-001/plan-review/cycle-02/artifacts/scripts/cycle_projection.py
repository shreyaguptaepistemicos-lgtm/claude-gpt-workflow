#!/usr/bin/env python3
"""What counts as a cycle, decided once and imported by everyone who asks.

B01-F11: "The ledger authorizes transitions from its unfiltered stored state and
history, while the controller filters events by valid cycles." Decision G was
implemented in `loop_state.py` alone, so the two components disagreed about what
a cycle is, and the disagreement was exploitable in both directions:

  * a DEMONSTRATED recorded in an invalid cycle left the ledger permanently
    RESOLVED, so a later valid resolution was refused while the controller still
    counted the finding OPEN. The finding could never be closed.
  * an ACCEPT recorded in an invalid cycle satisfied the ledger's precondition
    for `resolve`, so an invalid acceptance could authorize a closure the
    controller then counted as real.

Neither is fixable in one component. Filtering harder in the controller does not
stop the ledger from refusing; filtering harder in the ledger does not stop it
from authorizing. So the projection lives here, and both import it.

Three states, not two
--------------------
The distinction that makes this workable is between a cycle that has been judged
and failed and one that has not been judged yet.

    VALID     the directory exists and passes the MC-2 gate
    INVALID   the directory exists and fails it
    UNJUDGED  no directory yet

Only INVALID strips authority. An UNJUDGED cycle is the one being assembled
right now: findings get raised in it before its evidence is complete, and a
ledger that refused to record them would be unusable. Its events carry authority
provisionally, and lose it the moment the cycle is judged and fails, because
authority is recomputed on every read rather than frozen at write time.

Loop calculation is stricter and uses VALID only, per §2 and §3: an invalid cycle
"cannot consume one of the four valid review cycles", and an unjudged one has no
evidence to measure.

Nothing is ever deleted. Invalid events stay in the history as evidence of what
was recorded and when; they simply stop authorizing transitions and stop
blocking them.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"


def cycle_dirs(review: Path) -> list[tuple[int, Path]]:
    out = []
    for d in sorted(review.iterdir()) if review.is_dir() else []:
        m = re.fullmatch(r"cycle-(\d{2})", d.name)
        if m and d.is_dir():
            out.append((int(m.group(1)), d))
    return sorted(out)


def gate(cycle_dir: Path) -> tuple[bool, str]:
    """Run the MC-2 conformance gate. Never read a recorded verdict.

    A loop controller that accepted an asserted PASS would let an invalid cycle
    consume the budget, which is the exact defect the "MAX 4 counts valid cycles"
    note exists to prevent.
    """
    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle_dir)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        return False, "checker could not run"
    reason = ""
    if r.returncode != 0:
        fails = [l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l]
        reason = fails[0] if fails else "MC-2 FAIL"
    return r.returncode == 0, reason


class Projection:
    """Which cycles exist, which passed, and which events may authorize.

    `valid`   ordered cycle numbers that exist and pass MC-2. Loop arithmetic.
    `invalid` cycle number -> why it failed. Evidence only.
    """

    def __init__(self, valid: list[int], invalid: dict[int, str]):
        self.valid = valid
        self.invalid = invalid

    def authorizes(self, cycle: int) -> bool:
        """May an event recorded in this cycle authorize a state transition?

        Judged-and-failed is the only disqualifier. See the module docstring for
        why an unjudged cycle has to count.
        """
        return cycle not in self.invalid

    def why_not(self, cycle: int) -> str:
        return self.invalid.get(cycle, "")


def project(review: Path) -> Projection:
    valid: list[int] = []
    invalid: dict[int, str] = {}
    for num, d in cycle_dirs(review):
        ok, why = gate(d)
        if ok:
            valid.append(num)
        else:
            invalid[num] = why or "MC-2 FAIL"
    return Projection(valid, invalid)


def replay(history: list[dict], proj: Projection,
           upto: set[int] | None = None) -> str | None:
    """The state a finding reached, counting only events that carry authority.

    `upto` additionally restricts to a set of cycle numbers, which is how the
    controller asks for the state at an earlier cycle boundary. The ledger passes
    None and means "as things stand".
    """
    state = None
    for e in history:
        c = e["cycle"]
        if upto is not None and c not in upto:
            continue
        if not proj.authorizes(c):
            continue
        state = e["state"]
    return state


def last_authorized(history: list[dict], event: str,
                    proj: Projection) -> dict | None:
    """The most recent event of this kind that is allowed to authorize anything.

    An ACCEPT in an invalid cycle is still in the history and still visible in
    `show`. It just cannot be the ACCEPT that `resolve` requires.
    """
    for e in reversed(history):
        if e["event"] == event and proj.authorizes(e["cycle"]):
            return e
    return None
