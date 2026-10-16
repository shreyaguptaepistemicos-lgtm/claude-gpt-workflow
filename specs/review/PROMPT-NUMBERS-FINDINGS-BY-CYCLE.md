# A review prompt numbers new findings from its own cycle

Recorded 30 September 2026, closing C02-F01. This is the correction Codex asked
for in place of a fix, because the file it concerns cannot be edited.

## What happened

`specs/prompts/bootstrap-review-002-cycle-02.md` told its reviewer:

```text
Findings from this cycle are C01-Fnn.
```

It was cycle 2's prompt. The two digits in a finding identifier are the cycle
that raised it, so `ledger.py`'s `check_id` refuses a `C01-Fnn` raised at cycle
2, and `cmd_raise` separately refuses an identifier that already exists. Every
one of C01-F01 through C01-F08 already existed.

So the instruction was unfollowable in both directions. Numbering as told would
have produced identifiers the ledger refuses; numbering from the existing eight
would have given new defects the names of old ones.

The sentence was carried over from cycle 1's prompt, where it was correct, and
not updated when the file was written for cycle 2.

## What the reviewer did

Used `C02-Fnn`, and raised the conflict as C02-F01 rather than resolving it
quietly:

> Following the prompt's numbering would give a new defect an existing issue's
> identity, or, if numbering started after the eight existing IDs, still give a
> new cycle-02 issue cycle-01 digits that the ledger refuses at cycle 2.

That is the right handling and it is worth recording as such. A reviewer that
had simply complied would have produced a capture the ledger could not accept,
and the defect would have surfaced as a transcription failure with no finding
attached to it.

## Why the prompt is not corrected

It is frozen. Its digest is recorded in
`runs/BOOTSTRAP-002/plan-review/cycle-02/target.json`, MC-2 check 10 requires
the input to carry that digest, and the review recorded against it is the
evidence eight findings were closed on. Editing it now would change the bytes a
recorded review was conducted against, which is the thing the whole freezing
discipline exists to prevent.

Codex, cycle 02:

> Do not repair this by renaming already captured findings during
> transcription. Record an explicit correction to the review instructions while
> preserving this frozen prompt as historical evidence.

## The rule, for every prompt after this one

A prompt's new findings are numbered from the cycle that prompt is for. The
letter is the run; the digits are the cycle. `C03-Fnn` for cycle 3 of this run.

An earlier identifier may appear in a prompt, and often must: a prompt tells the
reviewer how to report an unrepaired finding against its persistent id, and
BOOTSTRAP-002's first prompt necessarily names several of BOOTSTRAP-001's. What
may not appear is an instruction to *raise* new findings under anything but the
prompt's own cycle.

## What holds it

`test_prompts.py` requires each bootstrap prompt to show the identifier its own
cycle needs. That control existed before this finding and was red the whole
time, because nothing was running the full suite. It caught C02-F01
independently and nobody looked, which is its own lesson and is recorded in the
commit of 28 September.

The cycle-02 prompt is exempted from it by name, and the exemption is bound to
this finding: it holds only while `C02-F01` is in the ledger, checked by reading
the ledger rather than by asserting it. If the finding is removed the control
goes red again. An exemption that cannot outlive its reason is the only kind
worth having.
