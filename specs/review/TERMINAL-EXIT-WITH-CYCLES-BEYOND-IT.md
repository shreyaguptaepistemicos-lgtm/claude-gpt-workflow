# LOOP_STATUS can read CONVERGED while the ledger holds the finding OPEN

26 September 2026, found while repairing C01-F01. Not raised by cycle-01's
review, not repaired, and open for Alex Zamurko.

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
