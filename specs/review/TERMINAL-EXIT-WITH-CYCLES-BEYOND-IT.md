# LOOP_STATUS can read CONVERGED while the ledger holds the finding OPEN

26 September 2026, found while repairing C01-F01. Not raised by cycle-01's
review. **Ruled on by Alex Zamurko on 17 October 2026 and repaired the same
day; the ruling and what it cost are at the foot of this note.** The question
and the three positions are left standing above it, because a note that is
rewritten to look like it always knew the answer is not a record of anything.

## What this note got wrong first

The first version of this note said the cycles run after the exit "are not
reported as anything at all. They are simply not reached." That is false, and
it was written from reading the boundary walk rather than running it.
`_probe/c01f01_controller.py` runs it:

```text
LOOP_STATUS: CONVERGED
Nothing open and nothing disputed. Proceed to human plan review.

UNAUTHORIZED CONTINUATION: the loop reached CONVERGED at n=2 (cycle-02).
  2 further valid cycle(s) were run after it: cycle-03, cycle-04
  §6's exits are mandatory, so the first one governs and the later cycles do
  not override it.
```

The continuation is named, the cycles are listed, and the rule is quoted. So
the controller is doing most of what this note accused it of skipping, and the
gap is much narrower than it claimed. The narrower gap is real, which is why
the note survives at all rather than being deleted.

## The gap that is actually there

Two lines of one output disagree.

```text
LOOP_STATUS: CONVERGED          the finding set was empty at n=2
ledger show                     OPEN, with the cycle-02 ACCEPT named as
                                never having taken effect
```

Both are correct about their own question. At the end of cycle 2 the finding
really was resolved, and as things stand it really is open again. But
`LOOP_STATUS` is the line consumers act on, and the runner reads it to decide
whether another cycle may be opened. A consumer that reads only that line gets
CONVERGED for a loop whose finding is open.

The UNAUTHORIZED CONTINUATION block is what keeps this from being silent. It
is prose under the status line rather than part of the status, so it informs a
reader and not a caller.

## The question, and it is a ruling

When a terminal exit governs at boundary n and valid cycles exist beyond it,
should `LOOP_STATUS` still be the exit computed at n?

```text
1  yes, as today
       the exit is a fact about the loop and the continuation block says the
       rest. Consumers that act on one line are reading it wrongly, and the
       remedy is to fix the consumers.

2  no: the status becomes something no consumer can mistake for permission
       a distinct status, or the exit at n reported together with a refusal
       to proceed. Costs a new value in a closed vocabulary, which §6 does
       not currently allow.

3  no: the LATEST boundary governs and the passed exit is reported alongside
       makes status and ledger agree, at the cost of letting work done after
       an uncleared exit decide the outcome. That is the direction C01-F02
       warns about, and it would undo the repair this same review asked for.
```

Position 1 is the current behaviour and may well be the intended one. What is
not defensible is leaving it unstated, because the disagreement looks like a
defect to anyone who meets it without this note.

## What is in place meanwhile

`scripts/test_ledger.py` carries the full history as a control:

```text
the rebuild holds the finding OPEN                      asserted
the diagnostic names the backdated ACCEPT and why       asserted
the output names the unauthorized continuation          asserted
LOOP_STATUS is CONVERGED                                tripwire, not a tick
```

The first three are settled behaviour and are asserted as such. The fourth
fires on any change in either direction and points back here, so a future
repair cannot pass silently and today's answer is not recorded as correct.

## Related, and distinct

C01-F02 required the four-valid-cycle ceiling to be enforced while walking
every boundary rather than only in the fallback for the latest one. That is
repaired: a cleared exit at n=4 now ends the loop at MAX_4_REACHED instead of
letting the walk continue to n=5.

It is the same walk and a different rule. The ceiling is about how many cycles
may be spent; this is about what a boundary means when evidence exists past
it. Repairing one should not be taken to have settled the other.

## The ruling, 17 October 2026

Alex Zamurko:

```text
Preserve the historical terminal result, but ensure that an unauthorised
continuation prevents downstream consumers from treating it as a valid
approval or convergence result.

Test this through the actual consumer path. If it already refuses safely,
document the evidence and close the issue. If it does not, implement
fail-closed behaviour.
```

That is position 1 with a condition attached, and the condition is the part
this note could not have guessed: the exit stands, and a consumer must not be
able to act on it.

### What the test through the consumer path found

It does not refuse safely, and did not.

The package a human approves from reads the controller's machine-readable
output. That output carried `governing_boundary`, `status`, `label`,
`valid_cycle_count`, `sets_established`, `open`, `resolved` and `disputed`.
The continuation was in none of them. It existed only in the prose printed
after the status line, which is what this note said on 26 September in these
words: it "informs a reader and not a caller".

So a loop that reached CONVERGED at n=2 and then ran two further valid cycles
produced an approval package headed CONVERGED, with the continuation visible
only to someone who read the quoted controller output closely enough to notice
a paragraph below the verdict. Three weeks of this note existing did not make
that false. Nobody had run the consumer.

### What was changed

`scripts/loop_state.py` now carries `unauthorized_continuation` in its JSON:
the boundary the loop terminated at, the status it terminated with, and the
cycles run after it. It is `null` when there is none rather than absent,
because an absent key reads as "this version does not report continuations",
which a caller testing for presence cannot distinguish from "there is no
continuation". The prose block and the JSON are now built from the same
computed value, so the two cannot drift into disagreeing about one loop.

`scripts/approval_package.py` refuses when it is present, with
`LOOP_STATE: UNAUTHORIZED_CONTINUATION`, naming the boundary and the cycles.
Refusing rather than annotating, because a package that is produced is a
package that can be approved from, and his instruction names the failure as
treating the exit "as a valid approval or convergence result".

Nothing about the §6 exit itself changed. `LOOP_STATUS` still reports the
first terminal exit, which is what "preserve the historical terminal result"
requires. What is withheld is the document, not the history.

### The evidence that it holds

`scripts/test_approval_package.py` builds a fixture with four valid cycles
whose finding is demonstrated at cycle 2, so the loop converges at n=2 with
cycles 3 and 4 standing past it. Two controls over it:

```text
the controller reports the continuation in machine output, not only in prose
the package refuses, and the refusal names cycle-03 and cycle-04
```

The second checks the named cycles appear, because a refusal that does not say
which cycles are in question cannot be checked by the person reading it.

### What is still true, and is the reason the tripwire stayed

`scripts/test_ledger.py` carries `LOOP_STATUS is CONVERGED` as a tripwire
rather than a tick, firing on any change in either direction. It did not fire
on this work, and that is the evidence that the historical result was
preserved. Had we quietly changed what the controller reports, it would have
gone red. A tripwire that never fires is worth nothing; this one earned its
place by staying silent about the one thing it was watching while everything
around it changed.
