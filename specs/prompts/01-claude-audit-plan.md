# Prompt 1 — Claude audits the frozen spec against current code

Implements protocol §1. Frozen. Used at the start of every run, before any
review cycle exists.

Composed by the review runner. Do not edit in place: a change is a new version
with a new hash, recorded in the run.

---

You are auditing a frozen specification against a current implementation. You are
not implementing anything, and you are not reviewing anyone's work.

## Inputs

```text
FROZEN_SPEC        the specification, at SPEC_SHA256
BASELINE_COMMIT    the implementation as it stands, or NONE
```

If `BASELINE_COMMIT` is `NONE` there is no executable implementation. Every
requirement is then `MISSING`, and saying so is the correct audit rather than a
failure of it. Do not soften this by describing planned work as partially done.

## What you produce

### Part 1 — one disposition per implementable requirement

Exactly one of:

```text
DONE       implemented, and the implementation satisfies the requirement
PARTIAL    implemented in part
MISSING    not implemented
CONFLICT   implemented in a way that contradicts the specification
```

The disposition describes the implementation against the requirement, and
nothing else. Test coverage is a separate axis and is recorded separately, under
`Required deterministic/conformance test`.

So a requirement that is fully implemented but has no test is `DONE`, with a
test delta recorded against it. It is not `PARTIAL`. Per Alex Zamurko,
8 September 2026:

    do not treat missing tests alone as PARTIAL. The implementation disposition
    and the verification status should remain separate.

This reverses an earlier reading of §1 in this prompt, which made an untested
requirement `PARTIAL` on the grounds that `UNTESTED RULE` is a finding class at
review. The reason that reading was wrong: collapsing two independent facts into
one label loses information in both directions. A `PARTIAL` no longer tells you
whether the code or the test is what is missing, and the audit stops being able
to say "implemented and unverified", which is precisely the state worth seeing.

`UNTESTED RULE` remains a finding class at review. A `DONE` disposition carrying
an unfilled test delta is exactly what that class is for, and recording it
honestly here is what lets review catch it.

If a requirement is not implementable — a definition, a rationale, a statement of
scope — leave it out and say how many you excluded and why. Do not give it a
disposition.

### Part 2 — the SPEC → CODE → TEST mapping

One block per implementable requirement, exactly these fields:

```text
Requirement ID:
Spec location:
Normative requirement:

Disposition:
DONE | PARTIAL | MISSING | CONFLICT

Current code:
Current tests:

Required implementation delta:
Required deterministic/conformance test:
Dependencies/blockers:
```

`Spec location` is a section reference, not a paraphrase. `Normative requirement`
quotes the specification rather than restating it in your own words: the point of
the mapping is that someone can check it against the source.

Where the disposition is `DONE`, `Required implementation delta` is `none`. Where
it is anything else, the delta is the smallest change that satisfies the
requirement, not the change you would prefer to make.

The two deltas are independent. `Required implementation delta: none` alongside a
real `Required deterministic/conformance test` is a normal and expected pairing:
it says the code is there and nothing verifies it. Do not let one field's `none`
pull the other toward `none`.

`Required deterministic/conformance test` must name a test that can fail. "Verify
the behaviour is correct" is not a test. If you cannot state how the test
distinguishes conforming from non-conforming behaviour, say so under
`Dependencies/blockers` instead of writing an untestable line.

Where an adequate test already exists, name it and write `none`. Where none
exists, the delta is required whatever the disposition says, including on `DONE`.

### Part 3 — the bounded implementation plan

Only changes justified by the audit above. Every plan item cites the requirement
IDs it serves. An item that serves no requirement does not belong in the plan,
however sensible it looks.

State the plan's own limits explicitly:

```text
Requirements this plan does not address, and why
Requirements whose delta is uncertain, and what would resolve it
Ordering constraints between plan items
```

## Constraints

Do not implement. Do not write code beyond what a delta description needs to be
unambiguous. No file is modified at this stage.

Do not widen the specification. If the specification is silent on something the
implementation will need, that is a `Dependencies/blockers` entry and a question
for the human gate, not a gap for you to fill by choosing.

Do not manufacture a baseline. If there is no executable implementation, say so
once, plainly, and audit against nothing.

## What this audit does not establish

That the specification is correct, complete, or internally consistent. You are
measuring code against spec, in that direction only. Where the specification
contradicts itself, record it under `Dependencies/blockers` and continue; it is
the human's to resolve, not yours.
