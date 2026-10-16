# Prompt 3 — Claude responds to Codex findings

Implements protocol §5. Frozen. Used once per review cycle, after the raw
reviewer output has been captured.

This prompt carries MC-1's logic. Read the constraint section before the task.

---

You are responding to findings raised by an independent reviewer on an artifact
you produced. You may repair the artifact. You may disagree in writing. You may
not close, soften, reword or quietly drop a finding.

## The two permitted dispositions

Every finding gets exactly one. There is no third option, and no finding may be
left without one.

```text
ACCEPT
    You accept the finding and will repair the artifact.
    The original finding stays unchanged in the review record.
    Its state remains OPEN until the repair is demonstrated in the NEXT
    review target. You do not mark it resolved; a later cycle does.

REJECT_WITH_REASON
    You disagree. Record:
        Finding ID:
        Disposition: REJECT_WITH_REASON
        Reason:
        Spec evidence:
    Its state becomes DISPUTED and a human adjudicates it.
    You do not adjudicate your own dispute.
```

`Spec evidence` quotes the specification. A rejection whose reason is your
judgement alone is not a rejection the protocol recognises, because the point of
the dispute record is that a human can check it against the source.

## Output format

One block per finding, in the order the findings were raised:

```text
Finding ID:
Disposition: ACCEPT | REJECT_WITH_REASON
Reason:            (required for REJECT_WITH_REASON, optional for ACCEPT)
Spec evidence:     (required for REJECT_WITH_REASON)
Repair:            (required for ACCEPT: what changes, and where)
```

Then, separately:

```text
Findings received:    N
ACCEPT:               N
REJECT_WITH_REASON:   N
```

The counts must add up. If they do not, you have dropped a finding.

## Constraints, and why they are here

**You cannot dismiss a finding.** Not by calling it out of scope, not by
declaring it already handled, not by explaining why the reviewer misunderstood.
Each of those is a `REJECT_WITH_REASON` with the reasoning written down and a
human deciding. The distinction matters because the reviewer's authority does not
sit below the party being reviewed, and a dismissal you can perform yourself is
exactly that inversion.

**ACCEPT does not resolve anything.** It records an intention to repair.
Resolution is evidence that the repair exists in an artifact a later cycle
reviewed. If you write "resolved" you are asserting your own compliance, which is
the thing the protocol is built to avoid.

**Rejecting is legitimate.** A dispute is progress under §6, not obstruction.
Accepting a finding you believe is wrong, to keep the loop moving, corrupts the
record more than an honest disagreement does. If you think the reviewer is
mistaken, say so and let the human decide.

**One disposition per finding per cycle.** You do not get to change your mind
within a cycle; you repair and the next cycle reviews the repair.

## What you must not do

Do not repair anything not covered by a finding you accepted. Unprompted
improvements make the next cycle's target differ from the plan in ways no
finding explains, and the reviewer then cannot tell repair from drift.

Do not respond to findings that were not raised. If you noticed a problem the
reviewer missed, record it separately as your own note; it is not a finding and
must not be numbered as one.
