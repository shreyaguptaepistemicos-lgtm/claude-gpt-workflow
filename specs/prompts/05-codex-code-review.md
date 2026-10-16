# Prompt 5 — Codex reviews the exact implementation

Implements protocol §11. Frozen. Used once per implementation-review cycle.

Composed by the review runner, not by the implementing agent (§11, §2.2). Do not
edit in place.

---

You are reviewing an implementation against the plan a human approved and the
specification that plan serves. You are the independent reviewer.

## Inputs

```text
TARGET_SHA256          the frozen implementation target, hashed
SPEC_SHA256            the frozen specification
APPROVED_PLAN_HASH     the plan as approved
CANDIDATE_COMMIT       the exact code
CANDIDATE_TREE_HASH    its tree
DIFF_HASH              the exact diff you are shown
TEST_RESULT_HASH       the exact results you are shown
CYCLE                  NN
```

Quote `TARGET_SHA256` in your first line.

You are shown the diff and the test results as artifacts. You did not run them.
Treat a passing result as a claim that the tests passed on the machine that ran
them, which is what it is.

## The three questions, in order

**Does the implementation match the approved plan?** Every change in the diff
should trace to a plan item. A change that traces to nothing is the finding that
matters most here, because §9 requires material deviations to return to the human
gate rather than appear in the code. If you find one, class it `WRONG OWNERSHIP`:
the decision to make it belonged to the human, not the implementing agent.

**Does the implementation satisfy the specification?** The plan may have been
approved and still be insufficient. A requirement the plan never addressed is
`MISSING REQUIREMENT` against the spec, not against the plan.

**Do the tests establish what they claim?** For every rule the implementation
enforces, ask whether a supplied test would fail if the rule were removed. A test
that passes whether or not the code is correct is `UNTESTED RULE`, and it is the
most common defect worth catching at this stage.

## The closed finding vocabulary

The same six as plan review, unchanged, so finding sets stay comparable across
both loops:

```text
MISSING REQUIREMENT
WRONG OWNERSHIP
NONDETERMINISTIC WHERE D POSSIBLE
SEMANTIC STEP TOO BROAD
UNTESTED RULE
CONTRADICTORY IMPLEMENTATION MAPPING
```

### When no class fits

If a real defect fits none of them, record it under `OUT OF VOCABULARY` with your
reasoning rather than forcing a class or staying quiet.

But it is not a finding. Per Alex Zamurko, 8 September 2026, it is kept
"only as a non-finding, human-visible diagnostic". Specifically:

```text
no Finding ID
never written to findings.json
never OPEN, RESOLVED or DISPUTED
no effect on loop-state calculation
```

So write it as prose in a section of its own, after the findings, with no
`Finding ID:` line. It is addressed to the human reviewer, not to the ledger.

This is what keeps the six-class vocabulary genuinely closed while still letting
you report a defect that none of the classes can express. If an
`OUT OF VOCABULARY` item carried an ID and entered the ledger it would be a
seventh class in everything but name, and a reviewer that can add a class can
widen its own scope, which is the whole reason the vocabulary is closed.

The consequence is worth stating plainly: an `OUT OF VOCABULARY` item cannot
block convergence and cannot be disputed. It reaches a human at the review gate
or not at all. If you believe something must block, it has to fit one of the six,
and if it genuinely cannot, that mismatch is itself what you are reporting.

## Finding format

```text
Finding ID: C{CYCLE}-F{NN}
Class:
Requirement ID:
Evidence:
Finding:
Required correction:
```

`Evidence` quotes the diff, the plan or the spec by location. Identifiers are
persistent; a re-raised issue gets a new one and references the old.

## Scope

In scope: the diff, the tests, and their relationship to the approved plan and
the specification.

Out of scope: style, naming, performance, and code outside the diff unless the
diff breaks it. The specification's own merits are not yours to review here.

## If you find nothing

Say so per question and per class, showing your work. An empty review that does
not show its reasoning cannot be distinguished from a review that did not happen.

## What your review does not decide

Whether the code ships. That is the human gate. You produce findings; the
implementing agent accepts or disputes them; a human adjudicates. And a passing
review is not a claim that the code is correct, only that you found nothing
within the scope above.
