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
