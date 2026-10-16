# Review input — BOOTSTRAP-001 / plan review / cycle 01

```text
TARGET_SHA256   22c86a1b4bd6b9b0c304bb4113b552df30801b61c35e134df95db1882d2e07b8
PROTOCOL_SHA256 296594a3c06cd2f9c66976c369b15804f39bbb2be37b5e62234d37fafd28d483
SPEC_SHA256     ad7f1099b66263123795dc2bf15f8275ad290bf91cdb0f5efaa09a942a8f321f
```

The target hash above is the binding between the frozen artifact and this
input. Quote it in your response.

---

# Bootstrap review prompt

Frozen for the `BOOTSTRAP_REVIEW` of the execution layer. Hand-written, per Alex
Zamurko, 8 September: a hand-written prompt is acceptable for the bootstrap and
the five production prompts are built and frozen before A1E-001.

This is **not** one of the five. It is used once, on the components that had to
exist before the protocol could run at all.

Revised twice, both times before use, and both times because it was written
before the thing it had to describe existed.

- 8 September. The first version named three artifacts. The ledger and loop
  controller were built after it was written, so calling it frozen was premature.
- 9 September. It did not name `scripts/bootstrap_gate.py`, the gate that now
  blocks every real cycle, and it predated Alex Zamurko's section mapping of the
  review scope. Both are below.

Nothing has been reviewed against any earlier text.

---

## What you are reviewing

Six artifacts, hashed and listed in `target.json`:

```text
specs/evidence-schema-v1.0.md   the frozen evidence structure
scripts/validate_cycle.py       the MC-2 conformance gate, fifteen checks
scripts/run_review.py           the review runner
scripts/ledger.py               the finding and state ledger
scripts/loop_state.py           the loop-state controller
scripts/bootstrap_gate.py       the gate enforcing this review
```

Their negative-control suites are supplied alongside as evidence that the checks
they contain are falsifiable:

```text
scripts/test_validate_cycle.py   24 controls
scripts/test_run_review.py       26 controls
scripts/test_ledger.py           37 controls, covering the ledger and controller
scripts/test_bootstrap_gate.py   24 controls
scripts/test_interfaces.py       12 controls, across six component seams
```

Those counts are asserted here and checked by `scripts/test_prompts.py` against
the suites themselves. A count typed into a prompt is a count that drifts, and
an inflated one would misrepresent how well controlled these components are to
the reviewer being asked to trust them.

## What you are reviewing them against

The protocol at the commit and hash recorded in `target.json`. That file is
authoritative for this review. Where this prompt and the protocol disagree, the
protocol governs and the disagreement is itself a finding.

Alex Zamurko fixed the scope on 9 September, and it maps directly rather than
being left to your judgement:

```text
scripts/validate_cycle.py   MC-2, and §10.2 for implementation review
scripts/run_review.py       §2.2 input composition, §10.1 target fields
scripts/ledger.py           §§5 and 12
scripts/loop_state.py       §§6 and 13
scripts/bootstrap_gate.py   no protocol section; see below
```

His reason for including the last two, in his words: they "determine the
authoritative meaning of otherwise valid review evidence", finding state and loop
outcome. An error there produces a false process outcome from evidence that
passes MC-2 cleanly.

`bootstrap_gate.py` implements no protocol section. It implements his ruling of
8 September that this review is mandatory before any real cycle. Review it
against that ruling and against whether it can be circumvented: it is the single
boolean standing between development evidence and a live protocol run, and it
covers itself in its own hash set precisely because an earlier version did not.

## The question

Do these six artifacts implement §2.2, §5, §6, §10.1, §10.2, MC-1 and MC-2 as
written, and do their controls actually establish what they claim?

Two failure modes matter more than the rest.

**A check that cannot come back false.** The v1.0 gate-hardening milestone found
thirteen of these. A check whose failure branch is unreachable reports success
while testing nothing. For every check in `validate_cycle.py` and every refusal
in `run_review.py`, ask whether the supplied controls demonstrate it firing, or
whether the control merely exercises the same code path under a different name.
Checks 1 to 4 are one mechanism, file existence, and only check 4 is
demonstrated; that specific weakness is already known and does not need
reporting, but comparable cases elsewhere do.

**A claim stronger than its evidence.** `MC1_ENFORCEMENT` is
`CONVENTION_ONLY` on this environment. Flag any language in the schema, the
scripts or their documentation that implies technical protection, immutability,
or a proven binding between reviewer input and reviewer output.

## Decisions already declared

The protocol underdetermines these, and each was resolved to build at all. They
are disclosed so you assess them rather than rediscover them. Undeclared
deviations you find are ordinary findings.

```text
A  target is instantiated on disk as target.json, and DIFF_HASH and
   TEST_RESULT_HASH are paired with diff_path and test_result_path so
   checks 14 and 15 have an artifact to hash. Ruled a schema-level
   concretisation, not a protocol change. See evidence-schema-v1.0.md.

B  candidate_tree_hash is derived by the runner from candidate_commit and
   never supplied by the operator. A hand-typed tree hash can be typed to
   match whatever was recorded.

C  Checks 11 to 15 report N/A on a plan cycle, never PASS. §10.2 scopes them
   to implementation review, and reporting PASS for a check that was never
   evaluated is the defect this gate exists to catch.

D  ACCEPT records a disposition and leaves the finding OPEN. §5 gives
   RESOLVED only "once the repair is demonstrated in the next review
   target", so ledger.py refuses to resolve in the same cycle as the
   acceptance. The protocol does not say who declares a repair demonstrated;
   `resolve` requires an evidence string rather than inventing an answer.

E  DISPUTED is terminal in the automated loop. §5 and §7.1 place adjudication
   at the human gate, so nothing here moves a finding out of it.

F  Check 13 compares approved_plan_hash against
   plan-approval/approval.json, where §7.3 freezes it. Absent that record the
   check fails rather than passing vacuously.

G  loop_state.py runs the MC-2 gate itself rather than reading a recorded
   verdict, so §6's n indexes VALID cycles and events recorded in an invalid
   cycle are ignored entirely, including resolutions. This is the
   conservative reading: it can delay an exit, never manufacture one.
```

D and G are the two most worth arguing with. D decides when a finding stops
being open, and G decides what counts as a cycle at all.

## Output format

Use only this closed vocabulary:

```text
MISSING REQUIREMENT
WRONG OWNERSHIP
NONDETERMINISTIC WHERE D POSSIBLE
SEMANTIC STEP TOO BROAD
UNTESTED RULE
CONTRADICTORY IMPLEMENTATION MAPPING
```

One block per finding, persistent identifier, cycle 01:

```text
Finding ID: B01-F01
Class:
Artifact:
Location:
Evidence:
Finding:
Required correction:
```

Quote the `TARGET_SHA256` from the top of this input in your first line, so the
response is bound to the exact artifacts you were shown.

If you find nothing in a category, say so explicitly rather than omitting it.
An empty review is a finding about the review, not about the code.

## Scope limits

Out of scope: style, performance, and anything in `specs/gap/`. Naming is out of
scope except where decision A is wrong.

Not yet built, so their absence is not a finding: the human review package
generator (§7) and the Gold runner (§15). The implementing agent has not written
a plan or an implementation yet, so there is no A1E-001 evidence to review; this
is the tooling only.

The five production prompts `specs/prompts/01`–`05` **do** exist and are not in
this target. Their absence from the review is a scoping decision, not a claim
that they are unwritten, and if you think the six artifacts cannot be judged
without them, say so as a finding.

---

# The governing protocol

`specs/implementation-review-protocol-v1.1.md`, sha256 `296594a3c06cd2f9c66976c369b15804f39bbb2be37b5e62234d37fafd28d483`.

This is the document the artifacts below are reviewed against. Where
it and the review prompt disagree, this governs.

```
Claude–Codex Minimal Implementation and Review Workflow
0. Protocol governance and baseline
0.1 Governing protocol
This workflow is a version-controlled governing specification.
Before any implementation run begins, the authoritative protocol must itself be committed to git.
Recommended location:
specs/implementation-review-protocol-v1.1.md

Record:
PROTOCOL_PATH
PROTOCOL_VERSION
PROTOCOL_COMMIT
PROTOCOL_HASH

The authoritative protocol is the git-controlled artifact.
Slack, chat history, .docx drafts, or other transient communication channels are not authoritative copies.
Every implementation run must reference the exact protocol version, commit, and hash used.
No implementation run may begin until these fields are populated.

0.2 Freeze the specification and baseline
Record:
SPEC_PATH
SPEC_VERSION
SPEC_HASH

BASELINE_COMMIT
BASELINE_TEST_RESULT
BASELINE_GOLD_RESULT
GOLD_SET_VERSION
GOLD_SET_HASH

If no executable implementation exists yet:
BASELINE_COMMIT: NONE
BASELINE_TEST_RESULT: NOT_APPLICABLE
BASELINE_GOLD_RESULT: NOT_APPLICABLE
REASON: no executable baseline implementation

A baseline result must never be manufactured retrospectively.
Where an executable baseline exists, the frozen Gold Set must be run before implementation.

1. Claude audits frozen spec → current code
Claude audits every implementable requirement in the frozen specification against the current implementation.
Each requirement receives exactly one disposition:
DONE
PARTIAL
MISSING
CONFLICT

Claude produces:
SPEC → CODE → TEST mapping

For each requirement:
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

Claude then produces a bounded implementation plan containing only changes justified by the audit.
No implementation occurs at this stage.

2. Plan review loop — Claude ↔ Codex
Maximum:
4 VALID CODEX REVIEW CYCLES

Only cycles that pass the MC-2 conformance gate count toward this maximum.

2.1 Freeze the review target for every cycle
Every cycle receives its own directory.
Example:
plan-review/
cycle-01/
cycle-02/
cycle-03/
cycle-04/

Before Codex review:
target
target.sha256

must be created.
target identifies or contains the exact plan artifact to be reviewed in that cycle.
A repaired plan creates a new target and therefore a new review cycle.

2.2 Review runner composes the Codex input
The implementing agent does not construct or supply the authoritative Codex review input.
The review runner:
reads the frozen target;
calculates/verifies target.sha256;
composes codex-input.md;
includes the exact target SHA-256 verbatim in codex-input.md;
supplies the frozen target or its exact referenced content to Codex;
writes the resulting Codex output to the review evidence directory.
Required relationship:
target
↓
review runner
↓
codex-input.md
↓
Codex
↓
codex-output-raw.md

The implementing agent may trigger the review process but may not alter the authoritative codex-input.md after composition.

3. Mandatory controls for every Codex review cycle
MC-1 — Reviewer input/output boundary
Codex review evidence must be technically separated from the implementing agent where infrastructure permits.
The review runner owns creation of:
target.sha256
codex-input.md
codex-output-raw.md
findings.json

After capture:
Claude / implementing agent:

READ:
permitted where required

WRITE:
denied

DELETE:
denied

for authoritative review evidence.
Claude may write separately:
claude-response.md
repaired-target

Claude may not overwrite:
codex-input.md
codex-output-raw.md
findings.json

Input-side control
The review runner, not Claude, composes codex-input.md from the frozen target.
Therefore the implementing agent does not control either:
what authoritative artifact Codex is shown
or
what authoritative Codex response is retained

Enforcement status
Each run records:
MC1_ENFORCEMENT:
TECHNICALLY_ENFORCED
or
CONVENTION_ONLY

If infrastructure cannot enforce write/delete restrictions:
MC1_ENFORCEMENT: CONVENTION_ONLY

must be recorded.
In that case, claims such as:
Codex findings are immutable
review input is technically protected

must not be made.
The protocol then provides procedural discipline, not a technical guarantee.

MC-2 — Per-cycle evidence completeness and target-binding gate
Every completed review cycle must contain:
target
target.sha256
codex-input.md
codex-output-raw.md

A deterministic conformance check must verify:
1. target exists

2. target.sha256 exists

3. codex-input.md exists

4. codex-output-raw.md exists

5. all required files are non-empty

6. SHA256(target)
==
value recorded in target.sha256

7. cycle identifier is unique

8. where target references a git commit:
referenced commit exists

9. all mandatory hashed artifacts for that review type
are present and their recorded hashes match the referenced artifacts

10. codex-input.md contains the exact target SHA-256 verbatim

Check 10 creates the required binding:
frozen target
↕
target SHA-256
↕
actual Codex input

A review is therefore not valid merely because a frozen artifact and a Codex response both exist. The recorded input must demonstrably reference the exact frozen target.
Result:
MC2_CONFORMANCE:
PASS | FAIL

If:
MC2_CONFORMANCE = FAIL

then:
REVIEW_CYCLE_STATUS = INVALID

An invalid cycle:
cannot support an authoritative Codex finding;
cannot count toward CONVERGED;
cannot count toward HUMAN_ADJUDICATION_REQUIRED;
cannot count toward STALLED;
cannot count toward MAX_4_REACHED;
cannot consume one of the four valid review cycles.
The evidence failure must be corrected and the review rerun.

MC-3 — Gold Set performance is comparative where a baseline exists
Where executable baseline code exists, preserve Gold Set results:
BEFORE implementation
AND
AFTER final implementation

using the same frozen Gold Set version/hash.
Where no executable baseline exists:
BASELINE_GOLD_RESULT = NOT_APPLICABLE

and the candidate is evaluated against predefined Gold acceptance criteria.

4. Codex reviews the implementation plan
Codex reviews the exact frozen plan against the frozen specification.
Codex uses the following closed finding vocabulary:
MISSING REQUIREMENT

WRONG OWNERSHIP

NONDETERMINISTIC WHERE D POSSIBLE

SEMANTIC STEP TOO BROAD

UNTESTED RULE

CONTRADICTORY IMPLEMENTATION MAPPING

Every finding receives a persistent identifier.
Example:
Finding ID: C02-F03
Class: UNTESTED RULE
Requirement ID: R-B7
Evidence:
Finding:
Required correction:

The vocabulary remains unchanged across cycles so that finding sets remain comparable.
The raw Codex response is captured before summarisation, interpretation, or Claude response.

5. Claude responds to Codex findings
Claude must respond to every finding with exactly one disposition:
ACCEPT

or:
REJECT_WITH_REASON

ACCEPT
Claude accepts the finding and repairs the plan.
The original Codex finding remains unchanged in the authoritative review record.
Its state becomes:
RESOLVED

once the repair is demonstrated in the next review target.

REJECT_WITH_REASON
Claude records:
Finding ID:
Disposition: REJECT_WITH_REASON
Reason:
Spec evidence:

Claude does not erase, rewrite, or close the Codex finding.
Its state becomes:
DISPUTED

and requires human adjudication.

6. Mechanically determine the plan-loop state
For each valid cycle, every Codex finding has one current state:
OPEN
RESOLVED
DISPUTED

Define:
OPEN_n
= set of actionable OPEN finding IDs after cycle n

RESOLVED_NEW_n
= findings that were OPEN after cycle n-1
and became RESOLVED during cycle n

DISPUTED_NEW_n
= findings that were OPEN after cycle n-1
and became DISPUTED during cycle n

For cycle n > 1, progress exists iff:
|OPEN_n| < |OPEN_n-1|

OR

RESOLVED_NEW_n is non-empty

OR

DISPUTED_NEW_n is non-empty

A newly recorded dispute counts as progress because an unresolved finding has been converted into an explicit human-adjudication issue.
Merely re-raising an already existing dispute does not count as progress.

Exit A — CONVERGED
OPEN_n = ∅
AND
DISPUTED_n = ∅

Stop the automated plan loop.
Proceed to human plan review with:
LOOP_STATUS = CONVERGED

Exit B — HUMAN_ADJUDICATION_REQUIRED
OPEN_n = ∅
AND
DISPUTED_n ≠ ∅

All actionable findings have been resolved or converted into disputes, and no further automated repair is available.
Stop the automated plan loop immediately.
Proceed to human plan review with:
LOOP_STATUS = HUMAN_ADJUDICATION_REQUIRED

Exit C — STALLED
For any valid cycle n > 1:
STALLED
IFF

|OPEN_n| >= |OPEN_n-1|

AND

RESOLVED_NEW_n = ∅

AND

DISPUTED_NEW_n = ∅

The immediately preceding valid cycle therefore produced:
no reduction in open actionable findings;
no newly resolved finding;
no newly disputed finding.
Stop the automated loop immediately.
Proceed to human plan review with:
LOOP_STATUS = STALLED

Exit D — MAX_4_REACHED
If:
VALID_CYCLE_COUNT = 4

and none of CONVERGED, HUMAN_ADJUDICATION_REQUIRED, or an earlier STALLED exit occurred:
LOOP_STATUS = MAX_4_REACHED

Stop automated review.

Otherwise — CONTINUE
If:
not CONVERGED
not HUMAN_ADJUDICATION_REQUIRED
not STALLED
VALID_CYCLE_COUNT < 4

Claude repairs the plan.
A new plan version is produced.
Return to Step 2 and create a new per-cycle review target.

7. Human review of the implementation plan
Human review occurs after:
CONVERGED
HUMAN_ADJUDICATION_REQUIRED
STALLED
or
MAX_4_REACHED

These states are not equivalent.
The review package must contain:
final plan
final plan hash

loop status
valid iteration count

SPEC → CODE → TEST mapping

resolved findings
disputes
unresolved findings

MC-1 enforcement status
MC-2 conformance results for every valid cycle

7.1 Disputes
A dispute is:
Codex finding
+
Claude REJECT_WITH_REASON

The human adjudicates the dispute.

7.2 Unresolved findings
An unresolved finding remains:
OPEN

The human determines whether it:
requires correction
is explicitly waived/accepted
or
causes rejection of the plan

Disputes and unresolved findings must be presented separately.

7.3 Human decision
Permitted outcomes:
APPROVE
RETURN_FOR_REWORK
REJECT

If approved:
APPROVED_PLAN_HASH
APPROVAL_RECORD

are frozen.

8. Claude implements the approved plan
Claude implements only the exact approved plan.
Before Codex implementation review, run:
build/check
deterministic tests
conformance tests
regression tests

Mechanical or deterministic failures return directly to Claude for repair.

9. PLAN_DEVIATION control
A material change outside the approved plan may not be introduced silently.
If implementation requires such a change:
1. STOP implementation.

2. Record:
PLAN_DEVIATION_ID
reason
affected requirement
proposed plan change
affected code/tests

3. Do not implement the deviation.

4. Return to Step 7:
HUMAN REVIEW OF THE IMPLEMENTATION PLAN.

5. Human reviews the revised plan.

6. If approved:
freeze new APPROVED_PLAN_HASH.

7. Resume implementation only against the newly approved plan.

Therefore:
MATERIAL PLAN DEVIATION
→ MANDATORY RETURN TO HUMAN PLAN APPROVAL

A deviation cannot be legitimised retrospectively during code review.

10. Implementation review loop — Claude ↔ Codex
Maximum:
4 VALID CODEX REVIEW CYCLES

The same MC-1, MC-2 and loop-state rules apply.
Every cycle receives its own directory:
implementation-review/
cycle-01/
cycle-02/
cycle-03/
cycle-04/

10.1 Freeze the exact implementation target per cycle
For implementation review, the target must identify all of the following:
CANDIDATE_COMMIT
CANDIDATE_TREE_HASH
APPROVED_PLAN_HASH
DIFF_HASH
TEST_RESULT_HASH

These fields are mandatory, not conditional.
The target must bind the review to:
exact candidate code
exact approved plan
exact implementation diff
exact deterministic/conformance/regression results

Before Codex review:
target
target.sha256

are frozen.
The review runner then composes:
codex-input.md

from that frozen target and includes target.sha256 verbatim.
After Codex returns:
codex-output-raw.md

is captured before any implementation repair.

10.2 Implementation-specific MC-2 checks
For every implementation review cycle, the conformance gate must additionally and unconditionally verify:
11. candidate commit is present and exists

12. candidate tree hash is present
and matches the candidate tree

13. approved-plan hash is present
and matches the frozen approved plan

14. diff hash is present
and matches the exact reviewed diff

15. test-result hash is present
and matches the exact supplied test results

Failure of any check makes the cycle:
INVALID

and it does not consume the four-cycle budget.

11. Codex reviews the exact implementation
Codex receives:
frozen specification
approved plan
exact candidate commit/hash
exact implementation diff
relevant tests
deterministic/conformance/regression results

The authoritative codex-input.md is composed by the review runner, not by Claude.
Codex uses the same closed finding vocabulary:
MISSING REQUIREMENT
WRONG OWNERSHIP
NONDETERMINISTIC WHERE D POSSIBLE
SEMANTIC STEP TOO BROAD
UNTESTED RULE
CONTRADICTORY IMPLEMENTATION MAPPING

The raw review is preserved through MC-1 and MC-2.

12. Claude responds and repairs
For every finding:
ACCEPT
→ repair implementation

or:
REJECT_WITH_REASON
→ preserve as DISPUTED

Claude cannot modify the authoritative Codex evidence where MC-1 is technically enforced.
A repair creates a new candidate and therefore a new review cycle.

13. Determine implementation-loop exit
Use exactly the same mechanically defined states and exit order as the plan loop:
CONVERGED
HUMAN_ADJUDICATION_REQUIRED
STALLED
MAX_4_REACHED
CONTINUE

HUMAN_ADJUDICATION_REQUIRED
IFF

OPEN_n = ∅
AND
DISPUTED_n ≠ ∅

When this state is reached, stop the automated implementation-review loop immediately and proceed to Step 14 for human adjudication.
No separate or subjective implementation-loop definition is permitted.

14. Human review of final code
Human review occurs after:
CONVERGED
HUMAN_ADJUDICATION_REQUIRED
STALLED
or
MAX_4_REACHED

The review package contains:
frozen specification
approved plan
candidate commit/hash

exact implementation diff
deterministic test results
conformance test results
regression test results

resolved findings
disputes
unresolved findings

loop status
valid iteration count

MC-1 enforcement status
MC-2 result for every valid cycle

any approved plan deviations

Human decision:
APPROVE
RETURN_FOR_REWORK
REJECT

If approved, freeze the exact candidate commit/hash.

15. Gold Set validation
15.1 Existing executable baseline
Run the same frozen Gold Set against:
BASELINE
vs
FINAL CANDIDATE

Compare at minimum:
targeted improvements
previously correct cases retained
new false positives
new false negatives
regressions
aggregate performance

Aggregate improvement does not override an unacceptable regression.

15.2 No executable baseline
Record:
BASELINE_GOLD_RESULT = NOT_APPLICABLE

Run the frozen Gold Set against the candidate and evaluate against predefined acceptance criteria.

16. Final freeze / release decision
The release evidence contains:
PROTOCOL_PATH
PROTOCOL_VERSION
PROTOCOL_COMMIT
PROTOCOL_HASH

SPEC_VERSION
SPEC_HASH

APPROVED_PLAN_HASH
FINAL_CANDIDATE_COMMIT
FINAL_CANDIDATE_HASH

PLAN_LOOP_STATUS
IMPLEMENTATION_LOOP_STATUS

MC1_ENFORCEMENT
MC2_CONFORMANCE_RESULTS

DISPUTE DISPOSITIONS
UNRESOLVED-FINDING DISPOSITIONS

BASELINE_GOLD_RESULT
FINAL_GOLD_RESULT
GOLD_COMPARISON

FINAL HUMAN DECISION

Only then is the capability frozen/released.

Minimal execution view
0. PROTOCOL + BASELINE
Commit/version protocol in git.
Record protocol path/version/commit/hash.
Freeze spec.
Freeze existing baseline tests + Gold.
If no executable baseline → mark N/A.

1. CLAUDE AUDIT + PLAN
DONE / PARTIAL / MISSING / CONFLICT
SPEC → CODE → TEST
bounded plan
deterministic/conformance tests

2. PLAN REVIEW LOOP
EACH cycle:
freeze exact target
hash exact target

review runner:
composes Codex input from target
embeds target SHA-256 in input

capture raw Codex output

enforce MC-1
run MC-2 target/evidence/input-binding gate

Codex reviews with closed finding vocabulary

Claude:
ACCEPT → repair
REJECT_WITH_REASON → DISPUTED

Mechanical exit:
CONVERGED
HUMAN_ADJUDICATION_REQUIRED
STALLED
MAX 4 valid cycles

3. HUMAN PLAN REVIEW
separately review:
disputes
unresolved findings

approve / return / reject
freeze approved plan

4. CLAUDE IMPLEMENTS
deterministic/conformance/regression checks

MATERIAL PLAN DEVIATION
→ STOP
→ return to human plan review

5. CODE REVIEW LOOP
EACH cycle:
freeze exact candidate target containing:
commit
tree hash
approved-plan hash
diff hash
test-result hash

review runner:
composes Codex input from target
embeds target SHA-256

capture raw Codex output

enforce MC-1
run MC-2 including all mandatory implementation hashes

Codex reviews exact implementation

Claude:
ACCEPT → repair
REJECT_WITH_REASON → DISPUTED

Mechanical exit:
CONVERGED
HUMAN_ADJUDICATION_REQUIRED
STALLED
MAX 4 valid cycles

6. HUMAN CODE REVIEW

7. GOLD SET
baseline ↔ candidate if baseline exists
otherwise candidate ↔ predefined acceptance criteria

8. FINAL FREEZE / RELEASE

Verification and preservation table
| ID | Required element | Source | Implemented in workflow | Verification criterion | Status |
|---|---|---|---|---|---|
| V01 | Claude audits frozen spec against current code | Original prompt | Step 1 | Audit occurs before planning/implementation | PRESERVED |
| V02 | DONE / PARTIAL / MISSING / CONFLICT | Original prompt | Step 1 | Every implementable requirement receives exactly one disposition | PRESERVED |
| V03 | SPEC → CODE → TESTmapping | Original prompt | Step 1 | Mapping exists for every requirement | PRESERVED |
| V04 | Add deterministic/conformance tests | Original prompt | Steps 1, 8 | Tests are specified in plan and run during implementation | PRESERVED |
| V05 | Send implementation plan to Codex | Original prompt | Steps 2–4 | Every valid plan cycle contains Codex review evidence | PRESERVED |
| V06 | Codex assesses contradictions/problems | Original prompt | Step 4 | Review uses closed finding vocabulary | PRESERVED + STRENGTHENED |
| V07 | Claude solves accepted Codex findings | Original prompt | Step 5 | ACCEPT produces a repair | PRESERVED |
| V08 | Claude cannot silently dismiss findings | Mandatory control | Steps 3, 5 | Only ACCEPT or REJECT_WITH_REASON permitted | ENFORCED |
| V09 | 3–4 iteration limit | Original prompt | Steps 2, 10 | Maximum fixed at 4 valid cycles | PRESERVED |
| V10 | Stop early when complete | Original intent | Step 6 | CONVERGED terminates loop immediately | PRESERVED |
| V11 | Distinguish CONVERGED / HUMAN_ADJUDICATION_REQUIRED / STALLED / MAX 4 | Prior comments | Steps 6, 13 | Four distinct recorded exit states | ENFORCED |
| V12 | STALLED exact predicate | Decision 1 | Step 6 | Mechanically defined using open/resolved/disputed state changes | ENFORCED |
| V13 | Newly disputed finding counts as progress | Comments | Step 6 | DISPUTED_NEW_n prevents false stall | ENFORCED |
| V14 | Re-raised dispute is not new progress | Comments | Step 6 | Only newly disputed findings count | ENFORCED |
| V15 | Human plan approval after loop | Original prompt | Step 7 | Human gate reached after all four terminal states | PRESERVED |
| V16 | STALLED explicitly reaches human review | Comments | Steps 6–7 | Explicit transition to Step 7 | ENFORCED |
| V17 | MAX 4 is not treated as convergence | Comments | Steps 6–7 | Status remains MAX_4_REACHED | ENFORCED |
| V18 | Disputes separate from unresolved findings | Comments | Step 7 | Separate review categories | ENFORCED |
| V19 | Human adjudicates disputes | Comments | Step 7 | REJECT_WITH_REASON requires human decision | ENFORCED |
| V20 | Claude implements approved plan | Original prompt | Step 8 | APPROVED_PLAN_HASH frozen before implementation | PRESERVED + STRENGTHENED |
| V21 | Plan deviations cannot be silent | Prior workflow | Step 9 | Explicit deviation record required | PRESERVED + STRENGTHENED |
| V22 | Material deviation returns to plan approval | Decision 4 | Step 9 | Mandatory stop and return to Step 7 | ENFORCED |
| V23 | Deterministic checks before code review | Original prompt | Step 8 | Build/test/conformance/regression checks precede Codex | PRESERVED |
| V24 | Codex reviews exact implementation | Original prompt | Steps 10–11 | Exact candidate, diff, plan and tests are supplied | PRESERVED |
| V25 | Claude↔Codex implementation loop | Original prompt | Steps 10–13 | Repeatable repair/review loop remains | PRESERVED |
| V26 | Code loop capped at 4 | Original prompt | Step 10 | Cap is four valid cycles | PRESERVED |
| V27 | Human code review after loop | Original prompt | Step 14 | Human review follows any terminal state | PRESERVED + CLARIFIED |
| V28 | Review target frozen per cycle | Mandatory control | Steps 2, 10 | Every cycle has its own target/hash | ENFORCED |
| V29 | Exact Codex input captured per cycle | Mandatory control | Steps 2–3, 10 | codex-input.md required | ENFORCED |
| V30 | Raw Codex output captured per cycle | Mandatory control | Steps 2–3, 10 | codex-output-raw.md required before repair | ENFORCED |
| V31 | MC-2 mechanically checked | Decision 2 | Step 3 | Deterministic conformance gate runs every cycle | ENFORCED |
| V32 | Invalid evidence cycle does not count | Decision 2 | Step 3 | Invalid cycle excluded from all loop-state calculations | ENFORCED |
| V33 | target.sha256 matches target | Prior comments | Step 3 | SHA-256 equality required | ENFORCED |
| V34 | Codex input is bound to target | Latest comments | Step 3 | codex-input.md must contain exact target SHA-256 | ADDED / ENFORCED |
| V35 | Review runner composes Codex input from target | Latest comments | Steps 2.2, 3 | Implementing agent does not author authoritative review input | ADDED / ENFORCED |
| V36 | Implementing agent cannot control authoritative review input | Latest comments | Step 3 | Input composition owned by review runner | ADDED / ENFORCED WHERE SUPPORTED |
| V37 | Codex findings technically protected | Decision 3 | Step 3 | Implementing agent lacks write/delete rights to authoritative evidence | ENFORCED WHERE SUPPORTED |
| V38 | If technical enforcement absent, claim downgraded | Decision 3 | Step 3 | CONVENTION_ONLY explicitly recorded | ENFORCED |
| V39 | Closed Codex finding vocabulary | Prior comments | Steps 4, 11 | Same six finding classes across cycles | ENFORCED |
| V40 | Persistent finding IDs | Prior control logic | Steps 4–5 | Same issue retains same ID | ENFORCED |
| V41 | Gold baseline before implementation | Mandatory control | Step 0 | Baseline Gold captured before implementation when executable baseline exists | ENFORCED |
| V42 | No fabricated baseline | Prior comments | Steps 0, 15 | First implementation may use explicit NOT_APPLICABLE | ENFORCED |
| V43 | Final Gold Set after implementation | Original prompt | Step 15 | Final frozen candidate is evaluated | PRESERVED |
| V44 | Gold checks regressions, not only aggregate gain | Prior workflow | Step 15 | FP/FN/retention/regression explicitly compared | PRESERVED |
| V45 | Protocol committed to git | Decision 5 | Step 0 | Run cannot begin without committed authoritative protocol | ENFORCED |
| V46 | Protocol path/version/commit/hash recorded | Decision 5 | Steps 0, 16 | All four identifiers appear in run/release evidence | ENFORCED |
| V47 | Protocol itself satisfies its governance requirement | Latest comments | Step 0.1 | Authoritative artifact is git-controlled before first run | ADDED / ENFORCED |
| V48 | Implementation target includes candidate commit | Prior workflow | Step 10.1 | Mandatory target field | ENFORCED |
| V49 | Implementation target includes tree hash | Latest comments | Steps 10.1–10.2 | Presence and hash match mechanically checked | ADDED / ENFORCED |
| V50 | Implementation target includes approved-plan hash | Latest comments | Steps 10.1–10.2 | Presence and match mechanically checked | ADDED / ENFORCED |
| V51 | Implementation target includes diff hash | Latest comments | Steps 10.1–10.2 | Presence and match mechanically checked | ADDED / ENFORCED |
| V52 | Implementation target includes test-result hash | Latest comments | Steps 10.1–10.2 | Presence and match mechanically checked | ADDED / ENFORCED |
| V53 | Implementation hash checks are unconditional | Latest comments | Step 10.2 | Checks 11–15 required for every implementation review cycle | ADDED / ENFORCED |
| V54 | MC-2 failure cannot burn review budget | Prior catch | Steps 2, 3, 10 | Only valid cycles count toward MAX 4 | ENFORCED |
| V55 | Final freeze/release remains human-governed | Original workflow implication | Step 16 | Final human decision retained in release evidence | PRESERVED |
| V56 | HUMAN_ADJUDICATION_REQUIRED exit state | Latest comments | Steps 3, 6, 7, 13, 14 | OPEN_n = ∅ AND DISPUTED_n ≠ ∅ stops the loop and reaches human adjudication without CONTINUE/STALLED misclassification | ADDED / ENFORCED |

Preservation verdict
Original workflow elements dropped: 0

Previously mandatory controls dropped: 0

New requested changes executed: 5 / 5
1. codex-input.md bound to target SHA-256 ✓
2. review runner owns composition of Codex input ✓
3. implementation hashes made unconditional ✓
4. protocol must itself be committed/versioned ✓
5. HUMAN_ADJUDICATION_REQUIRED exit added and propagated through both review loops ✓

Current control chain
GIT-COMMITTED GOVERNING PROTOCOL
↓
FROZEN SPEC + BASELINE
↓
CLAUDE AUDIT / PLAN
↓
FROZEN REVIEW TARGET
↓
REVIEW RUNNER COMPOSES INPUT FROM TARGET
↓
TARGET HASH EMBEDDED IN CODEX INPUT
↓
CODEX REVIEW
↓
RAW OUTPUT CAPTURE
↓
MC-1 + MC-2 CONFORMANCE
↓
CLAUDE ACCEPT / REJECT_WITH_REASON
↓
CONVERGED | HUMAN_ADJUDICATION_REQUIRED | STALLED | MAX 4 VALID CYCLES
↓
HUMAN PLAN APPROVAL
↓
CLAUDE IMPLEMENTATION
│
└── MATERIAL PLAN DEVIATION
→ HUMAN PLAN APPROVAL
↓
DETERMINISTIC / CONFORMANCE / REGRESSION TESTS
↓
EXACT IMPLEMENTATION TARGET
(commit + tree + plan + diff + test hashes)
↓
REVIEW RUNNER → CODEX
↓
MC-1 + MC-2 CONFORMANCE
↓
CONVERGED | HUMAN_ADJUDICATION_REQUIRED | STALLED | MAX 4 VALID CYCLES
↓
HUMAN CODE REVIEW
↓
GOLD VALIDATION
↓
FINAL FREEZE / RELEASE
```

---

# Artifacts under review

## `specs/evidence-schema-v1.0.md`

`sha256 98a5920def59c39dc5c8bdbb5700376e21560ee40654173219a5ac0bef246379`

```
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
```

## `scripts/validate_cycle.py`

`sha256 3d9c570c3a9eb3efcdc2daf1201597af05ad9f20880c74b25f4f607856dcaf60`

```
#!/usr/bin/env python3
"""MC-2 conformance gate.

Checks one review cycle against specs/evidence-schema-v1.0.md and MC-2 of the
protocol, which specifies fifteen checks: 1 to 10 for every cycle, and 11 to 15
additionally and unconditionally for implementation review cycles (§10.2).

    python scripts/validate_cycle.py runs/A1E-001/plan-review/cycle-01

Exit 0 = PASS, exit 1 = FAIL, exit 2 = the checker could not run.

A FAIL means REVIEW_CYCLE_STATUS = INVALID: the cycle cannot support a finding
and cannot count toward CONVERGED, STALLED, MAX_4_REACHED, or the four-cycle
budget. It is repaired and rerun, not interpreted.

Checks 11 to 15 apply only to implementation review. On a plan review they are
reported N/A rather than PASS. A check that reports success on a cycle it never
examined is the defect this gate exists to prevent, and it would be perverse to
build one into the gate itself.

Written under the anti-whitelist rule: every check derives its expectation from
the protocol text, and nothing passes because a previous run accepted it.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = ("target.json", "target.sha256", "codex-input.md", "codex-output-raw.md")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")

COMMON_FIELDS = ("review_type", "run_id", "cycle", "protocol_commit",
                 "protocol_sha256", "spec_sha256", "frozen_at")

# §10.1: "These fields are mandatory, not conditional."
IMPL_FIELDS = ("candidate_commit", "candidate_tree_hash", "approved_plan_hash",
               "diff_hash", "test_result_hash")

NA = "N/A"


class Result:
    def __init__(self) -> None:
        self.checks: list[tuple[int, str, object, str]] = []

    def add(self, n: int, name: str, ok: object, detail: str = "") -> object:
        self.checks.append((n, name, ok, detail))
        return ok

    def na(self, n: int, name: str, why: str) -> None:
        self.checks.append((n, name, NA, why))

    @property
    def passed(self) -> bool:
        return all(ok is True or ok == NA for _, _, ok, _ in self.checks)

    def report(self, cycle_dir: Path) -> str:
        lines = [f"MC-2 conformance — {cycle_dir}", ""]
        for n, name, ok, detail in self.checks:
            mark = NA if ok == NA else ("PASS" if ok else "FAIL")
            lines.append(f"  {n:>2}. [{mark:^4}] {name}")
            if detail:
                for ln in detail.splitlines():
                    lines.append(f"          {ln}")
        lines += ["", f"MC2_CONFORMANCE: {'PASS' if self.passed else 'FAIL'}"]
        if not self.passed:
            lines.append("REVIEW_CYCLE_STATUS: INVALID")
            lines.append("This cycle does not count toward the four-cycle budget "
                         "or any loop state. Repair the evidence and rerun.")
        return "\n".join(lines)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo_root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo_root), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return 127, ""


def git_commit_exists(repo_root: Path, commit: str) -> bool:
    return git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}")[0] == 0


def _check_hashed_ref(entry, repo_root: Path, label: str) -> list[str]:
    if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
        return [f"{label} must be an object with path and sha256"]
    p = repo_root / entry["path"]
    if not p.is_file():
        return [f"{label} path not found: {entry['path']}"]
    actual = sha256_file(p)
    if actual != entry["sha256"]:
        return [f"{label} hash mismatch for {entry['path']}: "
                f"recorded {entry['sha256']}, actual {actual}"]
    return []


def _hash_of_declared_file(target: dict, hash_field: str, path_field: str,
                           repo_root: Path) -> tuple[bool, str]:
    """Recorded hash present, its artifact resolvable, and the two agree."""
    recorded = target.get(hash_field)
    if not recorded:
        return False, f"{hash_field} is absent; §10.1 makes it mandatory"
    if not HEX64.match(str(recorded)):
        return False, f"{hash_field} is not a lowercase 64-char hex digest"
    rel = target.get(path_field)
    if not rel:
        return False, (f"{path_field} is absent, so {hash_field} cannot be checked "
                       f"against anything. The protocol requires the hash to match "
                       f"the artifact; the schema records where that artifact is.")
    p = repo_root / rel
    if not p.is_file():
        return False, f"{path_field} not found: {rel}"
    actual = sha256_file(p)
    if actual != recorded:
        return False, f"{rel}\n          recorded {recorded}\n          actual   {actual}"
    return True, ""


def validate(cycle_dir: Path, repo_root: Path) -> Result:
    r = Result()

    # 1-4. required files exist
    missing = [n for n in REQUIRED_FILES if not (cycle_dir / n).is_file()]
    for i, name in enumerate(REQUIRED_FILES, start=1):
        present = (cycle_dir / name).is_file()
        r.add(i, f"{name} exists", present, "" if present else "not found")
    if missing:
        r.add(5, "all required files non-empty", False,
              f"skipped, missing: {', '.join(missing)}")
        for n in range(6, 16):
            r.add(n, "(not reached)", False, "earlier checks failed")
        return r

    # 5. non-empty
    empty = [n for n in REQUIRED_FILES if (cycle_dir / n).stat().st_size == 0]
    r.add(5, "all required files non-empty", not empty,
          f"empty: {', '.join(empty)}" if empty else "")

    # 6. SHA256(target) == target.sha256
    recorded = (cycle_dir / "target.sha256").read_text(encoding="utf-8").strip()
    actual = sha256_file(cycle_dir / "target.json")
    if not HEX64.match(recorded):
        r.add(6, "target.sha256 matches target", False,
              f"target.sha256 is not a lowercase 64-char hex digest: {recorded[:80]!r}")
    else:
        r.add(6, "target.sha256 matches target", recorded == actual,
              "" if recorded == actual else
              f"recorded {recorded}\n          actual   {actual}")

    try:
        target = json.loads((cycle_dir / "target.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        for n, name in ((7, "cycle identifier unique"),
                        (8, "referenced git commit exists"),
                        (9, "mandatory hashed artifacts present and matching")):
            r.add(n, name, False, f"target.json is not valid JSON: {e}"
                  if n == 7 else "target.json unreadable")
        for n, name in _impl_check_names():
            r.add(n, name, False, "target.json unreadable")
        _check_10(r, cycle_dir, recorded)
        return r

    rtype = target.get("review_type")

    missing_fields = [f for f in COMMON_FIELDS if f not in target]
    if missing_fields:
        r.add(7, "cycle identifier unique", False,
              f"target.json missing required fields: {', '.join(missing_fields)}")
    else:
        siblings = [d for d in cycle_dir.parent.iterdir()
                    if d.is_dir() and d != cycle_dir and (d / "target.json").is_file()]
        clashes = []
        for s in siblings:
            try:
                other = json.loads((s / "target.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if other.get("cycle") == target.get("cycle"):
                clashes.append(s.name)
        r.add(7, "cycle identifier unique", not clashes,
              f"cycle {target.get('cycle')} also declared by: {', '.join(clashes)}"
              if clashes else f"cycle {target.get('cycle')} in {cycle_dir.parent.name}")

    # 8. referenced git commit exists
    commits = [v for k, v in target.items()
               if k in ("commit", "protocol_commit", "candidate_commit")]
    if not commits:
        r.add(8, "referenced git commit exists", True, "no commit referenced")
    else:
        bad = [c for c in commits if not git_commit_exists(repo_root, str(c))]
        r.add(8, "referenced git commit exists", not bad,
              f"unresolvable: {', '.join(bad)}" if bad
              else f"resolved: {', '.join(map(str, commits))}")

    # 9. mandatory hashed artifacts for that review type
    problems: list[str] = []
    if rtype == "plan":
        files = target.get("plan_files")
        if not files:
            problems.append("plan review requires a non-empty plan_files list")
        else:
            for entry in files:
                problems += _check_hashed_ref(entry, repo_root, "plan_files entry")
    elif rtype == "implementation":
        absent = [f for f in IMPL_FIELDS if not target.get(f)]
        if absent:
            problems.append("§10.1 requires all of: " + ", ".join(absent))
    else:
        problems.append(f"review_type must be 'plan' or 'implementation', got {rtype!r}")
    r.add(9, "mandatory hashed artifacts present and matching", not problems,
          "; ".join(problems))

    _check_10(r, cycle_dir, recorded)

    # 11-15. implementation-specific, §10.2
    if rtype != "implementation":
        why = f"review_type is {rtype!r}; §10.2 applies to implementation review only"
        for n, name in _impl_check_names():
            r.na(n, name, why)
        return r

    # 11. candidate commit is present and exists
    cc = target.get("candidate_commit")
    if not cc:
        r.add(11, "candidate commit present and exists", False, "candidate_commit absent")
    else:
        ok = git_commit_exists(repo_root, str(cc))
        r.add(11, "candidate commit present and exists", ok,
              "" if ok else f"does not resolve in this repository: {cc}")

    # 12. candidate tree hash present and matches the candidate tree
    th = target.get("candidate_tree_hash")
    if not th:
        r.add(12, "candidate tree hash matches the candidate tree", False,
              "candidate_tree_hash absent")
    elif not cc:
        r.add(12, "candidate tree hash matches the candidate tree", False,
              "no candidate_commit to resolve a tree from")
    else:
        code, real = git(repo_root, "rev-parse", f"{cc}^{{tree}}")
        if code != 0:
            r.add(12, "candidate tree hash matches the candidate tree", False,
                  f"could not resolve the tree of {cc}")
        else:
            ok = str(th).lower() == real.lower()
            r.add(12, "candidate tree hash matches the candidate tree", ok,
                  "" if ok else f"recorded {th}\n          actual   {real}")

    # 13. approved-plan hash present and matches the frozen approved plan
    ap = target.get("approved_plan_hash")
    approval = cycle_dir.parent.parent / "plan-approval" / "approval.json"
    if not ap:
        r.add(13, "approved-plan hash matches the frozen approved plan", False,
              "approved_plan_hash absent")
    elif not approval.is_file():
        r.add(13, "approved-plan hash matches the frozen approved plan", False,
              f"no approval record at {approval.name}; the protocol freezes "
              "APPROVED_PLAN_HASH at Step 7.3, and without that record this "
              "hash has nothing authoritative to match")
    else:
        try:
            frozen = json.loads(approval.read_text(encoding="utf-8")).get("approved_plan_hash")
        except json.JSONDecodeError:
            frozen = None
        if not frozen:
            r.add(13, "approved-plan hash matches the frozen approved plan", False,
                  "approval record carries no approved_plan_hash")
        else:
            ok = str(ap).lower() == str(frozen).lower()
            r.add(13, "approved-plan hash matches the frozen approved plan", ok,
                  "" if ok else f"target   {ap}\n          approval {frozen}")

    # 14-15. diff and test results
    ok14, d14 = _hash_of_declared_file(target, "diff_hash", "diff_path", repo_root)
    r.add(14, "diff hash matches the reviewed diff", ok14, d14)
    ok15, d15 = _hash_of_declared_file(target, "test_result_hash", "test_result_path",
                                       repo_root)
    r.add(15, "test-result hash matches the supplied test results", ok15, d15)

    return r


def _impl_check_names():
    return ((11, "candidate commit present and exists"),
            (12, "candidate tree hash matches the candidate tree"),
            (13, "approved-plan hash matches the frozen approved plan"),
            (14, "diff hash matches the reviewed diff"),
            (15, "test-result hash matches the supplied test results"))


def _check_10(r: Result, cycle_dir: Path, recorded: str) -> None:
    ci = (cycle_dir / "codex-input.md").read_text(encoding="utf-8", errors="replace")
    bound = HEX64.match(recorded) is not None and recorded in ci
    r.add(10, "codex-input.md contains target SHA-256 verbatim", bound,
          "" if bound else
          "the input does not carry the frozen target hash, so nothing ties the "
          "reviewed artifact to what the reviewer was shown")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cycle_dir = Path(argv[1]).resolve()
    if not cycle_dir.is_dir():
        print(f"not a directory: {cycle_dir}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    result = validate(cycle_dir, repo_root)
    print(result.report(cycle_dir))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/run_review.py`

`sha256 5eb8a1a26e21a8876a6778d8e44d73d7a4d890da3b42fa65de6a1e08d3ece7be`

```
#!/usr/bin/env python3
"""Review cycle runner.

Composes review input, freezes the target, captures raw reviewer output, and
refuses to open a cycle whose preconditions do not hold.

    python scripts/run_review.py init   --run A1E-001 \
        --protocol specs/implementation-review-protocol-v1.1.md \
        --spec specs/gap/A1E_gap_object_schema_v1-4.md
    python scripts/run_review.py freeze --run A1E-001 --type plan \
        --prompt specs/prompts/plan-review.md --file runs/A1E-001/plan/01-PLAN.md
    python scripts/run_review.py record --cycle runs/A1E-001/plan-review/cycle-01 \
        --output raw.txt --invocation manual

Exit 0 = the step completed, 1 = refused, 2 = could not run.

MC-1 boundary, CONVENTION_ONLY on this environment
--------------------------------------------------
codex-input.md is composed here and never by the implementing agent. That
separation is a convention this script follows. It is not something the script
can enforce: the implementing agent holds write access to these paths. No claim
of technical protection may be made while MC1_ENFORCEMENT is CONVENTION_ONLY.

Write-once evidence
-------------------
target.json, target.sha256, codex-input.md and codex-output-raw.md are never
overwritten. A cycle that went wrong is repaired by opening a new cycle, not by
editing the old one. `freeze` refuses on an existing cycle directory; `record`
refuses when raw output is already present.

What this runner does not establish
-----------------------------------
It does not invoke the reviewer. It cannot show that codex-output-raw.md came
from the invocation codex-input.md describes; that binding rests on the operator
and is recorded, not proven, in invocation.json. This is the same limit stated
in specs/evidence-schema-v1.0.md, restated here so it is visible at the point of
use.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"

MAX_CYCLES = 4
REVIEW_TYPES = ("plan", "implementation")
INVOCATIONS = ("manual", "automated")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


class Refused(Exception):
    """A precondition did not hold. Exit 1, change nothing."""


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_lf(p: Path, text: str) -> None:
    """Write evidence with LF endings on every platform.

    Path.write_text translates \\n to the platform line ending, so the same
    target.json frozen on Windows and on Linux would hash differently while
    being self-consistent on each. MC-2 would pass on both and the divergence
    would only surface when someone tried to reproduce a freeze elsewhere and
    got a different TARGET_SHA256. Evidence hashes have to be a property of the
    content, not of the machine that wrote it.
    """
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def rel(p: Path) -> str:
    """Repo-relative with forward slashes, so evidence is platform-neutral."""
    return p.resolve().relative_to(REPO).as_posix()


def hashed_ref(p: Path) -> dict:
    return {"path": rel(p), "sha256": sha256_file(p)}


def spec_digest(entries: list[dict]) -> str:
    """One digest over the spec set.

    SHA-256 of "path:sha256\\n" lines, sorted by path. Defined here because it
    has to be reproducible by anyone auditing a run, not just by this script.
    """
    body = "".join(f"{e['path']}:{e['sha256']}\n" for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def git_head() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except FileNotFoundError:
        return None


def require_file(p: Path, what: str) -> Path:
    if not p.is_file():
        raise Refused(f"{what} not found: {p}")
    if p.stat().st_size == 0:
        raise Refused(f"{what} is empty: {p}")
    return p


# ---------------------------------------------------------------- init

def cmd_init(args: argparse.Namespace) -> int:
    run_dir = REPO / "runs" / args.run
    run_json = run_dir / "run.json"
    if run_json.exists():
        raise Refused(f"run.json already exists: {run_json}\n"
                      "A run's pins are fixed at creation. Use a new run id.")

    # The bootstrap gate, ruled mandatory 8 September 2026. This runner and the
    # MC-2 checker cannot pass through the process they enable, so a one-time
    # independent review stands in for it, and no real run starts without one.
    #
    # Enforced here rather than at freeze because init is where a run becomes a
    # thing that exists. A run created now and frozen later would otherwise carry
    # pins made before anyone had looked at the code doing the pinning.
    if not args.bootstrap_exempt:
        # Loaded by path rather than by name. `from bootstrap_gate import ...`
        # works only when the script's own directory happens to be on sys.path,
        # which it is when run directly and is not in several other cases. A gate
        # that silently becomes an ImportError is a gate that stops gating.
        import importlib.util
        gate_py = Path(__file__).resolve().parent / "bootstrap_gate.py"
        if not gate_py.is_file():
            raise Refused(
                f"the bootstrap gate is missing: {gate_py}\n"
                "  Refusing rather than proceeding. A missing gate is not an "
                "absent requirement.")
        spec_ = importlib.util.spec_from_file_location("_bootstrap_gate", gate_py)
        mod = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(mod)
        ok, reasons = mod.evaluate(REPO)
        if not ok:
            raise Refused(
                "BOOTSTRAP_REVIEW not satisfied, so no real protocol run may be "
                "created:\n  " + "\n  ".join(reasons) +
                "\n\n  This is the one declared exception to the protocol and it "
                "is not optional.\n  To produce development evidence instead, "
                "pass --bootstrap-exempt, which\n  labels the run "
                "BOOTSTRAP / DEVELOPMENT EVIDENCE — NOT_A_PROTOCOL_CYCLE.")

    protocol = require_file(Path(args.protocol).resolve(), "protocol file")
    specs = [hashed_ref(require_file(Path(s).resolve(), "spec file")) for s in args.spec]
    if not specs:
        raise Refused("a run needs at least one spec file; --spec is repeatable")

    head = git_head()
    if head is None:
        raise Refused("cannot resolve git HEAD; the run must pin a commit")

    run = {
        "run_id": args.run,
        "created_at": now(),
        "protocol_commit": head,
        "protocol": hashed_ref(protocol),
        "protocol_sha256": sha256_file(protocol),
        "spec_files": specs,
        "spec_sha256": spec_digest(specs),
        "max_cycles": MAX_CYCLES,
        # Recorded on the run, not just checked at init, so a reader of the
        # evidence can tell which kind of run this was without consulting
        # anything else.
        "bootstrap_review": ("EXEMPT — BOOTSTRAP / DEVELOPMENT EVIDENCE, "
                             "NOT_A_PROTOCOL_CYCLE"
                             if args.bootstrap_exempt else "APPROVED"),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    write_lf(run_json, json.dumps(run, indent=2) + "\n")

    print(f"initialised {rel(run_json)}")
    print(f"  protocol_commit  {head}")
    print(f"  protocol_sha256  {run['protocol_sha256']}")
    print(f"  spec_sha256      {run['spec_sha256']}  over {len(specs)} spec file(s)")
    return 0


# ---------------------------------------------------------------- freeze

def load_run(run_id: str) -> dict:
    run_json = REPO / "runs" / run_id / "run.json"
    if not run_json.is_file():
        raise Refused(f"no run.json for {run_id}; run `init` first")
    try:
        return json.loads(run_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"run.json is not valid JSON: {e}")


def check_pins_still_hold(run: dict) -> None:
    """The protocol and specs must not have moved since init.

    A run whose spec changed underneath it is not four cycles against one spec;
    it is four cycles against whatever happened to be on disk each time. This is
    the check that makes the run.json pin mean something.
    """
    drift: list[str] = []

    proto = REPO / run["protocol"]["path"]
    if not proto.is_file():
        drift.append(f"protocol file is gone: {run['protocol']['path']}")
    elif sha256_file(proto) != run["protocol"]["sha256"]:
        drift.append(f"protocol changed since init: {run['protocol']['path']}\n"
                     f"    pinned {run['protocol']['sha256']}\n"
                     f"    actual {sha256_file(proto)}")

    for e in run["spec_files"]:
        p = REPO / e["path"]
        if not p.is_file():
            drift.append(f"spec file is gone: {e['path']}")
        elif sha256_file(p) != e["sha256"]:
            drift.append(f"spec changed since init: {e['path']}\n"
                         f"    pinned {e['sha256']}\n"
                         f"    actual {sha256_file(p)}")

    if drift:
        raise Refused("run pins no longer hold:\n  " + "\n  ".join(drift) +
                      "\n\nEither restore the pinned bytes or start a new run. "
                      "Continuing would produce cycles that cite a spec version "
                      "nobody reviewed.")


def next_cycle(review_dir: Path) -> int:
    if not review_dir.is_dir():
        return 1
    used = []
    for d in review_dir.iterdir():
        m = re.fullmatch(r"cycle-(\d{2})", d.name) if d.is_dir() else None
        if m:
            used.append(int(m.group(1)))
    return max(used) + 1 if used else 1


def check_previous_cycle_closed(review_dir: Path, n: int) -> None:
    if n <= 1:
        return
    prev = review_dir / f"cycle-{n - 1:02d}"
    raw = prev / "codex-output-raw.md"
    if not raw.is_file() or raw.stat().st_size == 0:
        raise Refused(f"cycle {n - 1:02d} has no recorded output at {rel(raw) if raw.exists() else raw}\n"
                      "Record the previous cycle's raw output before opening the next. "
                      "Two open cycles means the budget count is guesswork.")


def compose_input(prompt: str, target_hash: str, run: dict, rtype: str,
                  cycle_n: int, artifacts: list[tuple[dict, str]],
                  protocol_text: str = "") -> str:
    """Everything the reviewer needs, in the file the target hash binds.

    The protocol text is included, not merely hashed. Every review is *against*
    the protocol, and an earlier version of this function named PROTOCOL_SHA256
    in the header and stopped there. A reviewer cannot read a hash, so it would
    have been asked to judge conformance to a document it had never seen and
    would have answered from memory or invention.

    That is the pilot's failure restated: freezing an artifact proves it did not
    change, not that the reviewer read it. Here it was worse, because the
    reviewer could not have read it at all.

    It belongs in this file rather than being pasted alongside, because
    codex-input.md is what MC-2 check 10 binds to the frozen target. Anything
    supplied next to it is outside the evidence and cannot be shown to have been
    what the reviewer saw.
    """
    lines = [
        f"# Review input — {run['run_id']} / {rtype} review / cycle {cycle_n:02d}",
        "",
        "```text",
        f"TARGET_SHA256   {target_hash}",
        f"PROTOCOL_SHA256 {run['protocol_sha256']}",
        f"SPEC_SHA256     {run['spec_sha256']}",
        "```",
        "",
        "The target hash above is the binding between the frozen artifact and this",
        "input. Quote it in your response.",
        "",
        "---",
        "",
        prompt.rstrip(),
        "",
        "---",
        "",
    ]
    if protocol_text:
        lines += [
            "# The governing protocol",
            "",
            f"`{run['protocol']['path']}`, sha256 `{run['protocol_sha256']}`.",
            "",
            "This is the document the artifacts below are reviewed against. Where",
            "it and the review prompt disagree, this governs.",
            "",
            "```",
            protocol_text.rstrip("\n"),
            "```",
            "",
            "---",
            "",
        ]
    lines += [
        "# Artifacts under review",
        "",
    ]
    for ref, body in artifacts:
        lines += [f"## `{ref['path']}`", "", f"`sha256 {ref['sha256']}`", "",
                  "```", body.rstrip("\n"), "```", ""]
    return "\n".join(lines) + "\n"


def cmd_freeze(args: argparse.Namespace) -> int:
    if args.type not in REVIEW_TYPES:
        raise Refused(f"--type must be one of {REVIEW_TYPES}, got {args.type!r}")

    run = load_run(args.run)
    check_pins_still_hold(run)

    prompt_path = require_file(Path(args.prompt).resolve(), "prompt file")
    prompt = prompt_path.read_text(encoding="utf-8")

    review_dir = REPO / "runs" / args.run / f"{args.type}-review"
    n = next_cycle(review_dir)
    if n > MAX_CYCLES:
        raise Refused(f"cycle {n} would exceed the {MAX_CYCLES}-cycle budget for "
                      f"{args.run} {args.type} review.\n"
                      "MAX_4_REACHED is an exit, not an obstacle to route around. "
                      "Escalate to human review.")
    check_previous_cycle_closed(review_dir, n)

    cycle = review_dir / f"cycle-{n:02d}"
    if cycle.exists():
        raise Refused(f"cycle directory already exists: {rel(cycle)}\n"
                      "Frozen evidence is write-once.")

    target = {
        "review_type": args.type,
        "run_id": run["run_id"],
        "cycle": n,
        "protocol_commit": run["protocol_commit"],
        "protocol_sha256": run["protocol_sha256"],
        "spec_sha256": run["spec_sha256"],
        "frozen_at": now(),
    }

    artifacts: list[tuple[dict, str]] = []

    if args.type == "plan":
        if not args.file:
            raise Refused("plan review needs at least one --file")
        refs = [hashed_ref(require_file(Path(f).resolve(), "plan file")) for f in args.file]
        target["plan_files"] = refs
        artifacts = [(r, (REPO / r["path"]).read_text(encoding="utf-8", errors="replace"))
                     for r in refs]
    else:
        # §10.1: "These fields are mandatory, not conditional."
        if not args.candidate_commit:
            raise Refused("implementation review requires --candidate-commit")
        r = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", f"{args.candidate_commit}^{{tree}}"],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise Refused(f"--candidate-commit does not resolve: {args.candidate_commit}")
        target["candidate_commit"] = args.candidate_commit
        # Derived, not supplied: a tree hash typed by hand is a tree hash that
        # can be typed to match whatever was recorded.
        target["candidate_tree_hash"] = r.stdout.strip()

        if not args.approved_plan_hash:
            raise Refused("implementation review requires --approved-plan-hash")
        if not HEX64.match(args.approved_plan_hash):
            raise Refused("--approved-plan-hash must be a lowercase 64-char hex digest")
        target["approved_plan_hash"] = args.approved_plan_hash

        for path_key, hash_key, arg, label in (
                ("diff_path", "diff_hash", args.diff, "diff"),
                ("test_result_path", "test_result_hash", args.test_results,
                 "test results")):
            if not arg:
                raise Refused(f"implementation review requires --{label.replace(' ', '-')}")
            ref = hashed_ref(require_file(Path(arg).resolve(), label))
            target[path_key] = ref["path"]
            target[hash_key] = ref["sha256"]
            artifacts.append((ref, (REPO / ref["path"]).read_text(encoding="utf-8",
                                                                 errors="replace")))

    cycle.mkdir(parents=True)
    tj = cycle / "target.json"
    write_lf(tj, json.dumps(target, indent=2) + "\n")
    digest = sha256_file(tj)
    write_lf(cycle / "target.sha256", digest + "\n")

    ci = cycle / "codex-input.md"
    # Read from the pinned path. check_pins_still_hold has already verified this
    # file hashes to run.json's protocol_sha256, so the text embedded below is
    # the text the header names rather than whatever is on disk under that name.
    protocol_text = (REPO / run["protocol"]["path"]).read_text(encoding="utf-8")
    write_lf(ci, compose_input(prompt, digest, run, args.type, n, artifacts,
                               protocol_text))

    # Self-checks, not assumptions, on what was just written.
    if digest not in ci.read_text(encoding="utf-8"):
        raise Refused("composed input does not contain the target hash; refusing to "
                      "leave a cycle that MC-2 would reject")
    if b"\r" in tj.read_bytes():
        raise Refused("target.json contains CR bytes; its hash would not reproduce "
                      "on another platform")

    print(f"froze {rel(cycle)}")
    print(f"  target.sha256  {digest}")
    print(f"  artifacts      {len(artifacts)}")
    print()
    print("Next: run the review on codex-input.md, save the reply verbatim, then")
    print(f"  python scripts/run_review.py record --cycle {rel(cycle)} \\")
    print("      --output <reply file> --invocation manual")
    return 0


# ---------------------------------------------------------------- record

def cmd_record(args: argparse.Namespace) -> int:
    if args.invocation not in INVOCATIONS:
        raise Refused(f"--invocation must be one of {INVOCATIONS}")

    cycle = Path(args.cycle).resolve()
    if not (cycle / "target.json").is_file():
        raise Refused(f"not a frozen cycle directory: {cycle}")

    raw = cycle / "codex-output-raw.md"
    if raw.exists():
        raise Refused(f"raw output already recorded: {rel(raw)}\n"
                      "Raw reviewer output is write-once. If it was wrong, the cycle "
                      "is wrong; open a new one.")

    src = require_file(Path(args.output).resolve(), "reviewer output")
    # Bytes, not text. Whatever the reviewer returned is what gets stored.
    raw.write_bytes(src.read_bytes())

    write_lf(cycle / "invocation.json", json.dumps({
        "invocation": args.invocation,
        "recorded_at": now(),
        "source": str(src),
        "note": args.note or "",
        "unproven": "This file records how the review was invoked. It does not "
                    "establish that codex-output-raw.md came from codex-input.md.",
    }, indent=2) + "\n")

    print(f"recorded {rel(raw)}  ({raw.stat().st_size} bytes, invocation={args.invocation})")
    print()

    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle)],
                       capture_output=True, text=True)
    print(r.stdout.rstrip())
    if r.stderr.strip():
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode != 0:
        print()
        print("Cycle recorded but INVALID. It does not count toward the budget.")
    return 0 if r.returncode == 0 else 1


# ---------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_review.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create runs/<id>/run.json and pin protocol + specs")
    i.add_argument("--run", required=True)
    i.add_argument("--protocol", required=True)
    i.add_argument("--spec", action="append", default=[], required=True)
    i.add_argument("--bootstrap-exempt", action="store_true",
                   help="produce development evidence rather than a protocol "
                        "cycle; the run is labelled NOT_A_PROTOCOL_CYCLE and the "
                        "bootstrap gate is skipped. Not a way to start a real run "
                        "early.")
    i.set_defaults(fn=cmd_init)

    f = sub.add_parser("freeze", help="open the next cycle and compose reviewer input")
    f.add_argument("--run", required=True)
    f.add_argument("--type", required=True, choices=REVIEW_TYPES)
    f.add_argument("--prompt", required=True)
    f.add_argument("--file", action="append", default=[], help="plan review: repeatable")
    # §10.1 fields. candidate_tree_hash is derived from the commit, not passed.
    f.add_argument("--candidate-commit", dest="candidate_commit")
    f.add_argument("--approved-plan-hash", dest="approved_plan_hash")
    f.add_argument("--diff")
    f.add_argument("--test-results", dest="test_results")
    f.set_defaults(fn=cmd_freeze)

    r = sub.add_parser("record", help="store raw reviewer output and run the MC-2 gate")
    r.add_argument("--cycle", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--invocation", required=True, choices=INVOCATIONS)
    r.add_argument("--note", default="")
    r.set_defaults(fn=cmd_record)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    try:
        return args.fn(args)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/ledger.py`

`sha256 b7eca74ef8b19436907af82c5bb450913b3ba9613200d7b4dcee7260f678ad30`

```
#!/usr/bin/env python3
"""Finding and state ledger.

Tracks every Codex finding through OPEN / RESOLVED / DISPUTED across the cycles
of one review loop, with a full audit trail and no illegal transitions.

    python scripts/ledger.py raise   --review <dir> --cycle 1 --id C01-F01 \
        --class "UNTESTED RULE" --requirement R-B7
    python scripts/ledger.py respond --review <dir> --cycle 1 --id C01-F01 \
        --disposition ACCEPT --note "..."
    python scripts/ledger.py resolve --review <dir> --cycle 2 --id C01-F01 \
        --evidence "repaired in 02-PLAN.md §4"
    python scripts/ledger.py show    --review <dir> [--cycle N]

Exit 0 = done, 1 = refused, 2 = could not run.

The three states are the protocol's, §6: OPEN, RESOLVED, DISPUTED. There is no
fourth.

Why ACCEPT does not resolve
---------------------------
§5: on ACCEPT the finding's state becomes RESOLVED "once the repair is
demonstrated in the next review target". So accepting records a disposition and
leaves the state OPEN. Only a later cycle can move it to RESOLVED, and this
ledger refuses to do it in the same cycle as the ACCEPT.

That is not pedantry. If ACCEPT alone resolved a finding, the implementing agent
would close its own findings by asserting it intended to fix them, which is the
authority inversion MC-1 exists to prevent.

Who declares a repair demonstrated
----------------------------------
The protocol does not say mechanically, and this ledger does not invent an
answer. `resolve` requires an explicit evidence string and refuses without a
prior ACCEPT, so the assertion is recorded and attributable rather than implied.
See DECISIONS below.

DISPUTED is terminal here
-------------------------
§5 says a dispute "requires human adjudication" and §7.1 puts that at the human
gate. Nothing in the automated loop may move a finding out of DISPUTED, so this
ledger refuses. Adjudication belongs to the approval record, not here.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

FINDING_ID = re.compile(r"\AC(\d{2})-F(\d{2,3})\Z")

# §4, and the vocabulary "remains unchanged across cycles so that finding sets
# remain comparable". Anything outside it is refused rather than recorded.
CLASSES = (
    "MISSING REQUIREMENT",
    "WRONG OWNERSHIP",
    "NONDETERMINISTIC WHERE D POSSIBLE",
    "SEMANTIC STEP TOO BROAD",
    "UNTESTED RULE",
    "CONTRADICTORY IMPLEMENTATION MAPPING",
)

# Kept out of CLASSES deliberately, and refused by name rather than falling
# through the generic "not one of the six" message, because the reason it is
# refused is specific and worth printing.
#
# Alex Zamurko, 8 September 2026: OUT OF VOCABULARY is kept in the review prompts
# "only as a non-finding, human-visible diagnostic ... no Finding ID, must not be
# written to findings.json, must not enter OPEN / RESOLVED / DISPUTED, and must
# not affect loop-state calculation."
#
# The prompts say so; this refuses it, which is the difference between a rule and
# a request. An OUT OF VOCABULARY item admitted here would be a seventh class in
# everything but name, and would silently gain the power to block convergence.
NON_FINDING = "OUT OF VOCABULARY"

OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"
STATES = (OPEN, RESOLVED, DISPUTED)


class Refused(Exception):
    """A transition the protocol does not permit. Exit 1, change nothing."""


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_lf(p: Path, text: str) -> None:
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def ledger_path(review: Path) -> Path:
    return review / "findings.json"


def load(review: Path) -> dict:
    p = ledger_path(review)
    if not p.is_file():
        return {"review": review.name, "findings": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"findings.json is not valid JSON: {e}")


def save(review: Path, data: dict) -> None:
    review.mkdir(parents=True, exist_ok=True)
    write_lf(ledger_path(review), json.dumps(data, indent=2, sort_keys=True) + "\n")


def check_id(fid: str, cycle: int) -> None:
    m = FINDING_ID.match(fid)
    if not m:
        raise Refused(f"finding id must look like C02-F03, got {fid!r}")
    if int(m.group(1)) != cycle:
        raise Refused(f"{fid} declares cycle {int(m.group(1))} but was raised in "
                      f"cycle {cycle}. The identifier is persistent and carries the "
                      "cycle it was raised in; a mismatch makes the history unreadable.")


def get(data: dict, fid: str) -> dict:
    f = data["findings"].get(fid)
    if f is None:
        raise Refused(f"no such finding: {fid}. Raise it before responding to it.")
    return f


def last_event(f: dict, event: str) -> dict | None:
    for e in reversed(f["history"]):
        if e["event"] == event:
            return e
    return None


# ---------------------------------------------------------------- commands

def cmd_raise(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    check_id(a.id, a.cycle)
    if a.id in data["findings"]:
        raise Refused(f"{a.id} already exists. Finding identifiers are persistent; "
                      "a re-raised issue in a later cycle is a new finding that may "
                      "reference the old one, not a reuse of its id.")
    if a.klass.strip().upper() == NON_FINDING:
        raise Refused(
            f"{NON_FINDING} is not a finding and cannot enter the ledger.\n"
            "  It is a human-visible diagnostic only: no Finding ID, never in\n"
            "  findings.json, never OPEN / RESOLVED / DISPUTED, no effect on\n"
            "  loop state. Ruled by Alex Zamurko, 8 September 2026.\n"
            "  It reaches the human at the review gate, in the raw Codex output.\n"
            "  If the issue must block convergence it has to fit one of the six;\n"
            "  if it genuinely cannot, that mismatch is the thing being reported.")
    if a.klass not in CLASSES:
        raise Refused(f"class must be one of the six in §4, got {a.klass!r}\n  "
                      + "\n  ".join(CLASSES))

    data["findings"][a.id] = {
        "cycle_raised": a.cycle,
        "class": a.klass,
        "requirement_id": a.requirement or "",
        "state": OPEN,
        "history": [{"cycle": a.cycle, "event": "RAISED", "state": OPEN,
                     "at": now(), "note": a.note or ""}],
    }
    save(review, data)
    print(f"{a.id}  RAISED  cycle {a.cycle:02d}  {a.klass}  -> {OPEN}")
    return 0


def cmd_respond(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)

    if f["state"] == RESOLVED:
        raise Refused(f"{a.id} is RESOLVED. A resolved finding is not reopened by "
                      "the automated loop.")
    if f["state"] == DISPUTED:
        raise Refused(f"{a.id} is DISPUTED and requires human adjudication (§5, §7.1). "
                      "The automated loop does not move findings out of DISPUTED.")

    for e in f["history"]:
        if e["cycle"] == a.cycle and e["event"] in ("ACCEPT", "REJECT_WITH_REASON"):
            raise Refused(f"{a.id} already has a disposition in cycle {a.cycle:02d}: "
                          f"{e['event']}. §5 permits exactly one per finding.")

    if a.disposition == "ACCEPT":
        # State deliberately unchanged. See the module docstring.
        f["history"].append({"cycle": a.cycle, "event": "ACCEPT", "state": OPEN,
                             "at": now(), "note": a.note or ""})
        print(f"{a.id}  ACCEPT  cycle {a.cycle:02d}  -> still {OPEN}")
        print("       §5: RESOLVED only once the repair is demonstrated in the next")
        print("       review target. Use `resolve` from a later cycle.")
    else:
        # §5's REJECT_WITH_REASON block names Reason and Spec evidence as two
        # fields, and they answer different questions: why the reviewer is wrong,
        # and what in the specification says so. One free-text note satisfied the
        # first and let the second go unwritten, which is how a rejection ends up
        # resting on the implementing agent's judgement rather than on the spec.
        # Alex Zamurko, 8 September 2026: "DISPUTE ... requires reason/spec
        # evidence".
        if not (a.note or "").strip():
            raise Refused("REJECT_WITH_REASON requires --note, the Reason of §5. "
                          "A rejection without one is a silent dismissal.")
        if not (a.spec_evidence or "").strip():
            raise Refused(
                "REJECT_WITH_REASON requires --spec-evidence, the Spec evidence "
                "field of §5.\n"
                "  Reason says why you disagree. Spec evidence says what in the "
                "specification\n"
                "  supports you, and it is the half a human adjudicating the "
                "dispute needs.\n"
                "  A rejection resting only on the implementing agent's reading "
                "is the\n  authority inversion MC-1 exists to prevent.")
        f["state"] = DISPUTED
        f["history"].append({"cycle": a.cycle, "event": "REJECT_WITH_REASON",
                             "state": DISPUTED, "at": now(), "note": a.note,
                             "spec_evidence": a.spec_evidence})
        print(f"{a.id}  REJECT_WITH_REASON  cycle {a.cycle:02d}  -> {DISPUTED}")
        print("       Requires human adjudication at the plan gate.")

    save(review, data)
    return 0


def cmd_resolve(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)

    if f["state"] == RESOLVED:
        raise Refused(f"{a.id} is already RESOLVED.")
    if f["state"] == DISPUTED:
        raise Refused(f"{a.id} is DISPUTED. A dispute is resolved by human "
                      "adjudication at the gate, not by demonstrating a repair.")

    acc = last_event(f, "ACCEPT")
    if acc is None:
        raise Refused(f"{a.id} has no ACCEPT. §5 gives RESOLVED only to a finding "
                      "that was accepted and then repaired; a finding cannot become "
                      "resolved without first having been accepted.")
    if a.cycle <= acc["cycle"]:
        raise Refused(f"{a.id} was accepted in cycle {acc['cycle']:02d} and cannot be "
                      f"resolved in cycle {a.cycle:02d}. §5 requires the repair to be "
                      "demonstrated in the NEXT review target, so resolution belongs "
                      "to a later cycle than the acceptance.")
    if not (a.evidence or "").strip():
        raise Refused("--evidence is required. The protocol resolves a finding when "
                      "the repair is demonstrated; recording what demonstrates it is "
                      "the difference between a demonstration and an assertion.")

    f["state"] = RESOLVED
    f["history"].append({"cycle": a.cycle, "event": "DEMONSTRATED", "state": RESOLVED,
                         "at": now(), "note": a.evidence})
    save(review, data)
    print(f"{a.id}  DEMONSTRATED  cycle {a.cycle:02d}  -> {RESOLVED}")
    return 0


def state_after(f: dict, cycle: int) -> str:
    """The finding's state as at the end of the given cycle.

    §6 defines OPEN_n and the _NEW_n sets over cycle boundaries, so the loop
    controller needs history, not just the current state.
    """
    state = None
    for e in f["history"]:
        if e["cycle"] <= cycle:
            state = e["state"]
    return state or ""


def snapshot(data: dict, cycle: int) -> dict[str, set[str]]:
    out = {OPEN: set(), RESOLVED: set(), DISPUTED: set()}
    for fid, f in data["findings"].items():
        s = state_after(f, cycle)
        if s in out:
            out[s].add(fid)
    return out


def cmd_show(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    if not data["findings"]:
        print(f"no findings recorded in {review}")
        return 0

    if a.cycle is not None:
        snap = snapshot(data, a.cycle)
        print(f"state after cycle {a.cycle:02d}")
        for s in STATES:
            ids = sorted(snap[s])
            print(f"  {s:<9} {len(ids):>2}  {', '.join(ids) if ids else '-'}")
        return 0

    print(f"findings ledger — {review}")
    for fid in sorted(data["findings"]):
        f = data["findings"][fid]
        print(f"\n  {fid}  [{f['state']}]  {f['class']}"
              + (f"  ({f['requirement_id']})" if f["requirement_id"] else ""))
        for e in f["history"]:
            note = f"  {e['note'][:60]}" if e.get("note") else ""
            print(f"      cycle {e['cycle']:02d}  {e['event']:<18} -> {e['state']}{note}")
    print()
    snap = snapshot(data, 10**6)
    for s in STATES:
        print(f"  {s:<9} {len(snap[s])}")
    return 0


# ---------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledger.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--review", required=True,
                        help="the review directory, e.g. runs/A1E-001/plan-review")

    r = sub.add_parser("raise", help="record a Codex finding")
    common(r)
    r.add_argument("--cycle", type=int, required=True)
    r.add_argument("--id", required=True)
    # No argparse `choices` here. argparse would reject an out-of-vocabulary
    # class with a generic usage error and exit 2, before the refusals above can
    # explain why. The reason is the useful part, so validation happens in
    # cmd_raise and every refusal exits 1 with a stated cause.
    r.add_argument("--class", dest="klass", required=True,
                   metavar="CLASS")
    r.add_argument("--requirement")
    r.add_argument("--note", default="")
    r.set_defaults(fn=cmd_raise)

    d = sub.add_parser("respond", help="ACCEPT or REJECT_WITH_REASON")
    common(d)
    d.add_argument("--cycle", type=int, required=True)
    d.add_argument("--id", required=True)
    d.add_argument("--disposition", required=True,
                   choices=("ACCEPT", "REJECT_WITH_REASON"))
    d.add_argument("--note", default="",
                   help="§5 Reason. Required for REJECT_WITH_REASON.")
    d.add_argument("--spec-evidence", dest="spec_evidence", default="",
                   help="§5 Spec evidence. Required for REJECT_WITH_REASON: what "
                        "in the specification supports the rejection.")
    d.set_defaults(fn=cmd_respond)

    v = sub.add_parser("resolve", help="record that an accepted repair was demonstrated")
    common(v)
    v.add_argument("--cycle", type=int, required=True)
    v.add_argument("--id", required=True)
    v.add_argument("--evidence", default="")
    v.set_defaults(fn=cmd_resolve)

    s = sub.add_parser("show", help="print the ledger, or a per-cycle snapshot")
    common(s)
    s.add_argument("--cycle", type=int)
    s.set_defaults(fn=cmd_show)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    try:
        return args.fn(args)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/loop_state.py`

`sha256 3e9ba6e2ff769e24473b3ffbebb133d9b1758ae719756f06279f40d59ffa09be`

```
#!/usr/bin/env python3
"""Loop-state controller.

Computes CONVERGED / HUMAN_ADJUDICATION_REQUIRED / STALLED / MAX_4_REACHED /
CONTINUE for one review loop, per §6 and §13 of the protocol, and shows the
working.

    python scripts/loop_state.py --review runs/A1E-001/plan-review

Exit 0 = a state was determined, 2 = could not run.
The state itself is on stdout as LOOP_STATUS; it is not an exit code, because
CONTINUE is not a failure and STALLED is not an error.

Validity is computed, not trusted
---------------------------------
§2 : "Only cycles that pass the MC-2 conformance gate count toward this maximum."
§3 : an invalid cycle "cannot support an authoritative Codex finding" and
     "cannot consume one of the four valid review cycles".

So this runs scripts/validate_cycle.py on every cycle directory rather than
reading a recorded verdict. A loop controller that accepted an asserted PASS
would let an invalid cycle consume the budget, which is the exact defect the
"MAX 4 counts valid cycles" note exists to prevent.

Two consequences, both deliberate and both worth disagreeing with if you see it
differently:

1. §6's n indexes VALID cycles, not directory numbers. If cycle-02 fails the
   gate, then cycle-03 is n=2. Otherwise |OPEN_n| would be compared against a
   cycle whose evidence is not authoritative.

2. Events recorded in an invalid cycle are ignored entirely, including
   resolutions. A finding accepted in valid cycle 1 and marked demonstrated in
   invalid cycle 2 stays OPEN, because the cycle that would demonstrate it
   cannot support an authoritative anything. This is the conservative reading
   and it can only ever delay an exit, never manufacture one.

What this does not do
---------------------
It does not decide whether a repair was demonstrated; the ledger records that
assertion and this reads it. It does not adjudicate disputes. And CONVERGED
here means the finding sets are empty, not that the plan is good.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"
MAX_VALID_CYCLES = 4

OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"


def cycle_dirs(review: Path) -> list[tuple[int, Path]]:
    out = []
    for d in sorted(review.iterdir()) if review.is_dir() else []:
        m = re.fullmatch(r"cycle-(\d{2})", d.name)
        if m and d.is_dir():
            out.append((int(m.group(1)), d))
    return sorted(out)


def gate(cycle_dir: Path) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle_dir)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        return False, "checker could not run"
    reason = ""
    if r.returncode != 0:
        fails = [l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l]
        reason = fails[0] if fails else "MC-2 FAIL"
    return r.returncode == 0, reason


def load_ledger(review: Path) -> dict:
    p = review / "findings.json"
    if not p.is_file():
        return {"findings": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def state_after(f: dict, valid_upto: set[int]) -> str | None:
    """State as at the end of the valid cycles in `valid_upto`.

    Events in cycles outside the set are skipped, per consequence 2 above.
    """
    state = None
    for e in f["history"]:
        if e["cycle"] in valid_upto:
            state = e["state"]
    return state


def sets_at(ledger: dict, valid_upto: set[int]) -> dict[str, set[str]]:
    out = {OPEN: set(), RESOLVED: set(), DISPUTED: set()}
    for fid, f in ledger["findings"].items():
        s = state_after(f, valid_upto)
        if s in out:
            out[s].add(fid)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", required=True)
    ap.add_argument("--quiet", action="store_true", help="print LOOP_STATUS only")
    a = ap.parse_args(argv[1:])

    review = Path(a.review).resolve()
    if not review.is_dir():
        print(f"not a directory: {review}", file=sys.stderr)
        return 2

    dirs = cycle_dirs(review)
    if not dirs:
        print(f"no cycle directories in {review}", file=sys.stderr)
        return 2

    lines: list[str] = [f"loop state — {review}", "", "cycles"]
    valid: list[int] = []
    for num, d in dirs:
        ok, why = gate(d)
        if ok:
            valid.append(num)
            lines.append(f"  cycle-{num:02d}  VALID    -> n={len(valid)}")
        else:
            lines.append(f"  cycle-{num:02d}  INVALID  {why}")
            lines.append("            does not count toward the budget and its "
                         "events are ignored")
    lines += ["", f"VALID_CYCLE_COUNT: {len(valid)}"]

    if not valid:
        lines += ["", "LOOP_STATUS: CONTINUE",
                  "No valid cycle has been completed, so §6 has nothing to measure. "
                  "Repair the evidence and rerun."]
        print("\n".join(lines) if not a.quiet else "LOOP_STATUS: CONTINUE")
        return 0

    ledger = load_ledger(review)
    n = len(valid)
    upto_n = set(valid)
    upto_prev = set(valid[:-1])

    cur = sets_at(ledger, upto_n)
    prev = sets_at(ledger, upto_prev) if n > 1 else None

    # §6: the _NEW_n sets are findings that were OPEN after n-1 and changed during n.
    resolved_new: set[str] = set()
    disputed_new: set[str] = set()
    if prev is not None:
        for fid in prev[OPEN]:
            s = state_after(ledger["findings"][fid], upto_n)
            if s == RESOLVED:
                resolved_new.add(fid)
            elif s == DISPUTED:
                disputed_new.add(fid)

    def fmt(ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "-"

    lines += ["", "§6 sets"]
    lines.append(f"  OPEN_{n}          {len(cur[OPEN]):>2}  {fmt(cur[OPEN])}")
    lines.append(f"  DISPUTED_{n}      {len(cur[DISPUTED]):>2}  {fmt(cur[DISPUTED])}")
    lines.append(f"  RESOLVED_{n}      {len(cur[RESOLVED]):>2}  {fmt(cur[RESOLVED])}")
    if prev is not None:
        lines.append(f"  OPEN_{n-1}          {len(prev[OPEN]):>2}  {fmt(prev[OPEN])}")
        lines.append(f"  RESOLVED_NEW_{n}  {len(resolved_new):>2}  {fmt(resolved_new)}")
        lines.append(f"  DISPUTED_NEW_{n}  {len(disputed_new):>2}  {fmt(disputed_new)}")

    # Exits are tested in the protocol's order, and the order is load-bearing.
    # HUMAN_ADJUDICATION_REQUIRED sits between CONVERGED and STALLED because a
    # loop with nothing open and a dispute outstanding is not stalled: it
    # finished everything automation can do. Test STALLED first and it swallows
    # the case a cycle later, which is what v1.0 did.
    lines += ["", "exits"]
    status = None
    detail = ""

    converged = not cur[OPEN] and not cur[DISPUTED]
    lines.append(f"  A CONVERGED                    OPEN_{n} = 0 and DISPUTED_{n} = 0"
                 f"        {'yes' if converged else 'no'}")
    if converged:
        status = "CONVERGED"
        detail = "Nothing open and nothing disputed. Proceed to human plan review."

    if status is None:
        adjudicate = not cur[OPEN] and cur[DISPUTED]
        lines.append(f"  B HUMAN_ADJUDICATION_REQUIRED  OPEN_{n} = 0 and "
                     f"DISPUTED_{n} != 0     {'yes' if adjudicate else 'no'}")
        if adjudicate:
            status = "HUMAN_ADJUDICATION_REQUIRED"
            detail = ("Everything actionable is resolved or disputed, and no further "
                      "automated repair is available. Stop now rather than spending a "
                      "cycle on a plan with nothing open to repair. Proceed to human "
                      "plan review.")

    if status is None:
        if prev is None:
            lines.append("  C STALLED                      not testable at n=1 "
                         "(§6 requires n > 1)")
        else:
            stalled = (len(cur[OPEN]) >= len(prev[OPEN])
                       and not resolved_new and not disputed_new)
            lines.append(
                f"  C STALLED                      |OPEN_{n}| >= |OPEN_{n-1}|"
                f" ({len(cur[OPEN])} >= {len(prev[OPEN])})"
                f" and no new resolved/disputed   {'yes' if stalled else 'no'}")
            if stalled:
                status = "STALLED"
                detail = ("The last valid cycle reduced nothing, resolved nothing and "
                          "disputed nothing. Stop now rather than spending the "
                          "remaining budget. Proceed to human plan review.")

    if status is None:
        maxed = len(valid) >= MAX_VALID_CYCLES
        lines.append(f"  D MAX_4_REACHED                VALID_CYCLE_COUNT = {len(valid)}"
                     f"                  {'yes' if maxed else 'no'}")
        if maxed:
            status = "MAX_4_REACHED"
            detail = ("Budget exhausted with findings still open. Proceed to human "
                      "plan review with the unresolved matters exposed.")

    if status is None:
        status = "CONTINUE"
        detail = (f"Repair the plan, produce a new version, and open cycle "
                  f"{dirs[-1][0] + 1:02d} with a new frozen target.")

    lines += ["", f"LOOP_STATUS: {status}", detail]
    if status != "CONTINUE" and cur[DISPUTED]:
        lines.append("")
        lines.append(f"Disputes for adjudication ({len(cur[DISPUTED])}): "
                     f"{fmt(cur[DISPUTED])}")
        lines.append("§7 requires disputes and unresolved findings to reach the human "
                     "as separate lists.")

    print(f"LOOP_STATUS: {status}" if a.quiet else "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/bootstrap_gate.py`

`sha256 941d60adc96f8e3382a1de86bc202419490c82eba7ec0d54d027cec2e6f56540`

```
#!/usr/bin/env python3
"""The one-time bootstrap review, and the gate that makes it mandatory.

    python scripts/bootstrap_gate.py check
    python scripts/bootstrap_gate.py record --decision APPROVE \\
        --decided-by "Alex Zamurko" --note "..."

Exit 0 = a bootstrap review exists, was approved, and still covers the code that
is actually on disk.
Exit 1 = it does not, and no real protocol cycle may run.
Exit 2 = could not run.

Why this exists
---------------
The orchestrator exists to constrain the implementing agent, and the implementing
agent wrote it. The MC-2 checker decides whether a cycle counts, and the same
agent wrote that too. Neither can go through the process it enables, because the
process does not exist until they do.

Alex Zamurko ruled on 8 September 2026:

    Make a one-time BOOTSTRAP_REVIEW mandatory before relying on those
    components for real protocol cycles. Preserve the exact bootstrap input, raw
    Codex output, findings, responses, and human decision.

So this is the one declared exception to the protocol, made explicit and made
enforceable rather than left as a paragraph someone remembers.

The part that is easy to get wrong
----------------------------------
A gate that only asks "did a bootstrap review happen" passes forever. The review
would authorise the code as it stood that day, the code would change the next
morning, and the gate would keep saying yes about a file that no longer exists in
the form anyone reviewed. That is the same defect as a green test pinned to a
superseded protocol, one level up.

So the decision record pins the sha256 of every component it covers, and `check`
re-hashes them. Editing a reviewed component invalidates the review, by design.
Re-reviewing is the cost of changing the thing that everything else trusts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO / "bootstrap-review"
RECORD = REVIEW_DIR / "decision.json"

# The declared roots. Widened from two to four by Alex Zamurko, 9 September 2026:
# ledger.py and loop_state.py "determine the authoritative meaning of otherwise
# valid review evidence ... An error here could produce a false process outcome
# even when MC-2 evidence is valid."
#
# The section mapping is his, and it is what the review is against:
#
#     validate_cycle.py   MC-2, §10.2
#     run_review.py       §2.2, §10.1
#     ledger.py           §§5, 12
#     loop_state.py       §§6, 13
COMPONENTS = (
    "scripts/validate_cycle.py",
    "scripts/run_review.py",
    "scripts/ledger.py",
    "scripts/loop_state.py",
)

# This file is always covered, whatever the roots are. It was not, and that was
# the sharpest form of the hole Alex found: bootstrap_gate.py did not hash
# itself, so editing `evaluate` to return (True, []) would have defeated every
# other pin while `check` still reported APPROVED. A gate that does not cover
# itself is an honour system with extra steps.
ALWAYS = ("scripts/bootstrap_gate.py",)

# Anything matching this that resolves to a file in scripts/ is treated as an
# executable dependency of the component that mentions it.
PY_REF = __import__("re").compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.py)\b")

# Named in the ruling: "the exact bootstrap input, raw Codex output, findings,
# responses, and human decision". The decision is decision.json; these are the
# other four, and all must be present and non-empty before a decision is written.
EVIDENCE = (
    "codex-input.md",
    "codex-output-raw.md",
    "findings.md",
    "claude-response.md",
)

DECISIONS = ("APPROVE", "RETURN_FOR_REWORK", "REJECT")


class Refused(Exception):
    """Exit 1, change nothing."""


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_lf(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def closure(root: Path) -> dict[str, list[str]]:
    """Every scripts/*.py a covered component can reach, and who reaches it.

    Alex Zamurko, 9 September 2026:

        If validate_cycle.py or run_review.py imports repository-local modules
        whose changes can alter their behaviour, pinning only the two top-level
        files is insufficient. Either include those executable dependencies in
        the bootstrap decision hash set, or establish that the two files are
        behaviorally self-contained.

    They are not self-contained. run_review.py loads bootstrap_gate.py by path
    and invokes validate_cycle.py as a subprocess; loop_state.py invokes
    validate_cycle.py too. Editing a dependency changes a reviewed component's
    behaviour without changing its bytes, so a hash set of top-level files only
    is a hash set with a hole in it.

    Derived by walking references rather than listed by hand, because a
    hand-maintained dependency list is one that is right on the day it is written
    and silently wrong afterwards, which is the failure this whole gate exists to
    prevent one level down.

    Deliberately over-inclusive: a scripts/*.py named anywhere in a covered file,
    including in a usage line in its docstring, is treated as a dependency. The
    cost of over-inclusion is that an unrelated edit forces a re-review. The cost
    of under-inclusion is a component whose behaviour changed while its approval
    still verified. Those are not comparable, so the ambiguity resolves toward
    covering more.
    """
    reached: dict[str, list[str]] = {}
    pending = list(COMPONENTS) + list(ALWAYS)
    seen: set[str] = set()

    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            continue
        for name in sorted(set(PY_REF.findall(p.read_text(encoding="utf-8")))):
            dep = f"scripts/{name}"
            if dep == rel or not (root / dep).is_file():
                continue
            reached.setdefault(dep, []).append(rel)
            if dep not in seen:
                pending.append(dep)

    # Roots are covered because they were declared, not because something
    # reached them. Keep the two kinds separate in the record.
    for rel in list(COMPONENTS) + list(ALWAYS):
        reached.pop(rel, None)
    return reached


def covered(root: Path) -> dict[str, str]:
    """Every path the decision must pin: declared roots, this file, and the
    executable closure of both."""
    out: dict[str, str] = {}
    for rel in list(COMPONENTS) + list(ALWAYS) + sorted(closure(root)):
        p = root / rel
        if not p.is_file():
            raise Refused(f"component under bootstrap review is missing: {rel}")
        out[rel] = sha256_file(p)
    return out


def component_hashes(root: Path) -> dict[str, str]:
    return covered(root)


# ------------------------------------------------------------------ check

def evaluate(root: Path) -> tuple[bool, list[str]]:
    """(ok, reasons). Never raises; the reasons are the useful output."""
    rec = root / "bootstrap-review" / "decision.json"
    if not rec.is_file():
        return False, [
            "no bootstrap review on record.",
            "  These components have not been independently reviewed, and they",
            "  cannot go through the process they enable:",
            *[f"    {c}" for c in list(COMPONENTS) + list(ALWAYS)],
            "  Ruled mandatory 8 September 2026, widened to the finding ledger",
            "  and loop controller on 9 September because they determine the",
            "  authoritative meaning of otherwise valid review evidence.",
            f"  Expected: {rec.relative_to(root).as_posix()}",
        ]

    try:
        d = json.loads(rec.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"the bootstrap decision record is not valid JSON: {e}"]

    reasons: list[str] = []

    decision = d.get("decision")
    if decision != "APPROVE":
        reasons.append(f"the bootstrap review decision is {decision!r}, not APPROVE.")
        if decision in ("RETURN_FOR_REWORK", "REJECT"):
            reasons.append("  Repair the components, rerun the review, record a "
                           "new decision.")

    pinned = d.get("components") or {}

    # Required now, which may be more than was required when the decision was
    # written: the root list was widened on 9 September, and the dependency
    # closure changes whenever a covered file starts referencing another. A
    # decision that predates either is not a decision about the current system.
    try:
        required = set(covered(root))
    except Refused as e:
        return False, [str(e)]

    absent = sorted(required - set(pinned))
    if absent:
        reasons.append(
            "the review does not cover every component it must: "
            + ", ".join(absent) +
            "\n    Either the covered set was widened after this decision, or a "
            "reviewed file\n    now reaches code the decision never pinned. "
            "Re-review.")

    for rel, recorded in sorted(pinned.items()):
        p = root / rel
        if not p.is_file():
            reasons.append(f"{rel} was reviewed but no longer exists")
            continue
        actual = sha256_file(p)
        if actual != recorded:
            reasons.append(
                f"{rel} has changed since it was reviewed.\n"
                f"    reviewed  {recorded}\n"
                f"    on disk   {actual}\n"
                "    The approval covers the reviewed bytes, not the filename. "
                "Re-review or revert.")

    return (not reasons), reasons


def cmd_check(root: Path = REPO, quiet: bool = False) -> int:
    ok, reasons = evaluate(root)
    if ok:
        d = json.loads((root / "bootstrap-review" / "decision.json")
                       .read_text(encoding="utf-8"))
        if not quiet:
            deps = closure(root)
            print("BOOTSTRAP_REVIEW: APPROVED")
            print(f"  decided by  {d.get('decided_by', '?')}")
            print(f"  decided at  {d.get('decided_at', '?')}")
            for rel in list(COMPONENTS) + list(ALWAYS):
                print(f"  root        {rel}  {d['components'][rel][:16]}…")
            for rel in sorted(deps):
                via = ", ".join(Path(v).name for v in deps[rel])
                print(f"  dependency  {rel}  {d['components'][rel][:16]}…  "
                      f"via {via}")
        return 0
    if not quiet:
        print("BOOTSTRAP_REVIEW: NOT SATISFIED")
        for r in reasons:
            print(f"  {r}")
        print()
        print("No real protocol cycle may run until this passes.")
    return 1


# ------------------------------------------------------------------ record

def cmd_record(a: argparse.Namespace) -> int:
    if a.decision not in DECISIONS:
        raise Refused(f"decision must be one of {', '.join(DECISIONS)}")
    if not a.decided_by.strip():
        raise Refused("--decided-by is required; a human gate with no human "
                      "named is not a human gate")
    # The decision is made in Slack and recorded here by someone else, so the
    # record has to point back at where it was actually made. Without this the
    # operator can write any name into --decided-by and nothing distinguishes a
    # relayed approval from an invented one. Same distinction as everywhere else
    # in this repository: recorded, or merely asserted.
    if len(a.note.strip()) < 20:
        raise Refused(
            "--note is required, and must attribute the decision.\n"
            "  Give where it was made and what was said: channel, timestamp, and "
            "the words.\n"
            "  Example:\n"
            '    --note "#gap, 9 Sep 2026 12:03 AM, Alex Zamurko: \'Confirmed '
            "...'\"\n"
            "  --decided-by alone is a name typed by whoever ran this command.")

    absent = []
    for name in EVIDENCE:
        p = REVIEW_DIR / name
        if not p.is_file():
            absent.append(f"{name} (missing)")
        elif p.stat().st_size == 0:
            absent.append(f"{name} (empty)")
    if absent:
        raise Refused(
            "the bootstrap review evidence is incomplete, so there is nothing to "
            "decide about:\n  " + "\n  ".join(absent) +
            f"\n  Expected under {REVIEW_DIR.relative_to(REPO).as_posix()}/\n"
            "  The ruling requires the exact input, the raw Codex output, the "
            "findings and\n  the responses to be preserved alongside the decision.")

    if RECORD.exists():
        prior = json.loads(RECORD.read_text(encoding="utf-8"))
        if not a.supersede:
            raise Refused(
                f"a bootstrap decision already exists: {prior.get('decision')} "
                f"by {prior.get('decided_by')} at {prior.get('decided_at')}.\n"
                "  It is one-time by design. Pass --supersede to replace it, "
                "which preserves\n  the prior decision in the record rather than "
                "overwriting it silently.")

    record = {
        "decision": a.decision,
        "decided_by": a.decided_by.strip(),
        "decided_at": now(),
        "note": a.note,
        "components": component_hashes(REPO),
        "roots": list(COMPONENTS) + list(ALWAYS),
        "dependencies": {k: v for k, v in sorted(closure(REPO).items())},
        "evidence": {n: sha256_file(REVIEW_DIR / n) for n in EVIDENCE},
        "authority": "Alex Zamurko, 8 September 2026: a one-time BOOTSTRAP_REVIEW "
                     "is mandatory before relying on these components for real "
                     "protocol cycles.",
    }
    if RECORD.exists():
        record["supersedes"] = json.loads(RECORD.read_text(encoding="utf-8"))

    write_lf(RECORD, json.dumps(record, indent=2) + "\n")
    print(f"recorded {RECORD.relative_to(REPO).as_posix()}")
    print(f"  decision   {a.decision}")
    print(f"  decided by {record['decided_by']}")
    for rel, h in record["components"].items():
        print(f"  covers     {rel}  {h[:16]}…")
    if a.decision != "APPROVE":
        print()
        print("Real protocol cycles remain blocked until an APPROVE is recorded.")
    return 0


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="does an approved, still-current bootstrap "
                                 "review exist")

    r = sub.add_parser("record", help="record the human decision on the "
                                      "bootstrap review")
    r.add_argument("--decision", required=True, help=" | ".join(DECISIONS))
    r.add_argument("--decided-by", required=True)
    r.add_argument("--note", default="")
    r.add_argument("--supersede", action="store_true",
                   help="replace an existing decision, preserving it in the record")

    a = ap.parse_args(argv[1:])
    try:
        if a.cmd == "check":
            return cmd_check()
        return cmd_record(a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

