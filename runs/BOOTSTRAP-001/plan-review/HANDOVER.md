# BOOTSTRAP-001 plan review — handover to human review

**For Alex Zamurko. 16 September 2026.**

The loop has reached `MAX_4_REACHED` after four valid cycles. Under §6 that is an
exit, not an obstacle, and since your ruling of 15 September no authorisation
clears it. Five findings are still open and they come to you.

This document is the implementing agent's account. The authoritative records are
`ledger.json` and each cycle's `findings.json`. Where they disagree with this,
they govern.

---

## What this was, and what it is not

Four review cycles over the ten artifacts of the execution layer: the MC-2 gate,
the runner, the ledger, the loop controller, the bootstrap gate, the findings
parser, the cycle projection, the authority module, the run-pin module, and the
evidence schema.

**It is development evidence, not a protocol outcome.** `BOOTSTRAP-001` is
marked `NOT_A_PROTOCOL_CYCLE`, and the controller refuses to state an
authoritative loop result for it — you have to pass `--development` to compute
one at all, and the output carries the label. That is correct. This review
examined the machinery that runs reviews, using that machinery, before it had
been approved. Nothing here should be cited as a protocol result.

**Nothing here is technically enforced.** `MC1_ENFORCEMENT` is `CONVENTION_ONLY`.
Every check in this layer is detection that holds while the checks run faithfully
and while nobody edits the records they read. The same writable code performs the
checks on itself.

---

## The arc

| Boundary | Open | Resolved | Outcome |
|---|---|---|---|
| n=1 (cycle 01) | 18 | 0 | CONTINUE |
| n=2 (cycle 02) | 20 | 8 | CONTINUE |
| n=3 (cycle 03) | 17 | 13 | CONTINUE |
| n=4 (cycle 04) | 5 | 25 | **MAX_4_REACHED** |

Thirty findings raised, twenty-five resolved, five open.

Repair claims examined and rejected, by cycle: 5 of 13, then 9 of 20, then 5 of
11. **The rejection rate did not fall.** Roughly two in five repair claims failed
verification in every cycle, including the last. That is the single most useful
number in this document, and it is the reason the reviewer ended all four cycles
saying it makes no claim the review has converged.

---

## The five open findings

Each is a recurrence. All five were repaired at least once and the repair did not
hold.

**B01-F02 · the budget can still be extended.** Your ruling of 15 September was
that the four-valid-cycle maximum is not clearable. I implemented that for the
`MAX_4_REACHED` outcome specifically. But `STALLED` is evaluated *before* the
budget test, so an authorisation clearing a genuine `STALLED` at the fourth
boundary still returns `CONTINUE`. The controller and the runner still disagree,
by a different route than before. *Correction: enforce the ceiling before any
cleared outcome becomes CONTINUE.*

**B01-F07 · the gate checks that fields agree, not that they are true.** A target
was built whose governing pin named a file that does not exist, with
`"not-a-hash"` as its digest, consistent across both fields. Check 9 passed and
MC-2 returned PASS. The check confirms internal agreement between assertions; it
does not establish that the assertions identify real artifacts. *Correction:
validate digest syntax, establish which artifact is the protocol, and verify the
versions against preserved evidence.*

**B01-F11 · a backdated acceptance revives a reopened finding.** Accept at
cycle 1, demonstrate at 2, reopen at 3 — then append an acceptance dated cycle 2,
and demonstrate at 4. The ledger stores `RESOLVED`. No acceptance ever belonged
to the reopening cycle or later. *Correction: reject dispositions that predate
the transition they respond to.*

**B01-F14 · deleting the whole file bypasses the check for the missing field.**
Remove `mc1_enforcement` from `run.json` and the controller refuses, exit 2.
Remove `run.json` entirely and it exits 0 with an unqualified `CONVERGED`.
Classification returns UNKNOWN before the shared metadata check runs.
*Correction: refuse authoritative calculation when run metadata cannot be
established at all.*

**B02-F04 · the atomic commit point is preceded by a destructive write.**
Publication now turns on one atomic rename. But recording writes
`capture-log.json` non-atomically *before* reaching it. An interruption there
leaves partial JSON, and recovery then cannot read which capture was
authoritative. The previous generation survives on disk and becomes
unreachable. *Correction: make every capture-log update atomic, or separate
attempt journaling from the authoritative designation.*

---

## The pattern, which matters more than any single finding

In four of the five, the reviewer said some version of the same sentence:

- "The named control tests a boundary that already produces MAX_4_REACHED."
- "The named negative controls change one assertion while retaining the other,
  leaving consistent false assertions untested."
- "The named reopening control demonstrates refusal when no additional ACCEPT
  exists. It does not test whether a subsequently appended ACCEPT is causally
  eligible."
- "The named controls corrupt working copies while retaining a readable
  designation. They demonstrate publication recovery, not survival of this
  earlier write boundary."

Each control was written by the person who wrote the repair, and each tested the
case the repair was designed for. The adjacent case — one step sideways — went
untested every time. Mutation testing did not catch this, because breaking the
fix does make those controls fail; they simply were not asking a wide enough
question.

**This is a fact about how the controls are produced, not about these five
defects.** The same method produced the twenty-five findings now marked resolved,
and cycle 04 explicitly did not re-verify six of those. The honest reading is
that the resolved set is likely to contain defects of this shape too.

---

## What I think you are actually being asked to decide

Not "should these five be fixed" — they should, and each has a stated correction.

The decision is whether this execution layer is fit to run real protocol reviews
while these five are open. Points on each side, as fairly as I can put them:

**For using it now.** The layer caught thirty real defects in its own machinery,
including several the implementing agent would never have found. It refused to
state a protocol outcome for its own development run. It refused to let a
finished cycle's prompt be quietly rewritten. Every failure in this document was
found by the process working, not by the process failing.

**For fixing first.** Two of the five let a check pass on evidence that is simply
false — B01-F07 and B01-F14 both produce a PASS or a `CONVERGED` on material that
should stop the run cold. A gate that can be satisfied by a nonexistent artifact
is not yet a gate. And the rejection rate never fell, which is weak evidence that
a fifth cycle would have found more.

I lean to fixing B01-F07 and B01-F14 before the layer is trusted with a real run,
and to treating B01-F02, B01-F11 and B02-F04 as known and scheduled. But that is
a judgement about risk appetite and delivery pressure, which is yours.

---

## One question still standing

Twice now the implementing agent has found a defect in its own work rather than a
reviewer finding it: **B02-F11** on 10 September, and the count refresh rewriting
finished cycles' prompts on 15 September. Both are described in the cycle
summaries. Neither is in the ledger.

**Does a defect the implementing agent finds in its own work enter the ledger as
a finding?** Entering it means the agent raises findings against itself, which is
the thing this review exists so as not to depend on. Not entering it means the
ledger is not a complete census of known defects, and the two above appear only
in prose nobody is required to read.

Open since 10 September. Two instances make it policy rather than incident.

---

## Addendum, 16 September: all five are repaired

On your instruction, B01-F07 and B01-F14 were repaired the same day this was
handed over, and the remaining three followed. The five findings above are left
as written, because that is what the loop produced.

### The three that followed

**B01-F02**, commit `76e102b`. Your ruling made `MAX_4_REACHED` unclearable, and
that was not enough: §6 evaluates `STALLED` before the budget, so a fourth
boundary that genuinely stalls never met the unclearable list at all, and
clearing it returned `CONTINUE` with the ceiling never consulted. The check now
sits on the way out rather than trusting the shape of whichever exit was
cleared.

**B01-F11**, commit `4b36083`. A reopening spends the acceptance before it, and
nothing required the replacement to come after. An acceptance dated cycle 2,
appended to a finding reopened in cycle 3, resolved it in cycle 4. Two guards
now, because refusing to write one is not refusing to use one: the ledger will
not record a disposition dated before the reopening it answers, and replay will
not honour one already in the history.

**B02-F04**, commit `5201396`. Recording rewrote `capture-log.json` twice during
preparation, before the atomic rename called the commit point. Truncating it
there left the previous generation on disk with nothing able to say which
attempt it was. Every write to that file is atomic now.

*One honest note on B02-F04's control.* It reads the source and requires every
write to that file to use the atomic path, rather than injecting a crash, which
a suite driving the runner as a subprocess cannot do. That is a weaker kind of
control than the others here and it is marked as such in the code.

**B01-F14**, commit `c617333`. A missing `run.json` no longer classifies as
UNKNOWN and carry on. It refuses, and there is no labelled fallback: calling a
run we cannot read "development evidence" would be a claim about it.

**B01-F07**, commit `c584e66`. Check 9 now replays the run's own pin history for
the cycle and requires the recorded governing set to be the one that history
produces. Which pin counts as the protocol comes from what the run declares
rather than from whichever entry matched the field under test. All four
BOOTSTRAP-001 cycles still pass, so nothing completed was invalidated.

Both were mutation-verified, and this time the controls were written to attack
the fix. The control that matters for B01-F07 is the one where the governing set
is well formed, names the real protocol with its real digest, and is internally
consistent throughout — its only defect is a spec the run never pinned, which
nothing but the run's history can see. Breaking the replay turns that control red
and leaves the others green.

**None of the five can be demonstrated, and that is worth understanding.** §5
gives `RESOLVED` only once a repair is demonstrated in the next review target.
The loop closed at `MAX_4_REACHED` and there is no next target. So all five sit
`OPEN` in the ledger for as long as the ledger exists, however thoroughly they
are fixed. Closing them needs either a new run or a ruling from you. This is the
same collision as the six cycle-02 findings, arriving at the other end of the
loop.

**The ledger therefore now understates the work and overstates the risk.** Five
`OPEN` findings, none of them unrepaired. A reader who trusts the state field
gets the wrong picture in both directions, and this addendum is the only thing
that corrects it.

*Corrected 17 September.* It is no longer the only thing. On your item B, the
ledger now carries a descriptive `repair_status` beside the authoritative state,
and all five read `IMPLEMENTED_AWAITING_DEMONSTRATION`. The state field is
unchanged and stays `OPEN`; the counts are unchanged at five open and
twenty-five resolved; the loop still reports `MAX_4_REACHED`. A control captures
the controller's output and the per-cycle snapshot, writes the field, recomputes
both, and fails if either moved by a byte.

They become `EXTERNALLY_DEMONSTRATED` only once BOOTSTRAP-002 has actually
demonstrated them, and the command refuses that value without both a verification
run and a closure record. So the ledger cannot claim the demonstration before it
happens, which is the one thing this field could otherwise have been used for.

**One thing the repair turned up.** Making the controller refuse an unreadable
run broke three control suites, because their fixtures built review directories
with no `run.json` at all. They had been exercising those seams through the very
gap they existed to catch. That is the pattern cycle 04 named, found in the
fixtures rather than in the assertions, and it is a second place to look if you
decide the resolved set is worth re-examining.

The suites now stand at 307 controls, up from 298 at the close of cycle 04. That
number appears in no prompt, because all four cycle prompts are frozen and a
finished cycle's prompt states the controls that existed when it ran.

---

## Where everything is

```text
runs/BOOTSTRAP-001/plan-review/ledger.json          authoritative state
runs/BOOTSTRAP-001/plan-review/cycle-0N/            frozen evidence, four cycles
runs/BOOTSTRAP-001/plan-review/summaries/           per-cycle readable summaries
specs/prompts/bootstrap-review*.md                  what each reviewer was told
```

Each cycle directory holds the frozen target and its hash, the composed input,
the raw reviewer output, the extracted findings, and the capture log recording
every attempt. Cycle 04 also holds the auxiliary manifest binding the versions of
the five control suites, which are evidence but not members of the target.

The control suites stand at **307 controls across five files**. They stood at
**298 at the close of cycle 04**, which is the figure cycle 04's frozen prompt
states and the one that belongs to that review; the nine added since are the
controls for the five repairs in the addendum above.

*This section said 298 as the current figure while the addendum said 307. Alex
Zamurko caught it, 16 September. The two numbers were written by different
passes and only one of them was updated, which is the same shape as the count
refresh on 14 September.*
