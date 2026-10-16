# Review evidence schema v1.0

Frozen structure for review-cycle evidence under the implementation and review
protocol. MC-2 checks evidence against this schema, so the schema must be frozen
before any cycle is written: a checker cannot validate a structure that is still
moving.

Derived against the protocol source containing §2.2 and §10.2, which specifies
**fifteen** MC-2 checks — 1 to 10 for every cycle, 11 to 15 additionally and
unconditionally for implementation review.

## Status of this document

```text
MC1_ENFORCEMENT   CONVENTION_ONLY
```

Decided before Run 1 rather than discovered during it. The implementing agent
and the review evidence share one effective write authority on the current
single-user Windows environment, so a technical immutability claim is not
supportable. Per MC-1, claims that Codex findings are immutable or that review
input is technically protected **must not be made** while this holds.

Upgrade to `TECHNICALLY_ENFORCED` only when authoritative review evidence sits
behind a write boundary the implementing agent does not have.

## Directory layout

```text
runs/
  A1E-001/
    run.json
    baseline/
    plan-review/
      cycle-01/
        target.json
        target.sha256
        codex-input.md
        codex-output-raw.md
        invocation.json        written by the runner at record time
        findings.json          written by the runner
        claude-response.md     written by the implementing agent
      cycle-02/
        ...
    plan-approval/
      approval.json            freezes APPROVED_PLAN_HASH, per Step 7.3
    implementation-review/
      cycle-01/
        ...
    code-approval/
    gold/
```

Cycle directories are `cycle-NN`, zero-padded, starting at `01`. The number is
the cycle identifier and must be unique within its review directory.

## `target.json`

The frozen artifact identity for one cycle. Hashed as a file; that hash is what
binds the cycle together.

Common fields, both review types:

```json
{
  "review_type": "plan" | "implementation",
  "run_id": "A1E-001",
  "cycle": 1,
  "protocol_commit": "…",
  "protocol_sha256": "…",
  "spec_sha256": "…",
  "frozen_at": "2026-09-08T13:40:00Z"
}
```

Plan review adds:

```json
{
  "plan_files": [
    { "path": "runs/A1E-001/plan/01-PLAN.md", "sha256": "…" }
  ]
}
```

Implementation review adds the §10.1 fields. All five are mandatory, not
conditional:

```json
{
  "candidate_commit":    "…",
  "candidate_tree_hash": "…",
  "approved_plan_hash":  "…",
  "diff_path":           "…",
  "diff_hash":           "…",
  "test_result_path":    "…",
  "test_result_hash":    "…"
}
```

`candidate_tree_hash` is derived by the runner from `candidate_commit`, never
supplied by hand. A tree hash typed in by an operator is a tree hash that can be
typed to match whatever was recorded.

## `target.sha256`

One line: the lowercase hex SHA-256 of `target.json`, nothing else.

## `codex-input.md`

Composed by the review runner, never by the implementing agent (§2.2). Must
contain the `target.sha256` value verbatim somewhere in its text — MC-2 check
10. That string is the binding between what was frozen and what the reviewer was
actually shown.

Freezing the target proves the artifact did not change. Only the embedded hash
ties that artifact to the input the reviewer received. This is the control whose
absence made the GSD pilot's criterion 1 unprovable.

## `codex-output-raw.md`

Exactly what Codex returned, captured before any parsing, summarisation or
response. No repair may occur before this file exists.

## Schema-level concretisations

The protocol names logical artifacts; a checker needs to find them on disk.
These are instantiations of the protocol, not changes to it, per Alex Zamurko's
ruling of 8 September on D-3, restated 8 September 2026, 11:01 PM:

    use target.json as the concrete schema/filesystem representation of the
    protocol's logical target. This is an implementation concretisation, not a
    semantic change. The mapping should be documented explicitly so the
    protocol term target remains normative.

So `target` is the normative term and `target.json` is only how this
implementation stores it. Anything reasoning about the protocol says `target`;
only code touching the filesystem says `target.json`. A future implementation
storing it under another name would still conform, and this table is the whole
of what would have to change.

```text
target          → the file target.json
DIFF_HASH       → diff_hash, plus diff_path so check 14 has an artifact to
                  hash. The protocol requires the hash to match the reviewed
                  diff; without a path there is nothing to match against.
TEST_RESULT_HASH→ test_result_hash, plus test_result_path, same reason.
APPROVED_PLAN_HASH
                → check 13 compares the target's value against
                  plan-approval/approval.json, which is where Step 7.3 freezes
                  it. Absent that record, the check fails rather than passing
                  vacuously.
```

## What MC-2 does not check

Stated so nobody reads a PASS as more than it is.

- That `codex-output-raw.md` came from the invocation `codex-input.md` describes.
  Nothing in the evidence proves that binding; it rests on the runner behaving,
  and `invocation.json` records how the review was run without claiming more.
- That the reviewer read the whole input.
- That findings in `findings.json` correspond to the raw output. A separate check
  could compare finding IDs against the raw text; it is not among the fifteen.
- Anything about content quality. MC-2 is an evidence-completeness gate.

Checks 11 to 15 do not apply to plan review and are reported `N/A` there, never
`PASS`. A check reporting success on a cycle it never examined would be the
exact defect this gate exists to catch.

Under `CONVENTION_ONLY` the gaps above are procedural, not technical, and the
protocol's language must reflect that.

## Bootstrap exception

Per Alex Zamurko, 8 September. The runner and this checker necessarily precede
the automated protocol they enable, so artifacts produced before both exist and
have passed bootstrap review are:

```text
BOOTSTRAP / DEVELOPMENT EVIDENCE — NOT_A_PROTOCOL_CYCLE
```

They are not invalid cycles requiring retrospective interpretation. They are not
cycles. No `A1E-001` protocol cycle may be created until the evidence schema is
frozen and the MC-2 checker exists and has passed its own bootstrap review.
