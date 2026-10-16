# Bootstrap exit criteria

Status: FROZEN, 10 October 2026. Alex Zamurko answered all four judgements on
9 October and refined the first on 10 October; they are recorded under each
condition below, in his words.

Frozen means this document is now the version the fourth review is judged
against, and changing it takes a new version rather than an edit. Its digest
is recorded in `BOOTSTRAP-EXIT-CRITERIA.sha256` and `scripts/exit_criteria.py`
refuses to report anything if the two disagree. That is not tamper-proofing,
which AR-1 says plainly we do not have; it is so that a later reader can tell
which criteria a decision was taken against, and so that an edit has to be a
decision rather than a drift.

Frozen is not met. The conditions below are checked by
`scripts/exit_criteria.py`, and as of freezing EC-3 passes, EC-1 fails, and
EC-2 and EC-4 cannot be established. Three of those resolve through the fourth
review. Freezing the criteria before the review is the point: the bar is set
before the thing that has to clear it, not after.

Alex Zamurko, 9 October 2026, 4:41 pm:

    "Maybe we should introduce a formal exit criterion for the bootstrap phase,
    rather than continue reviewing indefinitely. The next independent review
    should answer whether the system is sufficiently reliable to proceed to the
    next development stage, not whether every conceivable defect has been
    eliminated."

This document turns that into four conditions that can be checked. It exists
because the alternative is a conversation at the end of every run about whether
we are done, and that conversation has no natural end.

## What this document is for

The bootstrap phase has produced three runs, fifty-odd repairs and five
implementer-disclosed defects. None of that answers the question Alex actually
needs answered, which is whether the review layer is reliable enough to be used
on real work. "No defects remain" is not that question and cannot be reached.

So each condition below has three parts.

- **The claim.** What the condition asserts, in one sentence.
- **The check.** Something anyone can run that returns the same answer each
  time. `scripts/exit_criteria.py` runs all of them and prints a verdict per
  condition.
- **The judgement.** The part no check can settle, named explicitly, and
  reserved to Alex. Hiding a judgement inside a word like "critical" or
  "adequate" would make the criteria look mechanical while leaving the real
  decision unrecorded.

A condition passes only when its check passes **and** its judgement is
recorded. The script never prints an overall verdict, because the overall
verdict is not the script's to give.

## EC-1 No critical open defect

**The claim.** The controller cannot declare convergence that the evidence does
not support, and no reporting tool can claim success for work it did not do.

**The check.**

1. For every run, the loop controller either computes a state or refuses with
   a stated reason. It never emits `CONVERGED` while findings are open at the
   governing boundary.
2. The approval package refuses with `FINDINGS_STATE: CANNOT_ESTABLISH` rather
   than printing an empty category, whenever the controller cannot establish
   the finding sets.
3. Every mutation in the probe set that targets a convergence or reporting
   rule goes red in a control that names it.

**The judgement, Alex's, and he has given it.** 9 October 2026, on what
counts as critical: "Anything permitting false success, false convergence,
invalid approval or unreliable verification, because these undermine the
reliability of the entire review process."

Refined on 10 October into two kinds, because the first wording made AR-1's
acceptance look like a contradiction of it:

Critical functional defects are failures that can produce incorrect decisions
during normal operation, and these block bootstrap. Adversarial integrity
risks are deliberate manipulation of writable code or records, and these may
be conditionally accepted for internal bootstrap but cannot be claimed as
protected. AR-1 is the second kind. It permits an invalid approval in the
sense that someone determined to forge one can, and it is accepted on that
basis with no claim of protection attached.

The four blocking defects under this ruling, recorded in
`specs/blocking-defects.json`: D02-F01, SELF-F02, SELF-F04, SELF-F05. A
finding raised after 9 October is unclassified until he rules on it, and this
condition cannot be evaluated while any finding is unclassified. Silence is
not a classification.

## EC-2 Reliable verification

**The claim.** The tests detect the failures they are named for, and the tools
that run them leave the repository as they found it.

**The check.**

1. Every suite passes.
2. A full mutation sweep reports every repair caught, with nothing in
   `BROKEN PROBE`, `MISSED`, `WRONG CONTROL`, `CRASHED` or `COULD NOT RUN`.
3. After that sweep, the real working tree is unchanged and no disposable
   checkout remains.

The third item became checkable rather than hopeful on 9 October, when the
probe moved to a disposable checkout. Before that, the question "did the tool
restore the repository" had a different answer every time it was killed.

**The judgement, Alex's, and he has given it.** 9 October 2026: "Every known
blocking failure must have a reproducible test. Exhaustive coverage is
unnecessary." And on AR-3: "Complete mutation coverage is unrealistic. Testing
every known blocking repair is sufficient for bootstrap, provided coverage
limitations are documented."

So the bar is every known blocking repair, not every repair. The set currently
exceeds it, covering all fifty-six rather than the four blocking ones, which
is worth saying because the bar is what will hold when the set stops keeping
pace with the code.

The limitation he required documented: a sweep can only test the mutations
someone wrote. Fifty-six catching fifty-six says nothing about a repair nobody
wrote a mutation for, and no check closes that gap, because it is a question
about what is absent.

## EC-3 Complete audit records

**The claim.** Findings, evidence, approvals and changes can each be traced
from the record back to the thing that produced them.

**The check.**

1. Every frozen cycle passes the MC-2 gate when it is run today, rather than
   carrying a recorded PASS from when it was frozen.
2. Every finding a review reported appears in the ledger and has a state the
   controller can reconstruct at the governing boundary.
3. Every superseded capture has an approval record bound by hash to both the
   displaced and the displacing bytes, and the displaced capture is preserved.
4. Every entry in the implementer-disclosed register carries a description, a
   discovery source, an affected component, a severity, a state, a repair and
   evidence.
5. An approval package can be produced for every run, or the run states why it
   cannot.

**The judgement, Alex's, and he has given it.** 9 October 2026: "Records must
match original evidence and frozen code. Hashes alone cannot establish truth."

That raises the bar above what the checks measure, deliberately. The five
checks above establish that a record exists, is internally consistent, and
agrees with the digests beside it. Matching the *original evidence* means
comparing the record against the thing it describes, and for an approval that
thing is a message in Slack or WhatsApp which the repository cannot reach.
That comparison is a person's work, and AR-2 is where it is recorded as such.

`MC1_ENFORCEMENT` remains `CONVENTION_ONLY`: the same writable code performs
these checks on itself, and nothing prevents someone editing the records it
reads. Under his 10 October split that is an adversarial integrity risk,
accepted for bootstrap and never to be described as protected.

## EC-4 Independent verification of blocking repairs

**The claim.** Every repair classified as blocking has been examined by a
reviewer who is not the implementing agent, in evidence that is preserved.

**The check.**

1. Each blocking item names the cycle whose reviewer examined its repair.
2. That cycle is frozen and passes MC-2 today.
3. The reviewer's own words about that item are quoted in the record, with the
   limits the reviewer stated.

**The judgement, Alex's, and he has given it.** 9 October 2026: "Behavioural
claims require independent execution because source inspection alone cannot
establish runtime behaviour."

That settles the case this condition was written around. For SELF-F01 the
cycle 03 reviewer read the source and the saved output of a run, because it
could not execute anything on that machine. Under this ruling that is not
enough for a blocking item, and AR-4 is marked blocking on exactly that basis.

**What counts as independent execution,** from his 10 October reply, in order
of preference. Codex executes the tests itself. Failing that, a separate
runner executes them against the exact frozen commit and Codex assesses that
evidence, which he accepts "provided the implementing agent does not control
that evidence". Failing both, SELF-F01 remains unverified and this condition
is not met.

The practical form of "does not control" is the tests running on GitHub
against the frozen commit, with the log published by GitHub rather than pasted
in. That establishes the run happened and passed. It does not establish that
the tests are good tests, since the implementing agent wrote them, and that
half is Codex reading the test sources. Both halves are needed.

## What moves to the backlog

Items that are real, recorded, and not blocking. They keep their records and
their states; they simply stop gating the phase.

- The citation work Alex deferred on 8 October: reference-list confirmation,
  the `and` taxonomy cases 8 and 11, and non-year publication-status values.
- The `SPEC -> CODE -> TEST` mapping absent from §7 of the approval package. A
  bootstrap run reviews code directly and has no plan, so there is no mapping
  to produce.
- Any finding raised after 9 October that Alex does not classify as blocking.

Moving an item here is a decision with a date and a name on it, not a filing
convenience. The backlog is read at the start of the next phase, not archived.

## Accepted risks

Alex Zamurko, 9 October 2026: "Let's distinguish what can be reliably verified
now from what needs stronger protection later, and explicitly document any
risks we accept."

A risk is accepted when it is understood, recorded, and knowingly left in
place. Accepting one is Alex's decision; writing it down accurately is mine.
The list lives in `specs/ACCEPTED-RISKS.md` so that it can be read on its own
by someone who has not followed the conversation.

## Recording the decision

This document is a draft until Alex rules on each judgement above. Once ruled,
it is frozen and its hash is recorded, so that a later reader can tell which
version of the criteria a decision was taken against. Changing the criteria
afterwards takes a new version rather than an edit, for the same reason a
frozen cycle's prompt is never updated to match today's controls.
