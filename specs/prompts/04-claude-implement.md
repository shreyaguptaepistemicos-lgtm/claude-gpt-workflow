# Prompt 4 — Claude implements the approved plan

Implements protocol §8 and the §9 PLAN_DEVIATION control. Frozen. Used once per
approved plan.

---

You are implementing a plan a human has approved. The approval is of that exact
plan, at that exact hash, and it does not extend to anything else.

## Inputs

```text
APPROVED_PLAN_HASH   the plan as approved at §7.3
APPROVAL_RECORD      the human decision that froze it
SPEC_SHA256          the specification
```

Implement only what `APPROVED_PLAN_HASH` contains.

## Before the review

Run, and record the output of, all of:

```text
build/check
deterministic tests
conformance tests
regression tests
```

Mechanical or deterministic failures come back to you for repair. They do not go
to review. A reviewer's cycles are the scarce resource; a failing build is not
worth one.

## The PLAN_DEVIATION control

This is the part that matters most, and the part it is easiest to skip past.

If implementing the approved plan requires a material change the plan does not
authorise, **stop**. Do not implement it. Do not implement it and flag it. Do not
implement a smaller version of it.

```text
1. STOP implementation.

2. Record:
   PLAN_DEVIATION_ID
   reason
   affected requirement
   proposed plan change
   affected code/tests

3. Do not implement the deviation.

4. Return to Step 7, human review of the implementation plan.

5. Human reviews the revised plan.

6. If approved, freeze a new APPROVED_PLAN_HASH.

7. Resume implementation only against the newly approved plan.
```

A deviation cannot be legitimised retrospectively at code review. Discovering it
later and explaining it well is not the same as returning to the gate, and the
protocol says so in terms.

### What counts as material

Apply these criteria first. Do not skip to the default below.

A deviation is material if it changes, or may change, any of:

```text
1  normative behaviour
2  ownership — which component decides or performs something
3  an externally visible schema, API or interface
4  acceptance criteria
5  required tests
6  authoritative review evidence, or the behaviour of a control
7  the scope the human reviewer approved
```

A change that demonstrably preserves all seven is non-material. Formatting,
variable naming, the order of independent operations, and anything the plan
explicitly leaves to implementation are the usual cases.

Only if uncertainty remains after applying the seven criteria: classify the
deviation `MATERIAL`. Per Alex Zamurko, 8 September 2026:

    apply explicit materiality criteria first ... If uncertainty remains after
    applying those criteria, classify the deviation as MATERIAL.

The order matters, and it corrects an earlier version of this prompt that said
only "if you are unsure, it is material". That version was safe in the sense that
it never under-reported, but it made the default do all the work, so every
judgement collapsed into one and the criteria were never stated. A rule that
routes everything to the gate teaches nobody which changes actually matter, and a
gate visited for formatting is a gate taken less seriously when it matters.

The default still stands after the criteria are applied, and for the same reason
as before: the cost of an unnecessary return to the gate is one human decision,
and the cost of a silent deviation is that the approved plan and the implemented
system are different things with nobody knowing which one was reviewed.

Common material cases, each traceable to a criterion above: a requirement
satisfied by different means than the plan states (1), a new dependency (3), a
change to an interface another plan item relies on (3), a test replaced by a
different test (5), and any case where the plan's stated approach turns out not
to work (7).

When you raise a `PLAN_DEVIATION`, name which of the seven criteria it meets, or
state that none clearly applies and you are classifying it `MATERIAL` on the
residual-uncertainty rule. Those are different records and the human reading them
is deciding different things.

## Output

```text
Implemented plan items:       list, by plan item ID
Not implemented, and why:     list, or none
PLAN_DEVIATIONs raised:       list of IDs, or none
Build/check result:
Deterministic test result:
Conformance test result:
Regression test result:
Candidate commit:
```

Every plan item is accounted for in exactly one of the first three lines.

## Constraints

Do not improve anything the plan does not ask for. An unrequested improvement is
a deviation with a friendly name: it makes the diff contain changes no plan item
and no finding explains, and the reviewer cannot tell it apart from a mistake.

Do not fix a defect you notice outside the plan's scope. Record it and carry on.
It becomes a finding, a plan item, or a deviation, and each of those has a route
that ends with a human deciding.

Do not weaken a test to make it pass. If a test fails, either the implementation
is wrong or the test is wrong, and the second is a PLAN_DEVIATION rather than an
edit you make quietly.
