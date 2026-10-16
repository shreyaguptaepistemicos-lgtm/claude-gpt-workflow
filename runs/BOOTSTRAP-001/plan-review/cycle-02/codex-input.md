# Review input — BOOTSTRAP-001 / plan review / cycle 02

```text
TARGET_SHA256   8facc07a82004f21b12bd7df699d4b17156c562d4bcae61b15693647dd3b5107
PROTOCOL_SHA256 296594a3c06cd2f9c66976c369b15804f39bbb2be37b5e62234d37fafd28d483
SPEC_SHA256     ad7f1099b66263123795dc2bf15f8275ad290bf91cdb0f5efaa09a942a8f321f
```

The target hash above is the binding between the frozen artifact and this
input. Quote it in your response.

---

# Bootstrap review prompt — cycle 02

Second cycle of the `BOOTSTRAP_REVIEW` of the execution layer. Hand-written, per
Alex Zamurko, 8 September: a hand-written prompt is acceptable for the bootstrap.
This is not one of the five production prompts.

Cycle 01 produced eighteen findings. All eighteen were accepted and none is
RESOLVED, because §5 gives RESOLVED only "once the repair is demonstrated in the
next review target". This is that target.

---

## What this cycle is for

Two questions, and the first is the one §5 turns on.

**1. Are the repairs demonstrated?** For each cycle-01 finding claimed repaired
below, does the current code actually fix what the finding described, and do its
controls establish that it does? A finding whose repair does not hold stays OPEN,
and saying so is the most useful thing this review can do.

**2. Is anything new wrong?** The repairs added three files and changed five,
and a fourth file has been in the covered set since before cycle 01 without ever
appearing in a reviewer's list. New defects introduced by the repairs are
ordinary findings.

## The account below is the implementing agent's own

Everything in the next two sections is Claude's description of Claude's work. No
one else has checked it. It is supplied so you spend the cycle on verification
rather than rediscovery, and it should be treated as a claim, not as evidence.

The evidence is the code and these commits:

```text
1ce74b7  F02 and F11
ecdcf1c  ruling 3, capture supersession authority
e704aac  rulings 1 and 2, the bounded bootstrap exception
b43fc46  issue 7 recurrence, and F06
```

A finding listed as repaired that is not repaired is a finding about this
prompt as much as about the code, and it is exactly what cycle 02 exists to
catch. Say so plainly if you find one.

## What you are reviewing

Ten artifacts, hashed and listed in `target.json`. Six were reviewed in cycle
01. Four have **never been seen by any reviewer**:

```text
specs/evidence-schema-v1.0.md   the frozen evidence structure
scripts/validate_cycle.py       the MC-2 conformance gate, fifteen checks
scripts/run_review.py           the review runner
scripts/ledger.py               the finding and state ledger
scripts/loop_state.py           the loop-state controller
scripts/bootstrap_gate.py       the gate enforcing this review

scripts/findings_format.py      UNREVIEWED. the single parser: raw reviewer
                                output to structured findings
scripts/cycle_projection.py     UNREVIEWED. what counts as a cycle, for both
                                the ledger and the controller
scripts/authority.py            UNREVIEWED. approvals that must come from
                                outside the implementing agent
scripts/run_pins.py             UNREVIEWED. which artifacts govern a run, and
                                which are under review
```

All four are load-bearing. `findings_format.py` decides what the reviewer said;
`cycle_projection.py` decides whether a recorded event may authorise a state
transition; `authority.py` decides whether a supersession may proceed;
`run_pins.py` decides what a cycle is measured against. An error in any of them
produces a false process outcome from evidence that passes MC-2 cleanly, which
is the reason Alex Zamurko gave for widening the review scope on 9 September.

None of them was declared as a component. All four entered the gate's covered
set through its import discovery, which is the B01-F16 repair behaving as
intended. Worth checking that it did so correctly rather than by luck, and worth
noting that until 10 September nothing checked that a covered file was named in
the prompt at all: three of these were covered, treated as reviewed, and absent
from the reviewer's list at the same time.

Their negative-control suites are supplied as evidence that the checks are
falsifiable:

```text
scripts/test_validate_cycle.py   24 controls
scripts/test_run_review.py       62 controls
scripts/test_ledger.py           56 controls, covering the ledger and controller
scripts/test_bootstrap_gate.py   36 controls
scripts/test_interfaces.py       20 controls, across seven component seams
```

Those counts are asserted here and checked by `scripts/test_prompts.py` against
the suites themselves.

## What you are reviewing them against

The protocol at the commit and hash recorded in `target.json`, unchanged since
cycle 01. Where this prompt and the protocol disagree, the protocol governs and
the disagreement is itself a finding.

Alex Zamurko's section mapping, carried forward, with the four unreviewed files
added:

```text
scripts/validate_cycle.py    MC-2, and §10.2 for implementation review
scripts/run_review.py        §2.2 input composition, §10.1 target fields
scripts/ledger.py            §§5 and 12
scripts/loop_state.py        §§6 and 13
scripts/bootstrap_gate.py    no protocol section; his 8 September ruling
scripts/findings_format.py   §4 finding structure, and the schema's
                             FINDING_ID_GRAMMAR
scripts/cycle_projection.py  §§2, 3 and 6: what counts as a valid cycle
scripts/authority.py         no protocol section; his 9 September ruling 3
scripts/run_pins.py          no protocol section; his 10 September Run-Pin and
                             Review-Target Separation Specification
```

## Claimed repairs, to verify

```text
B01-F02  loop_state.py evaluates every valid boundary in order and retains the
         first terminal outcome; run_review refuses to open a cycle after one.
         Continuing past an exit needs a record in loop-authorizations.json
         naming the boundary and the exit it clears.
B01-F03  cmd_record writes per-cycle findings.json; absence never means zero.
B01-F06  check 13 hashes the approved plan itself and requires the approval to
         name the artifact and to be an APPROVE.
B01-F08  the bootstrap gate is checked at freeze as well as init.
B01-F09  recording a decision refuses if the components drifted from the frozen
         review target.
B01-F10  evidence-schema-v1.0.md is in the gate's covered set.
B01-F11  ledger and controller share cycle_projection.py. An event in a cycle
         that fails MC-2 neither authorises a transition nor blocks one.
B01-F13  recurrence has its own transition, RESOLVED -> OPEN, keeping the
         identifier. The duplicate-id refusal no longer tells the operator to
         rename.
B01-F14  run.json records MC1_ENFORCEMENT.
B01-F15  the immutability and proof language is gone from the covered files, and
         a control scans for its return.
B01-F16  the closure discovers real imports by parsing, not only filename
         strings.
B01-F17  all five implementation refusals are exercised.
B01-F18  the seam-1 probes sit inside a cycle layout, so check 13 no longer
         fails on all of them for the wrong reason.
```

**Deferred by Alex Zamurko, 9 September, and still OPEN by his ruling, not by
oversight**: B01-F01, B01-F04, B01-F05, B01-F07, B01-F12. He scoped this round
to the critical set. They do not need re-reporting as new findings. If a repair
above interacts badly with one of them, that interaction is a finding.

## Declared decisions

Cycle 01's decisions A to G stand and are in `bootstrap-review.md`. Assess them
again if the repairs changed what they mean. Five are new.

```text
H  cycle_projection distinguishes three states, not two: VALID, INVALID and
   UNJUDGED. Only INVALID strips authority. A cycle with no directory yet is
   the one being assembled, and a ledger that refused to record into it would
   be unusable. Authority is recomputed on every read rather than frozen at
   write time, so an event loses authority the moment its cycle is judged and
   fails. The ledger's stored `state` field is a cache of that projection and
   nothing reads it to decide anything.

I  The first terminal loop outcome governs, and later cycles do not override
   it. An authorisation to continue must name both the boundary and the exit
   it clears; a blanket authorisation would restore B01-F02 under a different
   spelling. Cycles run after an unauthorised exit are reported, not absorbed.

J  authority.py claims only what CONVENTION_ONLY supports. It does not prove
   who wrote an approval. What it enforces is that the approval exists as a
   separate artifact, names a person and a reason, and binds by hash to the
   exact bytes it approves, so it cannot be recycled. The hashes are printed
   only by the refusal, so obtaining an approval is a step outside the command.
   The intended change is that unilateral supersession becomes a deliberate
   forgery naming a person rather than a flag. Argue with this if the claim is
   still stronger than the mechanism.

K  The bootstrap exception ends at the first runner approval, and the check
   consults git history as well as the working tree so that deleting the
   approval does not reopen it. This rests on an asymmetry: writing an approval
   only makes the rules stricter, so the direction worth closing is removal. A
   history rewrite still defeats it.
```

L  A run-level pin and a review target are disjoint roles, per Alex Zamurko's
   Run-Pin and Review-Target Separation Specification of 10 September. run.json
   is not edited when the pin set changes; it stays the record of what was
   pinned at init, and amendments are appended to pin-amendments.json with
   reason, affected artifacts, prior set, new set and effective cycle. The set
   governing a cycle is replayed from that history, so cycle 01 keeps the pins
   it was conducted under and cycle 02 gets the amended set.

   This was found by the loop deadlocking on it: evidence-schema-v1.0.md was
   both BOOTSTRAP-001's only run-level pin and cycle 01's first review target,
   so repairing findings about it broke the run's own pin and blocked the cycle
   meant to demonstrate the repairs. Assess whether the amendment mechanism can
   itself be used to make an inconvenient pin disappear.

H and J are the two most worth arguing with. H decides which recorded events
carry authority, and J decides whether a control the implementing agent cannot
operate has actually been built or merely described.

## Known, and not needing a finding

**Checks 1 to 4 are one mechanism**, file existence, and only check 4 is
demonstrated. Known from cycle 01. Comparable cases elsewhere still count.

## The two failure modes that matter most

**A check that cannot come back false.** For every check in `validate_cycle.py`,
every refusal in `run_review.py` and `authority.py`, and every rule in
`cycle_projection.py`, ask whether the supplied controls demonstrate it firing,
or whether the control merely exercises the same path under another name.

The implementing agent claims every control added in this round was verified by
mutating the repaired logic and confirming the control went red, and that three
controls came back alive on the first attempt and were rewritten. That claim is
not evidence. The suites are in the target; check whether the controls could
actually fail.

**A claim stronger than its evidence.** `MC1_ENFORCEMENT` is `CONVENTION_ONLY`.
Flag any language in the schema, the scripts or their documentation implying
technical protection, immutability, prevention, or a proven binding between
reviewer input and reviewer output. `authority.py` and `cycle_projection.py` are
new prose and have never been read by a reviewer.

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

One block per finding, persistent identifier, cycle 02:

```text
Finding ID: B02-F01
Class:
Artifact:
Location:
Evidence:
Finding:
Required correction:
```

For a cycle-01 finding whose repair does not hold, keep the original identifier
and say so explicitly, in this form, so the ledger can record the recurrence
against the persistent identifier rather than opening a new one:

```text
Finding ID: B01-F11
Status: REPAIR NOT DEMONSTRATED
Evidence:
Finding:
Required correction:
```

Quote the `TARGET_SHA256` from the top of this input in your first line.

State explicitly which claimed repairs you checked and found to hold. Silence
about a repair reads as a verdict nobody gave, which is the defect class this
whole review exists to catch. If you find nothing in a category, say so rather
than omitting it.

## Scope limits

Out of scope: style, performance, and anything in `specs/gap/`. Naming is out of
scope except where decision A is wrong.

Not yet built, so their absence is not a finding: the human review package
generator (§7) and the Gold runner (§15). There is still no A1E-001 plan or
implementation; this is the tooling only.

The five production prompts `specs/prompts/01`–`05` exist and are not in this
target. Their absence is a scoping decision, not a claim that they are unwritten.

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

`sha256 4203ba64bd5ba1db9cd56357c8bf9dd8e6efb419fab7f7635a415c272d3a739c`

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

Recording the target's hash detects a later change to the artifact, provided the
check is run and the checking code is faithful. It does not prevent one, and
under `CONVENTION_ONLY` nothing here does. The embedded hash is what ties that
artifact to the input the reviewer received, and its absence is what made the
GSD pilot's criterion 1 unprovable.

An earlier version of this paragraph said freezing "proves the artifact did not
change". Codex raised that as B01-F15 and was right: a hash recorded by the same
authority that can rewrite the artifact establishes drift detection, not
immutability. The distinction is the whole content of MC-1's enforcement-status
field, so the schema should not blur it.

## Canonical Finding ID grammar

One grammar, declared here, validated by the runner, preserved unchanged by the
ledger. Per Alex Zamurko, 9 September 2026:

    Prompt, parser, and ledger must not independently impose different
    grammars. The clean choice is: the review format defines the canonical
    grammar, the runner validates it, and the ledger preserves it unchanged.

```text
FINDING_ID_GRAMMAR = ^[A-Z]{0,2}\d{2}-F\d{2,3}$
```

An optional prefix of up to two capitals, the cycle as two digits, `-F`, and the
finding number. `C02-F03` from §4 and `B01-F01` from the bootstrap review both
satisfy it.

This exists because they did diverge. The prompt told the reviewer to use
`B01-F01`; the ledger enforced `C{cycle}-F{nn}`; so eighteen findings were
renamed during transcription and the authoritative record disagreed with the
ledger about what every one of them was called. Renaming a reviewer's identifier
is B01-F13.

An identifier that does not match makes the review result invalid. It is never
silently corrected, because a corrected identifier is a different finding
wearing the right name.

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

`sha256 b61bea2ab823558570ab9e8afcc8d06ad20c02f3b162cd3dc79545a40ceebb07`

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


def _check_hashed_ref(entry, repo_root: Path, label: str,
                      cycle_dir: Path | None = None) -> list[str]:
    """Validate a bound artifact against the cycle's preserved copy.

    Alex Zamurko, 9 September 2026: "At freeze, snapshot the exact reviewed
    artifact bytes into the cycle evidence directory and validate those
    preserved copies, not the live working tree."

    This used to hash `repo_root / path`, the live file. A completed cycle
    therefore went INVALID the moment anyone repaired what it had reviewed —
    and since the controller ignores events in invalid cycles, acting on a
    review erased it. Repair between cycles is the design; it cannot be what
    destroys the previous cycle.

    The live tree is now irrelevant to a completed cycle's validity. That is the
    point: the evidence is self-contained, and a cycle means the same thing on a
    fresh clone a year later as it does here.
    """
    if not isinstance(entry, dict) or "path" not in entry or "sha256" not in entry:
        return [f"{label} must be an object with path and sha256"]

    snap = (cycle_dir / "artifacts" / entry["path"]) if cycle_dir else None
    if snap is not None and snap.is_file():
        actual = sha256_file(snap)
        if actual != entry["sha256"]:
            return [f"{label} preserved copy of {entry['path']} does not match "
                    f"its record: {entry['sha256']} vs {actual}. The snapshot "
                    "has been altered since the freeze."]
        return []

    return [f"{label} has no preserved copy: expected "
            f"{(snap.relative_to(cycle_dir) if snap else '?')}.\n"
            "A cycle frozen without snapshots cannot be validated, because the "
            "only\nremaining source for the reviewed bytes is a working tree "
            "that has since moved on."]


def _approval_plan_path(approval: Path) -> str | None:
    """Which artifact the approval record's hash is of.

    §7.3 freezes APPROVED_PLAN_HASH but the protocol does not say where the
    path lives, so both places are accepted and either is enough. What is not
    acceptable is neither: a hash with no named artifact can only be compared
    against another copy of itself, which is what B01-F06 was.
    """
    try:
        d = json.loads(approval.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    p = d.get("approved_plan_path")
    if p:
        return p
    files = d.get("approved_plan_files")
    if isinstance(files, list) and len(files) == 1:
        return files[0]
    return None


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
                problems += _check_hashed_ref(entry, repo_root, "plan_files entry",
                                             cycle_dir)
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
            # B01-F06. This used to stop here, comparing two recorded strings.
            # Both records could agree perfectly while the plan itself had
            # changed underneath them, so an implementation cycle passed all
            # fifteen checks against a plan nobody approved. Codex demonstrated
            # exactly that on an isolated fixture.
            #
            # So the artifact is hashed, and the approval's decision is read
            # rather than assumed: an approval record that says
            # RETURN_FOR_REWORK is not an approval, and a hash matching one is
            # matching the wrong thing.
            problems13: list[str] = []
            if str(ap).lower() != str(frozen).lower():
                problems13.append(f"target {ap}\n          approval {frozen}")

            decision = None
            try:
                decision = json.loads(
                    approval.read_text(encoding="utf-8")).get("decision")
            except json.JSONDecodeError:
                pass
            if decision != "APPROVE":
                problems13.append(
                    f"the approval record's decision is {decision!r}, not "
                    "APPROVE; §7.3 freezes APPROVED_PLAN_HASH on approval, so a "
                    "hash carried by any other decision is not an approved plan")

            plan_ref = target.get("approved_plan_path") or _approval_plan_path(approval)
            if not plan_ref:
                problems13.append(
                    "neither the target nor the approval record says which "
                    "artifact the approved-plan hash is of, so the hash cannot "
                    "be checked against anything. Two matching records are not "
                    "an approved plan.")
            else:
                snap = cycle_dir / "artifacts" / plan_ref
                live = repo_root / plan_ref
                src = snap if snap.is_file() else live
                if not src.is_file():
                    problems13.append(f"approved plan not found: {plan_ref}")
                else:
                    actual = sha256_file(src)
                    if actual != str(frozen).lower():
                        problems13.append(
                            f"{plan_ref} does not hash to the approved value\n"
                            f"          approved {frozen}\n"
                            f"          actual   {actual}")

            r.add(13, "approved-plan hash matches the frozen approved plan",
                  not problems13, "; ".join(problems13))

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

`sha256 976b9af1155f5c55f122b5640af09afd6640626d8fd4214ddf407d23aea9715a`

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import authority  # noqa: E402
import run_pins  # noqa: E402

VALIDATOR = REPO / "scripts" / "validate_cycle.py"

MAX_CYCLES = 4
REVIEW_TYPES = ("plan", "implementation")

# §6's four exits. Named here rather than "not CONTINUE" so that a future status
# the controller learns to emit does not silently become permission to open
# another cycle.
TERMINAL_EXITS = ("CONVERGED", "HUMAN_ADJUDICATION_REQUIRED", "STALLED",
                  "MAX_4_REACHED")
INVOCATIONS = ("manual", "automated")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")

# MC-1 requires every run to record this. CONVENTION_ONLY here because the
# implementing agent and the review evidence share one write authority on a
# single-user machine; see specs/evidence-schema-v1.0.md. Upgrading it is a
# change to the environment, not to this constant.
MC1_ENFORCEMENT = "CONVENTION_ONLY"


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


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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
    # Loaded by path rather than by name. `from bootstrap_gate import ...` works
    # only when the script's own directory happens to be on sys.path, which it is
    # when run directly and is not in several other cases. A gate that silently
    # becomes an ImportError is a gate that stops gating.
    gate = load_gate()

    if args.bootstrap_exempt:
        # Ruling 2, 9 September: the exception "ends immediately after the first
        # human approval of a runner". Before this, --bootstrap-exempt was a flag
        # with no expiry, so "bootstrap" could quietly become the permanent way
        # runs were created. The termination is now a question the gate answers
        # from the record rather than a date anyone has to remember.
        available, why = gate.bootstrap_exception_available(REPO)
        if not available:
            raise Refused(
                "--bootstrap-exempt is no longer available.\n  "
                + "\n  ".join(why) +
                "\n\n  Create the run without the flag. The components have an "
                "approved runner now,\n  so real protocol runs are the only kind "
                "left to make.")
    else:
        ok, reasons = gate.evaluate(REPO)
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
        # B01-F14. MC-1: "Each run records: MC1_ENFORCEMENT:". A statement in
        # repository documentation is not a record on the run, and a reader of
        # this run's evidence should not have to go looking elsewhere to learn
        # what the enforcement status was at the time it was created.
        "mc1_enforcement": MC1_ENFORCEMENT,
        # Recorded on the run, not just checked at init, so a reader of the
        # evidence can tell which kind of run this was without consulting
        # anything else.
        "bootstrap_review": ("EXEMPT — BOOTSTRAP / DEVELOPMENT EVIDENCE, "
                             "NOT_A_PROTOCOL_CYCLE"
                             if args.bootstrap_exempt else "APPROVED"),
        # Ruling 1: cycle 02 sits inside the exception because no approved runner
        # exists yet. Recorded on the run so a later reader can see which side of
        # the termination this run was created on, without reconstructing the
        # state of runner-approvals/ at the time.
        "runner_approval_chain": ("NOT_STARTED — no approved runner exists"
                                  if gate.bootstrap_exception_available(REPO)[0]
                                  else "ACTIVE — candidate runners are reviewed "
                                       "by the prior approved runner"),
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


def check_pins_still_hold(run: dict, run_dir: Path | None = None,
                          cycle_n: int | None = None) -> None:
    """The governing artifacts must not have moved since init.

    A run whose spec changed underneath it is not four cycles against one spec;
    it is four cycles against whatever happened to be on disk each time. This is
    the check that makes the run.json pin mean something.

    Alex Zamurko's Run-Pin and Review-Target Separation Specification, 10
    September, narrows what belongs in that set: "A run-level pin may include
    only artifacts that are required to remain invariant for the entire run." An
    artifact under review is not one of those, and pinning one anyway is what
    stopped BOOTSTRAP-001 between cycles 01 and 02.

    So the set checked here is the one in force for the cycle being frozen,
    replayed from the amendment history, rather than whatever run.json listed at
    init. Cycle 01 is still checked against cycle 01's pins.
    """
    pins = None
    if run_dir is not None and cycle_n is not None:
        try:
            pins = set(run_pins.governing_pins(run, run_dir, cycle_n))
        except run_pins.PinError as e:
            raise Refused(f"the run's pin history cannot be read, so what "
                          f"governs this cycle is undeterminable:\n  {e}")

    drift: list[str] = []

    def still_pinned(rel_path: str) -> bool:
        return pins is None or rel_path in pins

    if still_pinned(run["protocol"]["path"]):
        proto = REPO / run["protocol"]["path"]
        if not proto.is_file():
            drift.append(f"protocol file is gone: {run['protocol']['path']}")
        elif sha256_file(proto) != run["protocol"]["sha256"]:
            drift.append(f"protocol changed since init: {run['protocol']['path']}\n"
                         f"    pinned {run['protocol']['sha256']}\n"
                         f"    actual {sha256_file(proto)}")

    for e in run["spec_files"]:
        if not still_pinned(e["path"]):
            continue
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


def check_pin_target_separation(run: dict, run_dir: Path, cycle_n: int,
                                target_paths: list[str]) -> None:
    """§2's governing invariant, refused rather than described.

    "No review process may require an artifact to remain byte-invariant for the
    duration of a run while simultaneously requiring that same artifact version
    to change in order to resolve review findings."

    Checked at freeze, where both sides are known for the first time: the pin set
    comes from the run and the target list from this cycle's arguments. Nothing
    checked it before, which is why the contradiction was only discovered by the
    loop deadlocking on it two cycles later.
    """
    try:
        pins = run_pins.governing_pins(run, run_dir, cycle_n)
    except run_pins.PinError as e:
        raise Refused(f"the run's pin history cannot be read:\n  {e}")
    clash = run_pins.separation_violations(pins, target_paths)
    if not clash:
        return
    raise Refused(
        "an artifact cannot be both a run-level governing pin and a review "
        "target:\n  " + "\n  ".join(clash) +
        "\n\n  It would have to stay byte-identical for the whole run and also "
        "change to\n  resolve any finding raised about it. The first repair "
        "would break the run's own\n  pin and stop the cycle that was meant to "
        "demonstrate the repair.\n\n"
        "  Alex Zamurko, 10 September: an artifact belongs to exactly one role, "
        "RUN-GOVERNING\n  or REVIEW-TARGET, unless explicit ACTIVE/CANDIDATE "
        "version separation is in place.\n"
        "  Amend the run's pin set, recording reason, affected artifacts, prior "
        "set, new set\n  and effective cycle in pin-amendments.json.")


def load_gate():
    """The bootstrap gate module, loaded by path.

    By path rather than by name: `from bootstrap_gate import ...` works only
    when the script's directory happens to be on sys.path, and a gate that
    silently becomes an ImportError is a gate that stops gating.
    """
    import importlib.util
    gate_py = Path(__file__).resolve().parent / "bootstrap_gate.py"
    if not gate_py.is_file():
        raise Refused(f"the bootstrap gate is missing: {gate_py}\n"
                      "  Refusing rather than proceeding. A missing gate is not "
                      "an absent requirement.")
    spec_ = importlib.util.spec_from_file_location("_bootstrap_gate", gate_py)
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    return mod


def check_bootstrap_still_holds(run: dict) -> None:
    """B01-F08: the gate has to hold now, not just when the run was created.

    Codex: "Bootstrap approval is evaluated only at initialization. A probe
    approved bootstrap, initialized a real run, changed validate_cycle.py, and
    successfully froze a cycle."

    I put the check at init and reasoned that init is where a run becomes a thing
    that exists. That was half right and wrong about the half that matters: a run
    can sit for days between init and its cycles, and every cycle is where the
    tooling is actually relied upon. So the gate is checked at both, and an
    exempt run stays exempt at both.
    """
    if str(run.get("bootstrap_review", "")).startswith("EXEMPT"):
        return
    ok, reasons = load_gate().evaluate(REPO)
    if not ok:
        raise Refused(
            "BOOTSTRAP_REVIEW no longer holds, so this cycle may not be "
            "frozen:\n  " + "\n  ".join(reasons) +
            "\n\n  The approval was valid when the run was created. Something "
            "covered by it has\n  changed since. Re-review, or revert the "
            "change.")


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


def check_loop_not_terminated(review_dir: Path, n: int) -> None:
    """Refuse to open a cycle after the loop has already exited.

    B01-F02: "The runner checks previous output existence, not the previous loop
    exit." Existence is the wrong question. A cycle can be perfectly well closed
    and still be the cycle at which §6 required the loop to stop, and freezing
    the next one produced evidence under a loop that had already terminated.

    The controller now retains the first terminal outcome, so it will report that
    exit rather than being overwritten by whatever the new cycle does. This makes
    the runner refuse to create the situation in the first place, which is the
    half that keeps the unauthorized cycle from existing at all.

    An undeterminable loop state is a refusal too. If the controller cannot say
    whether the loop has exited, nobody can say whether another cycle is
    permitted, and guessing CONTINUE is the assumption that costs a cycle.
    """
    if n <= 1:
        return
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "loop_state.py"),
         "--review", str(review_dir), "--quiet"],
        capture_output=True, text=True)
    if r.returncode == 2:
        raise Refused(
            "the loop state cannot be determined, so whether another cycle is "
            "permitted cannot be\ndetermined either:\n  "
            + (r.stderr.strip().splitlines() or ["(no reason given)"])[0]
            + "\nRepair the evidence and rerun. Opening a cycle on an "
              "undeterminable loop is how a\nterminated loop keeps running.")
    status = ""
    for line in r.stdout.splitlines():
        if line.startswith("LOOP_STATUS:"):
            status = line.split(":", 1)[1].strip()
    if status in TERMINAL_EXITS:
        raise Refused(
            f"the loop has already exited: LOOP_STATUS is {status}.\n"
            f"Opening cycle {n:02d} would produce evidence under a loop that "
            "§6 had already stopped.\n"
            "If another loop was genuinely approved, record the human "
            "authorization in\n  "
            f"{rel(review_dir / 'loop-authorizations.json')}\n"
            "naming the boundary, the outcome it clears, who authorized it and "
            "why. Otherwise\ntake the outcome to human review.")


def compose_input(prompt: str, target_hash: str, run: dict, rtype: str,
                  cycle_n: int, artifacts: list[tuple[dict, str]],
                  protocol_text: str = "") -> str:
    """Everything the reviewer needs, in the file the target hash binds.

    The protocol text is included, not merely hashed. Every review is *against*
    the protocol, and an earlier version of this function named PROTOCOL_SHA256
    in the header and stopped there. A reviewer cannot read a hash, so it would
    have been asked to judge conformance to a document it had never seen and
    would have answered from memory or invention.

    That is the pilot's failure restated: recording an artifact's hash detects a
    later change to it, and says nothing about whether the reviewer read it.
    Here it was worse, because the reviewer could not have read it at all.

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
    check_bootstrap_still_holds(run)

    prompt_path = require_file(Path(args.prompt).resolve(), "prompt file")
    prompt = prompt_path.read_text(encoding="utf-8")

    review_dir = REPO / "runs" / args.run / f"{args.type}-review"
    run_dir = REPO / "runs" / args.run
    n = next_cycle(review_dir)
    if n > MAX_CYCLES:
        raise Refused(f"cycle {n} would exceed the {MAX_CYCLES}-cycle budget for "
                      f"{args.run} {args.type} review.\n"
                      "MAX_4_REACHED is an exit, not an obstacle to route around. "
                      "Escalate to human review.")
    # After n is known, because the pin set in force is a property of the cycle
    # rather than of the run: an amendment effective at cycle k governs k onward
    # and leaves earlier cycles checked against what they were conducted under.
    check_pins_still_hold(run, run_dir, n)
    check_previous_cycle_closed(review_dir, n)
    check_loop_not_terminated(review_dir, n)

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
        # Both sides are known for the first time here: the pin set from the run,
        # the target list from this cycle's arguments. Nothing compared them
        # before, which is why the contradiction surfaced only when the loop
        # deadlocked on it a cycle later.
        check_pin_target_separation(run, run_dir, n, [r["path"] for r in refs])
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

    # ---- snapshot the reviewed bytes ----
    # Alex Zamurko, 9 September 2026:
    #
    #     At freeze, snapshot the exact reviewed artifact bytes into the cycle
    #     evidence directory and validate those preserved copies, not the live
    #     working tree. A completed review cycle must remain valid after the
    #     implementation is repaired.
    #
    # Before this, freeze recorded a hash of a file that stayed mutable, and
    # check 9 re-hashed the live tree. So repairing the code a review asked for
    # invalidated the cycle that asked, the controller then ignored its events,
    # and eighteen findings vanished from loop state. Repair between cycles is
    # the entire design; it cannot be the thing that destroys the previous cycle.
    #
    # Every artifact bound to the target, and only those: not top-level files
    # alone, not the whole repository.
    snapshot = cycle / "artifacts"
    for ref, body in artifacts:
        dest = snapshot / ref["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((REPO / ref["path"]).read_bytes())
        if sha256_file(dest) != ref["sha256"]:
            raise Refused(f"snapshot of {ref['path']} does not match the hash "
                          "recorded for it; refusing to freeze a cycle whose "
                          "preserved copy already disagrees with its own record")

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


# ---------------------------------------------------------------- findings

# The parser and the canonical Finding ID grammar live in one module, imported
# by this runner and by the MC-2 checker. Two implementations of a format is how
# the prompt, the ledger and the parser ended up each enforcing their own.
import findings_format

CLASSES = findings_format.CLASSES


def canonical_id_grammar():
    return findings_format.canonical_id_grammar()


def extract_findings(raw: str) -> tuple[list[dict], list[str]]:
    # A missing or unreadable schema is a refusal, not a traceback: the parser
    # cannot know the canonical grammar, so it cannot say anything about the
    # review, and saying nothing must not look like finding nothing.
    try:
        return findings_format.extract(raw)
    except findings_format.FormatError as e:
        raise Refused(str(e))


# ---------------------------------------------------------------- capture
#
# Alex Zamurko, 9 September 2026, issue 6. Before this, `record` refused if a
# capture already existed, so a failed capture killed the cycle. In practice
# that meant deleting evidence: the reply reached the file on the fourth
# attempt, two earlier attempts held seventy bytes of shell command and passed
# MC-2, and a better capture sat unnoticed in another directory. Nothing said
# which of them governed.
#
#     Use the rule that the first capture satisfying the predefined
#     capture-validity requirements becomes authoritative. Any replacement
#     requires explicit invalidation and preservation of both attempts.
#
# So attempts are numbered, all are kept, and one is designated. Nothing is
# deleted to tidy up, which is what happened three times in one afternoon.

CAPTURE_SCHEMA = "cycle-capture/1"


def capture_validity(raw_text: str, target_hash: str,
                     zero_asserted: bool) -> list[str]:
    """The predefined requirements. Empty list means this capture is valid.

    Fixed in advance rather than judged per case, because the point of a
    designation rule is that it does not depend on who is looking.
    """
    problems: list[str] = []
    if not raw_text.strip():
        problems.append("empty")
    if target_hash not in raw_text:
        problems.append(
            f"does not quote the target hash {target_hash[:16]}…; the review "
            "prompt requires the reviewer to, and without it this is not "
            "demonstrably a capture of this target")
    found, parse_problems = extract_findings(raw_text)
    problems += parse_problems
    if not found and not parse_problems and not zero_asserted:
        problems.append("no finding blocks, and zero was not asserted; pass "
                        "--zero-findings if the reviewer genuinely reported "
                        "none, since absence must never be read as zero")
    return problems


def next_attempt(cycle: Path) -> int:
    d = cycle / "captures"
    if not d.is_dir():
        return 1
    used = [int(m.group(1)) for p in d.iterdir()
            if (m := re.fullmatch(r"attempt-(\d{2})", p.name))]
    return max(used) + 1 if used else 1


def load_capture_log(cycle: Path) -> dict:
    p = cycle / "capture-log.json"
    if not p.is_file():
        return {"schema": CAPTURE_SCHEMA, "authoritative": None, "attempts": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"capture-log.json is not valid JSON: {e}")


def cmd_record(args: argparse.Namespace) -> int:
    if args.invocation not in INVOCATIONS:
        raise Refused(f"--invocation must be one of {INVOCATIONS}")

    cycle = Path(args.cycle).resolve()
    if not (cycle / "target.json").is_file():
        raise Refused(f"not a frozen cycle directory: {cycle}")

    log = load_capture_log(cycle)
    if log.get("authoritative") and not args.supersede_capture:
        raise Refused(
            f"attempt-{log['authoritative']:02d} is already the authoritative "
            "capture for this cycle.\n"
            "  The first capture meeting the validity requirements governs, and "
            "later ones do\n  not displace it silently. Replacing it takes both "
            "--supersede-capture with\n  --reason, and an approval recorded by "
            "someone other than the implementing\n  agent. Both captures are "
            "kept either way; only the designation would move.")
    if args.supersede_capture and not log.get("authoritative"):
        raise Refused("--supersede-capture passed but no authoritative capture "
                      "exists to supersede")
    if args.supersede_capture and not (args.reason or "").strip():
        raise Refused(
            "--supersede-capture requires --reason.\n"
            "  Replacing the capture that governs a review is a decision, and "
            "the record has\n  to say why it was made rather than leaving a "
            "silent substitution.")

    src = require_file(Path(args.output).resolve(), "reviewer output")
    body = src.read_text(encoding="utf-8", errors="replace")
    raw = cycle / "codex-output-raw.md"

    # Alex Zamurko, ruling 3, 9 September 2026: supersession needs "an authority
    # outside the implementer plus an auditable reason". --reason was neither. It
    # is a string I type, in a command I run, so the party the control constrains
    # was operating the control. Preserving every attempt does not help if the
    # same party still picks which one governs.
    #
    # Checked here, after the replacement's bytes are known and before anything
    # on disk moves, because the approval has to bind to those exact bytes.
    if args.supersede_capture:
        approval_path = cycle / "capture-supersession-approval.json"
        try:
            approval = authority.require_approval(
                approval_path, "capture-supersession",
                {"cycle": cycle.name,
                 "superseded_sha256": log["authoritative_sha256"],
                 "superseding_sha256": sha256_bytes(src.read_bytes())})
        except authority.NotAuthorized as e:
            raise Refused(f"supersession is not authorized.\n\n{e}")
        args._approval = approval

    # ---- preserve this attempt, whatever comes of it ----
    # Written before validity is judged, so a failed capture leaves a record
    # rather than nothing. Three attempts vanished today because the only way to
    # retry was to delete what was there.
    target_hash = (cycle / "target.sha256").read_text(encoding="utf-8").strip()
    n = next_attempt(cycle)
    adir = cycle / "captures" / f"attempt-{n:02d}"
    adir.mkdir(parents=True)
    (adir / "raw.md").write_bytes(src.read_bytes())

    invalid = capture_validity(body, target_hash, bool(args.zero_findings))
    entry = {
        "attempt": n,
        "recorded_at": now(),
        "source": str(src),
        "invocation": args.invocation,
        "note": args.note or "",
        "sha256": sha256_file(adir / "raw.md"),
        "bytes": (adir / "raw.md").stat().st_size,
        "valid": not invalid,
        "problems": invalid,
        "retry_reason": args.reason or "",
    }
    write_lf(adir / "capture.json", json.dumps(entry, indent=2) + "\n")
    log["attempts"].append(entry)

    if invalid:
        if args.supersede_capture:
            log["attempts"][-1]["superseded_nothing"] = True
        write_lf(cycle / "capture-log.json", json.dumps(log, indent=2) + "\n")
        raise Refused(
            f"attempt-{n:02d} does not meet the capture validity requirements:\n  "
            + "\n  ".join(invalid) +
            f"\n\n  The attempt is preserved at {rel(adir)} and recorded in "
            "capture-log.json.\n  Nothing was designated authoritative and the "
            "cycle is unchanged. Retry with a\n  better capture; failed attempts "
            "are kept rather than deleted.")

    if args.supersede_capture:
        prior = log["authoritative"]
        approval = getattr(args, "_approval", {})
        log.setdefault("invalidated", []).append({
            "attempt": prior,
            "invalidated_at": now(),
            "reason": args.reason,
            "superseded_by": n,
            # The authority is recorded alongside the act, not only in the
            # approval file, so removing that file later does not leave a
            # supersession in the log with nobody's name on it.
            "authorized_by": approval.get("authorized_by", ""),
            "authority_reason": approval.get("reason", ""),
            "authorized_at": approval.get("at", ""),
        })
        # The prior attempt stays on disk. Only the designation moves.
        raw.unlink(missing_ok=True)
        (cycle / "findings.json").unlink(missing_ok=True)

    log["authoritative"] = n
    log["authoritative_sha256"] = entry["sha256"]

    # ---- authoritative findings, extracted before anything is written ----
    # Alex Zamurko, 9 September 2026, issue 4:
    #
    #     Runner creates findings.json for every completed review. Explicitly
    #     represent zero findings; absence must never mean zero. Implementing
    #     agent must not manually create or overwrite authoritative findings.
    #
    # Extraction happens here rather than being left to whoever is present,
    # because the failure this closes is real findings never reaching the ledger
    # and the controller reading that silence as a clean review.
    found, problems = extract_findings(body)
    if problems:
        raise Refused(
            "the reviewer output does not parse as review evidence:\n  "
            + "\n  ".join(problems) +
            "\n\n  Nothing has been written. The raw output is captured only "
            "alongside an\n  authoritative findings record, so a cycle cannot "
            "exist with evidence nobody\n  could read.")

    # Zero has to be asserted, never inferred. "No blocks found" is equally
    # consistent with a clean review and with a capture that went wrong — which
    # happened four times before this cycle was recorded — so the operator
    # states which, and the record says a human said so.
    if not found and not args.zero_findings:
        raise Refused(
            "no finding blocks found in the reviewer output.\n"
            "  That is either a clean review or a capture that went wrong, and "
            "the two are\n  indistinguishable from here. If the reviewer "
            "genuinely reported none, pass\n  --zero-findings to assert it. "
            "Absence is not permitted to mean zero.")
    if found and args.zero_findings:
        raise Refused(
            f"--zero-findings was passed but {len(found)} finding block(s) are "
            "present:\n  " + ", ".join(f["id"] for f in found) +
            "\n  Nothing written.")

    # Bytes, not text. Whatever the reviewer returned is what gets stored.
    raw.write_bytes(src.read_bytes())

    write_lf(cycle / "findings.json", json.dumps({
        "schema": "cycle-findings/1",
        # Requirement 2: a review that cannot be parsed deterministically is
        # INVALID, and INVALID is not zero. Nothing reaches this line unless the
        # parse was clean, so the field is VALID here by construction — it is
        # recorded so a reader of the evidence sees the status rather than
        # inferring it from the file's existence.
        "review_result_status": "VALID",
        "raw_finding_count": len(found),
        "finding_id_grammar": canonical_id_grammar().pattern,
        "cycle": json.loads((cycle / "target.json").read_text(encoding="utf-8"))
                     .get("cycle"),
        "extracted_at": now(),
        # Binds this record to the exact capture it was read out of, so a later
        # recapture cannot leave a findings file describing different bytes.
        "source": f"captures/attempt-{n:02d}/raw.md",
        "source_attempt": n,
        "source_sha256": sha256_file(raw),
        "count": len(found),
        "zero_findings_asserted": bool(args.zero_findings),
        "findings": found,
    }, indent=2) + "\n")

    write_lf(cycle / "capture-log.json", json.dumps(log, indent=2) + "\n")

    write_lf(cycle / "invocation.json", json.dumps({
        "authoritative_attempt": n,
        "authoritative_sha256": entry["sha256"],
        "attempts_recorded": len(log["attempts"]),
        "invocation": args.invocation,
        "recorded_at": now(),
        "source": str(src),
        "note": args.note or "",
        "unproven": "This file records how the review was invoked. It does not "
                    "establish that codex-output-raw.md came from codex-input.md.",
    }, indent=2) + "\n")

    print(f"recorded {rel(raw)}  ({raw.stat().st_size} bytes, invocation={args.invocation})")
    if found:
        print(f"  findings.json  {len(found)} finding(s): "
              + ", ".join(f["id"] for f in found))
    else:
        print("  findings.json  zero findings, explicitly asserted")
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
    r.add_argument("--supersede-capture", dest="supersede_capture",
                   action="store_true",
                   help="replace the authoritative capture. Requires --reason "
                        "AND an approval record from outside the implementing "
                        "agent at <cycle>/capture-supersession-approval.json, "
                        "bound by hash to both captures. Both attempts are "
                        "preserved; only the designation moves.")
    r.add_argument("--reason", default="",
                   help="why the current authoritative capture is being "
                        "invalidated, or why this attempt was retried.")
    r.add_argument("--zero-findings", dest="zero_findings", action="store_true",
                   help="assert that the reviewer reported no findings. "
                        "Required when the output contains no finding blocks: "
                        "absence must never be read as zero.")
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

`sha256 43a842cd5f5aea26bf8ba8964640b906d18be9e866c2045aee035dd3a8bf4f88`

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

Invalid cycles do not authorize and do not block
------------------------------------------------
B01-F11. Transition authority is computed through `cycle_projection`, the same
module the loop controller uses, rather than from the stored state. An event
recorded in a cycle that fails MC-2 stays in the history as evidence and is
printed by `show`, but it cannot satisfy a precondition and it cannot stand in
the way of a valid transition. Before this, an ACCEPT in an invalid cycle could
authorize a closure and a DEMONSTRATED in an invalid cycle could prevent one
forever.

The stored `state` field is a cache of that projection, rewritten on every
command. Nothing reads it to decide anything.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycle_projection  # noqa: E402

# An optional single-letter prefix, then the cycle, then the finding number.
# §4's example is C02-F03; the bootstrap review used B01-F01 because the prompt
# said so. Identifiers are the reviewer's and are persistent (V40), so the
# ledger records what was issued rather than renaming it — renaming a finding
# during transcription is exactly what B01-F13 is about. The digits still have
# to match the cycle, which is the part that carries meaning.
FINDING_ID = re.compile(r"\A[A-Z]?(\d{2})-F(\d{2,3})\Z")

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
    """State history, deliberately not called findings.json.

    Alex Zamurko, issue 4: "Separate authoritative findings from response/state
    history." They were both findings.json, at different levels — the schema
    documented a per-cycle file written by the runner, and this wrote a
    review-level one. Two files with one name is how a reader ends up believing
    the wrong one is authoritative.

    cycle-NN/findings.json  what the reviewer found, written by the runner
    ledger.json             what happened to each finding since, written here
    """
    return review / "ledger.json"


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
        raise Refused(f"finding id must look like C02-F03 or B01-F01, "
                      f"got {fid!r}")
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
    """Unfiltered. Kept for reporting; never for authority. See `authorized`."""
    for e in reversed(f["history"]):
        if e["event"] == event:
            return e
    return None


# ------------------------------------------------- the projection (B01-F11)

def projection(review: Path) -> cycle_projection.Projection:
    return cycle_projection.project(review)


def effective_state(f: dict, proj: cycle_projection.Projection) -> str:
    """The state this finding is actually in, ignoring events without authority.

    This replaces every former read of f["state"]. The difference only shows up
    once a cycle has been judged and failed, which is precisely the case B01-F11
    is about.
    """
    return cycle_projection.replay(f["history"], proj) or OPEN


def authorized(f: dict, event: str,
               proj: cycle_projection.Projection) -> dict | None:
    return cycle_projection.last_authorized(f["history"], event, proj)


def note_ignored(f: dict, proj: cycle_projection.Projection) -> str:
    """A line naming the events being disregarded, so a refusal is legible.

    Without this, a resolve that is refused for want of an ACCEPT looks wrong to
    an operator who can see an ACCEPT sitting in the history.
    """
    ignored = [f"cycle {e['cycle']:02d} {e['event']}"
               for e in f["history"] if not proj.authorizes(e["cycle"])]
    if not ignored:
        return ""
    return ("\n  Disregarded, recorded in a cycle that fails MC-2: "
            + "; ".join(ignored)
            + "\n  They remain in the history as evidence. Repair the cycle's "
            "evidence and they\n  count again.")


def restate(f: dict, proj: cycle_projection.Projection) -> None:
    f["state"] = effective_state(f, proj)


# ---------------------------------------------------------------- commands

def cmd_raise(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    check_id(a.id, a.cycle)
    if a.id in data["findings"]:
        # B01-F13. The refusal is right; its guidance was not. Telling the
        # operator to create a new finding for a recurrence contradicts V40 and
        # defeats §6's re-raise detection, which needs the identity to persist.
        # Issue 7 gave the recurrence its own transition, so this now points at
        # it instead of instructing a rename.
        raise Refused(
            f"{a.id} already exists, and identifiers are persistent (V40).\n"
            f"  If this is the same underlying finding recurring after it was "
            "resolved, use\n  `reopen`, which keeps the identifier and moves "
            "RESOLVED -> OPEN.\n"
            "  If it is genuinely a different finding, it needs its own "
            "identifier.")
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
    proj = projection(review)
    state = effective_state(f, proj)

    if state == RESOLVED:
        raise Refused(f"{a.id} is RESOLVED. Responding again is not how a "
                      "recurrence is recorded:\n  use `reopen` with evidence, "
                      "which keeps the identifier and moves\n  RESOLVED -> OPEN "
                      "per §7 of the 9 September ruling.")
    if state == DISPUTED:
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
        f["history"].append({"cycle": a.cycle, "event": "REJECT_WITH_REASON",
                             "state": DISPUTED, "at": now(), "note": a.note,
                             "spec_evidence": a.spec_evidence})
        print(f"{a.id}  REJECT_WITH_REASON  cycle {a.cycle:02d}  -> {DISPUTED}")
        print("       Requires human adjudication at the plan gate.")

    restate(f, proj)
    save(review, data)
    return 0


def cmd_reopen(a: argparse.Namespace) -> int:
    """RESOLVED -> OPEN when the same underlying finding recurs.

    Alex Zamurko, 9 September 2026, issue 7:

        If a previously RESOLVED finding is raised again as the same underlying
        finding, the persistent Finding ID is retained and its state transitions
        RESOLVED -> OPEN. The recurrence is recorded as a reopen event with
        cycle and evidence. No new authoritative finding state is introduced.

    Before this the ledger refused outright, which was wrong in both directions:
    a recurrence either had to be recorded under a new identifier, breaking V40
    and §6's re-raise detection, or not recorded at all. There is still no fourth
    state; the controller sees an ordinary member of OPEN_n.
    """
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)
    proj = projection(review)
    state = effective_state(f, proj)

    if state != RESOLVED:
        raise Refused(f"{a.id} is {state}, not RESOLVED. Reopening applies "
                      "only to a finding that was resolved and has recurred."
                      + note_ignored(f, proj))
    if not (a.evidence or "").strip():
        raise Refused(
            "--evidence is required. A reopen asserts that the same underlying "
            "finding is\n  present again, and the record has to say what shows "
            "it rather than leaving\n  the claim bare.")

    last = authorized(f, "DEMONSTRATED", proj)
    if last and a.cycle <= last["cycle"]:
        raise Refused(
            f"{a.id} was resolved in cycle {last['cycle']:02d} and cannot "
            f"recur in cycle {a.cycle:02d}.\n  A recurrence is observed in a "
            "later cycle than the resolution it undoes.")

    f["history"].append({"cycle": a.cycle, "event": "REOPENED", "state": OPEN,
                         "at": now(), "note": a.evidence,
                         "prior_state": RESOLVED})
    restate(f, proj)
    save(review, data)
    print(f"{a.id}  REOPENED  cycle {a.cycle:02d}  {RESOLVED} -> {OPEN}")
    print("       The identifier is retained; §6 counts it as an ordinary "
          "member of OPEN_n.")
    return 0


def cmd_resolve(a: argparse.Namespace) -> int:
    review = Path(a.review).resolve()
    data = load(review)
    f = get(data, a.id)
    proj = projection(review)
    state = effective_state(f, proj)

    if state == RESOLVED:
        raise Refused(f"{a.id} is already RESOLVED.")
    if state == DISPUTED:
        raise Refused(f"{a.id} is DISPUTED. A dispute is resolved by human "
                      "adjudication at the gate, not by demonstrating a repair.")

    acc = authorized(f, "ACCEPT", proj)
    if acc is None:
        raise Refused(f"{a.id} has no ACCEPT. §5 gives RESOLVED only to a finding "
                      "that was accepted and then repaired; a finding cannot become "
                      "resolved without first having been accepted."
                      + note_ignored(f, proj))
    if a.cycle <= acc["cycle"]:
        raise Refused(f"{a.id} was accepted in cycle {acc['cycle']:02d} and cannot be "
                      f"resolved in cycle {a.cycle:02d}. §5 requires the repair to be "
                      "demonstrated in the NEXT review target, so resolution belongs "
                      "to a later cycle than the acceptance.")
    if not (a.evidence or "").strip():
        raise Refused("--evidence is required. The protocol resolves a finding when "
                      "the repair is demonstrated; recording what demonstrates it is "
                      "the difference between a demonstration and an assertion.")

    f["history"].append({"cycle": a.cycle, "event": "DEMONSTRATED", "state": RESOLVED,
                         "at": now(), "note": a.evidence})
    restate(f, proj)
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


def snapshot(data: dict, cycle: int,
             proj: cycle_projection.Projection | None = None) -> dict[str, set[str]]:
    """Per-cycle view. Also projected, or `show --cycle` would contradict `show`."""
    out = {OPEN: set(), RESOLVED: set(), DISPUTED: set()}
    for fid, f in data["findings"].items():
        if proj is None:
            s = state_after(f, cycle)
        else:
            s = cycle_projection.replay(
                f["history"], proj,
                upto={e["cycle"] for e in f["history"] if e["cycle"] <= cycle})
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
        snap = snapshot(data, a.cycle, projection(review))
        print(f"state after cycle {a.cycle:02d}")
        for s in STATES:
            ids = sorted(snap[s])
            print(f"  {s:<9} {len(ids):>2}  {', '.join(ids) if ids else '-'}")
        return 0

    proj = projection(review)
    print(f"findings ledger — {review}")
    if proj.invalid:
        print("  cycles failing MC-2, whose events are evidence only: "
              + ", ".join(f"{c:02d}" for c in sorted(proj.invalid)))
    for fid in sorted(data["findings"]):
        f = data["findings"][fid]
        print(f"\n  {fid}  [{effective_state(f, proj)}]  {f['class']}"
              + (f"  ({f['requirement_id']})" if f["requirement_id"] else ""))
        for e in f["history"]:
            note = f"  {e['note'][:60]}" if e.get("note") else ""
            mark = "" if proj.authorizes(e["cycle"]) else "  [no authority]"
            print(f"      cycle {e['cycle']:02d}  {e['event']:<18} -> "
                  f"{e['state']}{mark}{note}")
    print()
    counts = {s: 0 for s in STATES}
    for f in data["findings"].values():
        counts[effective_state(f, proj)] += 1
    for s in STATES:
        print(f"  {s:<9} {counts[s]}")
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

    o = sub.add_parser("reopen", help="record that a RESOLVED finding recurred")
    common(o)
    o.add_argument("--cycle", type=int, required=True)
    o.add_argument("--id", required=True)
    o.add_argument("--evidence", default="",
                   help="what shows the same underlying finding is present again")
    o.set_defaults(fn=cmd_reopen)

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

`sha256 d99ea037d55acb074a669a1f888f7ec1caa469c71453057bc81759ca5371d650`

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cycle_projection  # noqa: E402

VALIDATOR = REPO / "scripts" / "validate_cycle.py"
MAX_VALID_CYCLES = 4
TERMINAL = ("CONVERGED", "HUMAN_ADJUDICATION_REQUIRED", "STALLED",
            "MAX_4_REACHED")

OPEN, RESOLVED, DISPUTED = "OPEN", "RESOLVED", "DISPUTED"

# B01-F11: both live in cycle_projection now, so the ledger and this controller
# cannot drift apart about which cycles count.
cycle_dirs = cycle_projection.cycle_dirs
gate = cycle_projection.gate


class CannotCalculate(Exception):
    """Loop state is not determinable from the evidence present. Exit 2."""


def load_ledger(review: Path) -> dict:
    """State history. Absent means no findings have been responded to yet.

    Distinct from the per-cycle authoritative findings, which are checked
    separately below and whose absence is a refusal rather than a zero.
    """
    p = review / "ledger.json"
    if not p.is_file():
        return {"findings": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"ledger.json is not valid JSON: {e}")


def authoritative_findings(cycle_dir: Path) -> list[str]:
    """The finding IDs the runner extracted for this cycle.

    Alex Zamurko, issue 4: "Controller refuses to calculate loop state if
    findings.json is missing or invalid."

    Absence used to mean zero. That is the path by which a review full of
    findings produces CONVERGED: nobody transcribes them, the ledger is empty,
    and empty reads as clean. So a valid cycle without an authoritative findings
    record is not a cycle with no findings; it is a cycle whose result nobody
    can determine, and the controller says so rather than guessing.
    """
    # Requirements 3 and 4: the structured result must still account for the
    # raw review, and identifiers must be unchanged along the whole chain
    #
    #     codex-output-raw.md -> findings.json -> ledger.json
    #
    # Checked here rather than only at record time, because findings.json is an
    # ordinary file afterwards. A finding quietly dropped from it, or renamed,
    # would otherwise never be noticed again.
    raw = cycle_dir / "codex-output-raw.md"
    p = cycle_dir / "findings.json"

    # Issue 6: "controller reads only the designated authoritative capture."
    # codex-output-raw.md is written from that attempt, so the two must agree.
    # If they do not, someone edited the working copy after the designation, and
    # the loop would be measuring a review nobody designated.
    clog = cycle_dir / "capture-log.json"
    if clog.is_file() and raw.is_file():
        try:
            cl = json.loads(clog.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CannotCalculate(f"{cycle_dir.name}/capture-log.json is not "
                                  f"valid JSON: {e}")
        chosen = cl.get("authoritative")
        if chosen is None:
            raise CannotCalculate(
                f"{cycle_dir.name} has capture attempts but none is designated "
                "authoritative.\n  Every attempt failed the validity "
                "requirements, so there is no review to evaluate.")
        import hashlib
        actual = hashlib.sha256(raw.read_bytes()).hexdigest()
        if actual != cl.get("authoritative_sha256"):
            raise CannotCalculate(
                f"{cycle_dir.name}: codex-output-raw.md does not match "
                f"attempt-{chosen:02d}, the designated authoritative capture.\n"
                f"  designated  {cl.get('authoritative_sha256')}\n"
                f"  on disk     {actual}\n"
                "  The loop must read the designated capture and nothing else.")

    if raw.is_file() and p.is_file():
        try:
            import findings_format
            parsed, problems = findings_format.extract(
                raw.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review cannot be reparsed, so the "
                f"structured result cannot be checked against it: {e}")
        if problems:
            raise CannotCalculate(
                f"{cycle_dir.name}: the raw review no longer parses "
                "deterministically:\n  " + "\n  ".join(problems))
        try:
            structured = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CannotCalculate(f"{cycle_dir.name}/findings.json is not valid "
                                  f"JSON: {e}")
        raw_ids = [f["id"] for f in parsed]
        got_ids = [f.get("id") for f in structured.get("findings", [])]
        if raw_ids != got_ids:
            raise CannotCalculate(
                f"{cycle_dir.name}: findings.json does not match the raw review "
                "it was extracted from.\n"
                f"  raw        {raw_ids}\n"
                f"  structured {got_ids}\n"
                "  A finding dropped or renamed here is a finding the loop will "
                "never see.")

    if not p.is_file():
        raise CannotCalculate(
            f"{p.parent.name} passed MC-2 but has no findings.json.\n"
            "  Absence is not zero. Either the runner did not record this cycle "
            "or the file\n  was removed; both make the loop state "
            "undeterminable. Re-record the cycle.")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"{p.parent.name}/findings.json is not valid "
                              f"JSON: {e}")
    if d.get("schema") != "cycle-findings/1":
        raise CannotCalculate(
            f"{p.parent.name}/findings.json declares schema "
            f"{d.get('schema')!r}, expected 'cycle-findings/1'")
    items = d.get("findings")
    if not isinstance(items, list) or "count" not in d:
        raise CannotCalculate(f"{p.parent.name}/findings.json is malformed: "
                              "needs a findings list and a count")
    if d["count"] != len(items):
        raise CannotCalculate(
            f"{p.parent.name}/findings.json says count={d['count']} but carries "
            f"{len(items)} findings")
    if not items and not d.get("zero_findings_asserted"):
        raise CannotCalculate(
            f"{p.parent.name}/findings.json records zero findings without "
            "zero_findings_asserted.\n  Zero has to be asserted, never inferred.")
    return [f["id"] for f in items if isinstance(f, dict) and "id" in f]


def state_after(f: dict, valid_upto: set[int]) -> str | None:
    """State as at the end of the valid cycles in `valid_upto`.

    Events in cycles outside the set are skipped, per consequence 2 above. The
    replay itself lives in cycle_projection so the ledger applies the identical
    rule when it decides whether a transition is permitted (B01-F11).
    """
    allow_all = cycle_projection.Projection([], {})
    return cycle_projection.replay(f["history"], allow_all, upto=valid_upto)


def load_authorizations(review: Path) -> list[dict]:
    """Recorded human authorizations to run another loop past a terminal exit.

    B01-F02's correction: "Refuse further automated cycles after that outcome
    unless an explicitly recorded human transition authorizes another loop."

    An authorization has to name both the boundary and the outcome it clears. A
    blanket "keep going" would restore the defect under a different spelling: it
    would let any later cycle override any earlier mandatory termination, which
    is the finding.
    """
    p = review / "loop-authorizations.json"
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CannotCalculate(f"loop-authorizations.json is not valid JSON: {e}")
    if d.get("schema") != "loop-authorization/1":
        raise CannotCalculate(
            f"loop-authorizations.json declares schema {d.get('schema')!r}, "
            "expected 'loop-authorization/1'")
    items = d.get("authorizations")
    if not isinstance(items, list):
        raise CannotCalculate("loop-authorizations.json has no authorizations list")
    for i, a in enumerate(items):
        missing = [k for k in ("after_valid_cycle", "outcome", "authorized_by",
                               "reason") if not str(a.get(k, "")).strip()]
        if missing:
            raise CannotCalculate(
                f"authorization {i} is missing {', '.join(missing)}.\n"
                "  An authorization to continue past a mandatory exit has to say "
                "which exit,\n  at which boundary, on whose authority, and why. "
                "Any of those blank and it\n  is not a recorded human transition, "
                "it is a switch the loop turned off for itself.")
    return items


def cleared_by(auths: list[dict], n: int, outcome: str) -> dict | None:
    for a in auths:
        if a.get("after_valid_cycle") == n and a.get("outcome") == outcome:
            return a
    return None


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
    try:
        return _run(a)
    except CannotCalculate as e:
        print(f"CANNOT CALCULATE LOOP STATE: {e}", file=sys.stderr)
        print()
        print("No LOOP_STATUS is emitted. An undeterminable state is not "
              "CONTINUE, and it is\nnot CONVERGED; treating it as either is the "
              "failure this refusal exists to stop.", file=sys.stderr)
        return 2


def _run(a) -> int:
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

    # Every valid cycle must carry an authoritative findings record, and the
    # ledger must account for everything in it. Without this the controller
    # measures only what someone remembered to transcribe, and silence reads as
    # a clean review.
    ledger = load_ledger(review)
    lines += ["", "authoritative findings"]
    unaccounted: list[str] = []
    for num, d in dirs:
        if num not in valid:
            continue
        ids = authoritative_findings(d)
        missing = [i for i in ids if i not in ledger["findings"]]
        lines.append(f"  cycle-{num:02d}  {len(ids)} finding(s)"
                     + (f": {', '.join(ids)}" if ids else ", explicitly zero"))
        unaccounted += [f"cycle-{num:02d}: {i}" for i in missing]
    if unaccounted:
        raise CannotCalculate(
            "findings the reviewer recorded are absent from the ledger:\n  "
            + "\n  ".join(unaccounted) +
            "\n\n  The loop state would be computed over a smaller finding set "
            "than the review\n  produced, which is how a review full of findings "
            "reaches CONVERGED.")
    lines.append("  every recorded finding is accounted for in the ledger")

    # B01-F02. Every valid cycle boundary is evaluated in order, and the first
    # terminal outcome governs. Evaluating only the latest boundary let a later
    # cycle overwrite an earlier mandatory exit: one finding accepted in cycle
    # 01, untouched in 02 and resolved in 03 reported CONVERGED, even though
    # cycle 02 had already required STALLED and the loop should never have
    # reached 03.
    auths = load_authorizations(review)
    governing = None          # (n, status, detail, cur)
    overridden: list[str] = []
    lines += ["", "boundaries, in order"]

    for n in range(1, len(valid) + 1):
        cur, prev, resolved_new, disputed_new = sets_at_boundary(ledger, valid, n)
        status, detail, shown = decide(cur, prev, resolved_new, disputed_new, n)
        lines.append(f"  n={n} (cycle-{valid[n-1]:02d})  OPEN {len(cur[OPEN])}  "
                     f"DISPUTED {len(cur[DISPUTED])}  RESOLVED {len(cur[RESOLVED])}"
                     f"   -> {status}")
        if status == "CONTINUE":
            continue
        auth = cleared_by(auths, n, status)
        if auth is None:
            governing = (n, status, detail, cur, shown)
            break
        lines.append(f"        {status} at n={n} cleared by recorded "
                     f"authorization: {auth['authorized_by']}")
        lines.append(f"        reason: {auth['reason']}")
        overridden.append(f"n={n} {status} (authorized by {auth['authorized_by']})")

    n_latest = len(valid)
    if governing is None:
        cur, prev, resolved_new, disputed_new = sets_at_boundary(
            ledger, valid, n_latest)
        status, detail, shown = decide(cur, prev, resolved_new, disputed_new,
                                       n_latest)
        governing = (n_latest, status, detail, cur, shown)

    n, status, detail, cur, shown = governing

    def fmt(ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "-"

    lines += ["", f"§6 sets and exits at the governing boundary, n={n}"] + shown

    if status == "CONTINUE":
        detail = (f"Repair the plan, produce a new version, and open cycle "
                  f"{dirs[-1][0] + 1:02d} with a new frozen target.")

    lines += ["", f"LOOP_STATUS: {status}", detail]

    # The cycles that should never have been opened. Reported rather than
    # silently absorbed, because the evidence in them was produced under a loop
    # that had already terminated and no one authorized restarting it.
    if status in TERMINAL and n < n_latest:
        after = [f"cycle-{c:02d}" for c in valid[n:]]
        lines += ["",
                  f"UNAUTHORIZED CONTINUATION: the loop reached {status} at n={n} "
                  f"(cycle-{valid[n-1]:02d}).",
                  f"  {len(after)} further valid cycle(s) were run after it: "
                  + ", ".join(after),
                  "  §6's exits are mandatory, so the first one governs and the "
                  "later cycles do",
                  "  not override it. Record a human authorization in "
                  "loop-authorizations.json if",
                  "  another loop was genuinely approved, or take the outcome "
                  "above to the gate."]
    if overridden:
        lines += ["", "Earlier terminal outcomes cleared by recorded "
                  "authorization: " + "; ".join(overridden)]

    if status != "CONTINUE" and cur[DISPUTED]:
        lines.append("")
        lines.append(f"Disputes for adjudication ({len(cur[DISPUTED])}): "
                     f"{fmt(cur[DISPUTED])}")
        lines.append("§7 requires disputes and unresolved findings to reach the human "
                     "as separate lists.")

    print(f"LOOP_STATUS: {status}" if a.quiet else "\n".join(lines))
    return 0


def sets_at_boundary(ledger: dict, valid: list[int], n: int):
    """The §6 sets as at valid cycle boundary n, plus the _NEW_n deltas."""
    upto_n = set(valid[:n])
    cur = sets_at(ledger, upto_n)
    prev = sets_at(ledger, set(valid[:n - 1])) if n > 1 else None
    resolved_new: set[str] = set()
    disputed_new: set[str] = set()
    if prev is not None:
        for fid in prev[OPEN]:
            s = state_after(ledger["findings"][fid], upto_n)
            if s == RESOLVED:
                resolved_new.add(fid)
            elif s == DISPUTED:
                disputed_new.add(fid)
    return cur, prev, resolved_new, disputed_new


def decide(cur, prev, resolved_new: set[str], disputed_new: set[str],
           n: int) -> tuple[str, str, list[str]]:
    """The §6 exit test at one boundary.

    Exits are tested in the protocol's order, and the order is load-bearing.
    HUMAN_ADJUDICATION_REQUIRED sits between CONVERGED and STALLED because a loop
    with nothing open and a dispute outstanding is not stalled: it finished
    everything automation can do. Test STALLED first and it swallows the case a
    cycle later, which is what v1.0 did.
    """
    def fmt(ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "-"

    shown = [
        f"  OPEN_{n}          {len(cur[OPEN]):>2}  {fmt(cur[OPEN])}",
        f"  DISPUTED_{n}      {len(cur[DISPUTED]):>2}  {fmt(cur[DISPUTED])}",
        f"  RESOLVED_{n}      {len(cur[RESOLVED]):>2}  {fmt(cur[RESOLVED])}",
    ]
    if prev is not None:
        shown += [
            f"  OPEN_{n-1}          {len(prev[OPEN]):>2}  {fmt(prev[OPEN])}",
            f"  RESOLVED_NEW_{n}  {len(resolved_new):>2}  {fmt(resolved_new)}",
            f"  DISPUTED_NEW_{n}  {len(disputed_new):>2}  {fmt(disputed_new)}",
        ]

    if not cur[OPEN] and not cur[DISPUTED]:
        shown.append(f"  A CONVERGED                    OPEN_{n} = 0 and "
                     f"DISPUTED_{n} = 0        yes")
        return ("CONVERGED",
                "Nothing open and nothing disputed. Proceed to human plan review.",
                shown)

    if not cur[OPEN] and cur[DISPUTED]:
        shown.append(f"  B HUMAN_ADJUDICATION_REQUIRED  OPEN_{n} = 0 and "
                     f"DISPUTED_{n} != 0     yes")
        return ("HUMAN_ADJUDICATION_REQUIRED",
                "Everything actionable is resolved or disputed, and no further "
                "automated repair is available. Stop now rather than spending a "
                "cycle on a plan with nothing open to repair. Proceed to human "
                "plan review.", shown)

    if prev is None:
        shown.append("  C STALLED                      not testable at n=1 "
                     "(§6 requires n > 1)")
    else:
        stalled = (len(cur[OPEN]) >= len(prev[OPEN])
                   and not resolved_new and not disputed_new)
        shown.append(
            f"  C STALLED                      |OPEN_{n}| >= |OPEN_{n-1}|"
            f" ({len(cur[OPEN])} >= {len(prev[OPEN])})"
            f" and no new resolved/disputed   {'yes' if stalled else 'no'}")
        if stalled:
            return ("STALLED",
                    "The last valid cycle reduced nothing, resolved nothing and "
                    "disputed nothing. Stop now rather than spending the "
                    "remaining budget. Proceed to human plan review.", shown)

    maxed = n >= MAX_VALID_CYCLES
    shown.append(f"  D MAX_4_REACHED                VALID_CYCLE_COUNT = {n}"
                 f"                  {'yes' if maxed else 'no'}")
    if maxed:
        return ("MAX_4_REACHED",
                "Budget exhausted with findings still open. Proceed to human "
                "plan review with the unresolved matters exposed.", shown)

    return ("CONTINUE", "", shown)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/bootstrap_gate.py`

`sha256 9bb99992c26141f80cc4c68c2210813c74fe38cf844d957ce07fef118b2aba5c`

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
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REVIEW_DIR = REPO / "bootstrap-review"
RECORD = REVIEW_DIR / "decision.json"

# Alex Zamurko, 9 September 2026, rulings 1 and 2:
#
#     Cycle 02 remains inside the bootstrap exception; start the ACTIVE/CANDIDATE
#     chain only after the first human approval ... The bootstrap exception ends
#     immediately after the first human approval of a runner ... without a precise
#     termination point, "bootstrap" can become an indefinite exemption.
#
# So the exception is not a period someone declares over. It ends when the first
# runner approval exists, and that is a fact on disk rather than a judgement.
RUNNER_APPROVAL_DIR = "runner-approvals"

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
# The evidence schema is here because of B01-F10: the frozen review target
# carried six artifacts and the covered set held five. Codex was reviewing the
# schema, and editing it afterwards did not invalidate its own approval.
#
# It is not a script, and it implements no code, but MC-2 checks evidence
# against it. A gate that covers the checker and not the document the checker
# reads its expectations from has a seam running straight through the middle of
# what it claims to cover.
COMPONENTS = (
    "specs/evidence-schema-v1.0.md",
    "scripts/validate_cycle.py",
    "scripts/run_review.py",
    "scripts/ledger.py",
    "scripts/loop_state.py",
)

# This file is always covered, whatever the roots are. It was not, which is the
# hole Alex found on 9 September.
#
# What that fixes, precisely, and what it does not. Covering this file means a
# later edit to it is DETECTED, by a subsequent run of the unedited code. It does
# not mean the edit is prevented, and it does not survive an edit that also
# disables the detection: replacing `evaluate` with an unconditional success
# defeats the self-hash along with everything else, because the same writable
# code performs both.
#
# An earlier comment here claimed self-hashing closed that hole. Codex raised it
# as B01-F15 and was right. Under CONVENTION_ONLY this is drift detection that
# holds when the checks run faithfully, and nothing stronger. The stronger claim
# needs a write boundary the implementing agent does not hold, which is what
# MC1_ENFORCEMENT: TECHNICALLY_ENFORCED would record.
ALWAYS = ("scripts/bootstrap_gate.py",)

# A filename mentioned as a string, which is how this repository loads modules
# dynamically: run_review.py builds a path to bootstrap_gate.py, and both
# run_review.py and loop_state.py invoke validate_cycle.py as a subprocess.
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


def references(path: Path) -> set[str]:
    """Every scripts/*.py this file could load, by either route.

    Two routes, because this repository uses both and an earlier version saw
    only one. Codex, B01-F16:

        Dependency discovery recognizes filename strings ending in `.py`.
        Ordinary `import helper_module` and `from helper_module import VALUE`
        are not recognized.

    That was correct, and the control that was supposed to demonstrate the
    closure inserted `_HELPER = "helper_module.py"` — a string. So it exercised
    the route that already worked and said nothing about the one that did not.
    A real local import sat outside the approval hash set.

    Imports are read from the parsed syntax tree rather than by regex, because a
    regex over source text cannot tell an import from the word "import" in a
    comment, and being wrong in that direction means covering files nothing
    actually loads.
    """
    text = path.read_text(encoding="utf-8")
    found = {f"scripts/{n}" for n in PY_REF.findall(text)}

    # The filename scan applies to every covered file; import analysis only to
    # Python. A covered file need not be code — the evidence schema is covered
    # because MC-2 reads its expectations from it — and ast.parse on markdown
    # raises rather than returning nothing.
    if path.suffix != ".py":
        return found

    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(f"scripts/{alias.name.split('.')[0]}.py")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # from . import x  /  from .x import y
                for alias in node.names:
                    found.add(f"scripts/{alias.name}.py")
                if node.module:
                    found.add(f"scripts/{node.module.split('.')[0]}.py")
            elif node.module:
                found.add(f"scripts/{node.module.split('.')[0]}.py")
    return found


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
        for dep in sorted(references(p)):
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


def target_artifacts(target_json: Path) -> dict[str, str]:
    """The path→sha256 map the review target froze, from its plan_files."""
    if not target_json.is_file():
        raise Refused(f"review target not found: {target_json}")
    try:
        t = json.loads(target_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise Refused(f"review target is not valid JSON: {e}")
    entries = t.get("plan_files") or []
    if not entries:
        raise Refused(f"{target_json} lists no plan_files, so there is nothing "
                      "to bind the decision to")
    return {e["path"]: e["sha256"] for e in entries
            if isinstance(e, dict) and "path" in e and "sha256" in e}


def target_drift(root: Path, target_json: Path) -> list[str]:
    """Where the covered set and the reviewed target disagree.

    Three ways they can, and each means the decision would be about something
    other than what was reviewed:

      - a covered file was edited after the freeze;
      - a covered file was never in the target, so nobody reviewed it;
      - the target carried an artifact the gate does not cover, so approving it
        commits to nothing.
    """
    frozen = target_artifacts(target_json)
    now = covered(root)
    out: list[str] = []

    for rel, digest in sorted(now.items()):
        if rel not in frozen:
            out.append(f"{rel} is covered but was not in the review target, so "
                       "no reviewer saw it")
        elif frozen[rel] != digest:
            out.append(f"{rel} changed after the freeze\n"
                       f"      reviewed  {frozen[rel]}\n"
                       f"      on disk   {digest}")

    for rel in sorted(set(frozen) - set(now)):
        out.append(f"{rel} was reviewed but is not in the covered set, so "
                   "approving it would bind nothing")
    return out


# ------------------------------------------------------------------ check

# -------------------------------------------------- the exception's end

def runner_approvals_on_disk(root: Path) -> list[Path]:
    d = root / RUNNER_APPROVAL_DIR
    return sorted(d.glob("*.json")) if d.is_dir() else []


def runner_approvals_in_history(root: Path) -> list[str]:
    """Runner approvals git has ever seen added, whether or not they exist now.

    This is what makes the termination one-way, and it is the part that took a
    second look. A gate that decides by listing a directory can be reopened by
    deleting the directory: the exception would end and then quietly resume, and
    nothing in the tree would show it had ever ended. "Bootstrap" becoming an
    indefinite exemption is the exact failure ruling 2 exists to prevent, and
    deletion is the easiest route to it.

    Git history is the cheapest available record that a delete does not reach. It
    is not tamper-proof; a history rewrite defeats it. But a rewrite is a loud,
    deliberate act that leaves the reflog and every clone disagreeing, where
    deleting a file is neither.

    The asymmetry that makes this sound under MC1_ENFORCEMENT: CONVENTION_ONLY is
    worth stating. Nothing stops the implementing agent from WRITING an approval,
    but writing one only ever makes the rules stricter: it ends its own
    exemption and subjects every later runner to review by a prior approved one.
    The direction that would benefit the implementing agent is removing one, and
    that is the direction this closes.
    """
    r = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--diff-filter=A",
         "--format=%H", "--name-only", "--", f"{RUNNER_APPROVAL_DIR}/"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return sorted({l.strip() for l in r.stdout.splitlines()
                   if l.strip().startswith(f"{RUNNER_APPROVAL_DIR}/")
                   and l.strip().endswith(".json")})


def bootstrap_exception_available(root: Path) -> tuple[bool, list[str]]:
    """(available, reasons). Ruling 2's termination point, asked as a question.

    Available means no runner has been approved yet, so there is still no prior
    approved runner that could serve as ACTIVE_REVIEW_RUNNER, and development
    evidence is the only kind obtainable. That is ruling 1's reasoning for
    cycle 02 and it stops being true the moment the first approval exists.
    """
    live = runner_approvals_on_disk(root)
    historic = runner_approvals_in_history(root)

    if live:
        return False, [
            "the bootstrap exception ended when the first runner was approved:",
            *[f"    {p.relative_to(root).as_posix()}" for p in live],
            "  From that approval onward every candidate runner is reviewed by "
            "the prior",
            "  approved one. There is no route back to the exception; it covered "
            "the period",
            "  before any approved runner existed, and that period is over.",
        ]

    if historic:
        return False, [
            "a runner approval was recorded and is no longer on disk:",
            *[f"    {h}" for h in historic],
            "  git history has it even though the working tree does not, so the "
            "exception is",
            "  still over. Ruling 2 ends it at the first approval, not at the "
            "most recent",
            "  surviving copy of the file.",
            "  Restore the approval record, or explain the deletion in a commit. "
            "A gate that",
            "  could be reopened by deleting a file would be a convention, not a "
            "termination.",
        ]

    return True, [
        "no runner has been approved yet, so the bootstrap exception is still "
        "available.",
        "  There is no prior approved runner to act as ACTIVE_REVIEW_RUNNER, "
        "which is the",
        "  condition the exception exists to cover. It ends at the first "
        "approval.",
    ]


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

    # B01-F09. The decision must be about the artifacts that were reviewed, not
    # about whatever is on disk when someone gets round to recording it.
    #
    # Codex: "Recording a decision checks only that four evidence files are
    # nonempty, then hashes the current component files. It never compares those
    # files with the frozen review target."
    #
    # So: approve, edit a component, record — and the approval covered code the
    # reviewer never saw, under evidence describing code that no longer exists.
    # `check` would then verify the decision against itself and pass forever.
    if a.target:
        drift = target_drift(REPO, Path(a.target).resolve())
        if drift:
            raise Refused(
                "the components have changed since the review target was "
                "frozen:\n  " + "\n  ".join(drift) +
                "\n\n  A decision recorded now would approve bytes the reviewer "
                "never saw.\n  Revert the drift, or re-freeze and re-review.")
    else:
        raise Refused(
            "--target is required: the frozen target.json the review was run "
            "against.\n"
            "  The decision has to be bound to what was reviewed. Without it "
            "this records\n  an approval of whatever happens to be on disk now, "
            "which is B01-F09.\n"
            "  Example:\n"
            "    --target runs/BOOTSTRAP-001/plan-review/cycle-01/target.json")

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
        "reviewed_target": {
            "path": Path(a.target).resolve().relative_to(REPO).as_posix(),
            "sha256": sha256_file(Path(a.target).resolve()),
        },
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


# ------------------------------------------------------- approve a runner

def cmd_approve_runner(a: argparse.Namespace) -> int:
    """Record the first human approval of a runner, which ends the exception.

    Ruling 2: "The first approved runner creates the missing first link in the
    chain; from that point onward, every candidate runner can and should be
    reviewed by the prior approved runner."

    Deliberately a separate command from `record`. The bootstrap decision
    approves the components as reviewed; this approves a specific runner to act
    as ACTIVE_REVIEW_RUNNER for the next candidate, and it is the event that ends
    the exemption. Folding them together would make ending the exception a side
    effect of approving code, and the two are different decisions taken at
    different moments.
    """
    if not a.decided_by.strip():
        raise Refused("--decided-by is required; the approval that ends the "
                      "exception cannot be anonymous")
    if len(a.note.strip()) < 20:
        raise Refused(
            "--note is required, and must attribute the decision.\n"
            "  Give where it was made and what was said: channel, timestamp, and "
            "the words.\n"
            "  This approval ends the bootstrap exception permanently, so the "
            "record has to\n  say who ended it and on what basis.")

    runner = Path(a.runner).resolve()
    if not runner.is_file():
        raise Refused(f"runner not found: {a.runner}")
    if not a.review:
        raise Refused(
            "--review is required: the review that approved this runner.\n"
            "  A runner approved by nothing is the thing the chain exists to "
            "rule out.")
    review = Path(a.review).resolve()
    if not review.is_file():
        raise Refused(f"review evidence not found: {a.review}")

    ok, reasons = evaluate(REPO)
    if not ok:
        raise Refused(
            "the bootstrap review does not currently hold, so no runner can be "
            "approved on\nthe strength of it:\n  " + "\n  ".join(reasons))

    available, _ = bootstrap_exception_available(REPO)
    d = REPO / RUNNER_APPROVAL_DIR
    d.mkdir(parents=True, exist_ok=True)
    rel_runner = runner.relative_to(REPO).as_posix()
    digest = sha256_file(runner)
    out = d / f"{digest[:12]}.json"
    if out.exists():
        raise Refused(f"this exact runner is already approved: "
                      f"{out.relative_to(REPO).as_posix()}")

    record = {
        "schema": "runner-approval/1",
        "runner_path": rel_runner,
        "runner_sha256": digest,
        "approved_by": a.decided_by.strip(),
        "approved_at": now(),
        "note": a.note,
        "review_evidence": {
            "path": review.relative_to(REPO).as_posix(),
            "sha256": sha256_file(review),
        },
        "components": component_hashes(REPO),
        "ends_bootstrap_exception": bool(available),
        "authority": "Alex Zamurko, 9 September 2026: the bootstrap exception "
                     "ends immediately after the first human approval of a "
                     "runner.",
    }
    write_lf(out, json.dumps(record, indent=2) + "\n")
    print(f"recorded {out.relative_to(REPO).as_posix()}")
    print(f"  runner      {rel_runner}  {digest[:16]}…")
    print(f"  approved by {record['approved_by']}")
    if available:
        print()
        print("The bootstrap exception ends here. --bootstrap-exempt will be "
              "refused from now on,")
        print("and every candidate runner is reviewed by the prior approved "
              "runner.")
        print()
        print("Commit this file. The termination is one-way, and git history is "
              "what makes it")
        print("one-way; an uncommitted approval can be undone by deleting it.")
    return 0


def cmd_exception(root: Path = REPO) -> int:
    available, why = bootstrap_exception_available(root)
    print("BOOTSTRAP_EXCEPTION: " + ("AVAILABLE" if available else "ENDED"))
    for line in why:
        print(f"  {line}")
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
    r.add_argument("--target", default="",
                   help="the frozen target.json the review was run against. "
                        "Required: it is what binds the decision to the "
                        "artifacts a reviewer actually saw.")
    r.add_argument("--supersede", action="store_true",
                   help="replace an existing decision, preserving it in the record")

    sub.add_parser("exception", help="is the bootstrap exception still available")

    ar = sub.add_parser("approve-runner",
                        help="record the first human approval of a runner, which "
                             "ends the bootstrap exception")
    ar.add_argument("--runner", required=True,
                    help="the runner being approved, e.g. scripts/run_review.py")
    ar.add_argument("--decided-by", required=True)
    ar.add_argument("--note", default="")
    ar.add_argument("--review", default="",
                    help="the review evidence this approval rests on, e.g. a "
                         "cycle's codex-output-raw.md")

    a = ap.parse_args(argv[1:])
    try:
        if a.cmd == "check":
            return cmd_check()
        if a.cmd == "exception":
            return cmd_exception()
        if a.cmd == "approve-runner":
            return cmd_approve_runner(a)
        return cmd_record(a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

## `scripts/findings_format.py`

`sha256 727f722a3fba0c04d2165b043d1294f251d00ba56fe60b363977dbd11fc99d7b`

```
#!/usr/bin/env python3
"""The one parser for reviewer output, and the one Finding ID grammar.

Imported by the runner, which writes findings.json, and by the MC-2 checker,
which verifies it. One module rather than two implementations, because the
failure this closes is components each enforcing their own idea of the format.

Alex Zamurko, 9 September 2026:

    Prompt, parser, and ledger must not independently impose different
    grammars. The clean choice is: the review format defines the canonical
    grammar, the runner validates it, and the ledger preserves it unchanged.

That happened. The prompt said `B01-F01`, the ledger demanded `C{cycle}-F{nn}`,
and eighteen findings were renamed between the review and the record. A second
copy of this logic anywhere would be a fourth grammar with the same problem, so
there is exactly one, and the grammar itself is read from the schema rather than
restated here.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DOC = REPO / "specs" / "evidence-schema-v1.0.md"

# §4's closed vocabulary. A class outside it is a defect in the review, not a
# finding to be recorded.
CLASSES = (
    "MISSING REQUIREMENT",
    "WRONG OWNERSHIP",
    "NONDETERMINISTIC WHERE D POSSIBLE",
    "SEMANTIC STEP TOO BROAD",
    "UNTESTED RULE",
    "CONTRADICTORY IMPLEMENTATION MAPPING",
)

# Permissive about the identifier on purpose. An id that fails the canonical
# grammar must make the result INVALID, not disappear from the parse: a strict
# pattern here would turn a malformed identifier into a missing finding, which
# is the worse failure of the two.
FINDING_HEADER = re.compile(r"^Finding ID:\s*(\S+)\s*$", re.M)
FINDING_CLASS = re.compile(r"^Class:\s*(.+?)\s*$", re.M)

# Used only to prove that zero means zero. Deliberately looser than the header.
# Requirement 1: zero is permitted only when parsing confirms the raw review
# contains no finding blocks, and the risk is a parser that fails to recognise
# real findings while the operator honestly asserts none. So zero has to survive
# a broader net, and any signal the strict parse does not account for is
# ambiguity rather than absence.
SIGNALS = (
    re.compile(r"finding\s*id\s*[:=]", re.I),
    re.compile(r"^\s*required correction\s*:", re.I | re.M),
    re.compile(r"\b[A-Z]{0,2}\d{2}-F\d{2,3}\b"),
)


class FormatError(Exception):
    """The schema does not declare what this module needs. Not recoverable."""


def canonical_id_grammar() -> re.Pattern:
    """The Finding ID grammar, read from its one authoritative location."""
    m = re.search(r"^FINDING_ID_GRAMMAR\s*=\s*(\S+)\s*$",
                  SCHEMA_DOC.read_text(encoding="utf-8"), re.M)
    if not m:
        raise FormatError(
            f"no FINDING_ID_GRAMMAR declared in {SCHEMA_DOC.name}. The canonical "
            "grammar has one authoritative location and this is it; without it "
            "the parser would be inventing a grammar, which is the divergence "
            "being closed.")
    return re.compile(m.group(1))


def extract(raw: str) -> tuple[list[dict], list[str]]:
    """(findings, problems) parsed deterministically from raw reviewer output.

    Anything unparseable is a problem rather than a silent omission. The failure
    being prevented is findings going missing between the reviewer and the
    ledger, so this never quietly returns fewer than it saw.
    """
    grammar = canonical_id_grammar()
    found: list[dict] = []
    problems: list[str] = []

    starts = [(m.start(), m.group(1)) for m in FINDING_HEADER.finditer(raw)]
    raw_count = len(starts)

    for i, (pos, fid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
        block = raw[pos:end]

        if not grammar.fullmatch(fid):
            problems.append(f"finding identifier {fid!r} does not match the "
                            f"canonical grammar {grammar.pattern}")
            continue
        km = FINDING_CLASS.search(block)
        if not km:
            problems.append(f"{fid} has no Class: line")
            continue
        klass = km.group(1).strip()
        if klass not in CLASSES:
            problems.append(f"{fid} declares a class outside the closed "
                            f"vocabulary of §4: {klass!r}")
            continue
        found.append({"id": fid, "class": klass})

    ids = [f["id"] for f in found]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate finding identifiers: {', '.join(dupes)}")

    # RAW_FINDING_COUNT = STRUCTURED_FINDING_COUNT.
    if raw_count != len(found) and not problems:
        problems.append(f"{raw_count} finding block(s) detected in the raw "
                        f"review but {len(found)} structured record(s) produced")

    if raw_count == 0:
        hits = [p.pattern for p in SIGNALS if p.search(raw)]
        if hits:
            problems.append(
                "no finding blocks parsed, but the raw review carries signals "
                "that one is present:\n    " + "\n    ".join(hits) +
                "\n  Zero cannot be asserted over a review the parser may have "
                "failed to read.")
    return found, problems
```

## `scripts/cycle_projection.py`

`sha256 f057b9aff4257e5ad27eb9da5a75a93f6f969d2c9ee47a71c601eb14b4cd3e78`

```
#!/usr/bin/env python3
"""What counts as a cycle, decided once and imported by everyone who asks.

B01-F11: "The ledger authorizes transitions from its unfiltered stored state and
history, while the controller filters events by valid cycles." Decision G was
implemented in `loop_state.py` alone, so the two components disagreed about what
a cycle is, and the disagreement was exploitable in both directions:

  * a DEMONSTRATED recorded in an invalid cycle left the ledger permanently
    RESOLVED, so a later valid resolution was refused while the controller still
    counted the finding OPEN. The finding could never be closed.
  * an ACCEPT recorded in an invalid cycle satisfied the ledger's precondition
    for `resolve`, so an invalid acceptance could authorize a closure the
    controller then counted as real.

Neither is fixable in one component. Filtering harder in the controller does not
stop the ledger from refusing; filtering harder in the ledger does not stop it
from authorizing. So the projection lives here, and both import it.

Three states, not two
--------------------
The distinction that makes this workable is between a cycle that has been judged
and failed and one that has not been judged yet.

    VALID     the directory exists and passes the MC-2 gate
    INVALID   the directory exists and fails it
    UNJUDGED  no directory yet

Only INVALID strips authority. An UNJUDGED cycle is the one being assembled
right now: findings get raised in it before its evidence is complete, and a
ledger that refused to record them would be unusable. Its events carry authority
provisionally, and lose it the moment the cycle is judged and fails, because
authority is recomputed on every read rather than frozen at write time.

Loop calculation is stricter and uses VALID only, per §2 and §3: an invalid cycle
"cannot consume one of the four valid review cycles", and an unjudged one has no
evidence to measure.

Nothing is ever deleted. Invalid events stay in the history as evidence of what
was recorded and when; they simply stop authorizing transitions and stop
blocking them.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate_cycle.py"


def cycle_dirs(review: Path) -> list[tuple[int, Path]]:
    out = []
    for d in sorted(review.iterdir()) if review.is_dir() else []:
        m = re.fullmatch(r"cycle-(\d{2})", d.name)
        if m and d.is_dir():
            out.append((int(m.group(1)), d))
    return sorted(out)


def gate(cycle_dir: Path) -> tuple[bool, str]:
    """Run the MC-2 conformance gate. Never read a recorded verdict.

    A loop controller that accepted an asserted PASS would let an invalid cycle
    consume the budget, which is the exact defect the "MAX 4 counts valid cycles"
    note exists to prevent.
    """
    r = subprocess.run([sys.executable, str(VALIDATOR), str(cycle_dir)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        return False, "checker could not run"
    reason = ""
    if r.returncode != 0:
        fails = [l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l]
        reason = fails[0] if fails else "MC-2 FAIL"
    return r.returncode == 0, reason


class Projection:
    """Which cycles exist, which passed, and which events may authorize.

    `valid`   ordered cycle numbers that exist and pass MC-2. Loop arithmetic.
    `invalid` cycle number -> why it failed. Evidence only.
    """

    def __init__(self, valid: list[int], invalid: dict[int, str]):
        self.valid = valid
        self.invalid = invalid

    def authorizes(self, cycle: int) -> bool:
        """May an event recorded in this cycle authorize a state transition?

        Judged-and-failed is the only disqualifier. See the module docstring for
        why an unjudged cycle has to count.
        """
        return cycle not in self.invalid

    def why_not(self, cycle: int) -> str:
        return self.invalid.get(cycle, "")


def project(review: Path) -> Projection:
    valid: list[int] = []
    invalid: dict[int, str] = {}
    for num, d in cycle_dirs(review):
        ok, why = gate(d)
        if ok:
            valid.append(num)
        else:
            invalid[num] = why or "MC-2 FAIL"
    return Projection(valid, invalid)


def replay(history: list[dict], proj: Projection,
           upto: set[int] | None = None) -> str | None:
    """The state a finding reached, counting only events that carry authority.

    `upto` additionally restricts to a set of cycle numbers, which is how the
    controller asks for the state at an earlier cycle boundary. The ledger passes
    None and means "as things stand".
    """
    state = None
    for e in history:
        c = e["cycle"]
        if upto is not None and c not in upto:
            continue
        if not proj.authorizes(c):
            continue
        state = e["state"]
    return state


def last_authorized(history: list[dict], event: str,
                    proj: Projection) -> dict | None:
    """The most recent event of this kind that is allowed to authorize anything.

    An ACCEPT in an invalid cycle is still in the history and still visible in
    `show`. It just cannot be the ACCEPT that `resolve` requires.
    """
    for e in reversed(history):
        if e["event"] == event and proj.authorizes(e["cycle"]):
            return e
    return None
```

## `scripts/authority.py`

`sha256 2794e8149559593fe9fb5fb49e3998ad4b84fcbe1cebb077188ba5ea6f6aa203`

```
#!/usr/bin/env python3
"""Approvals that have to come from outside the implementing agent.

Alex Zamurko, 9 September 2026, ruling 3:

    An authoritative capture may be superseded only with explicit human/evidence
    authority approval and a recorded reason; the implementing agent cannot
    supersede it unilaterally ... allowing the implementing agent to choose a
    later Codex capture creates a direct cherry-picking path. Preserving all
    attempts is not sufficient if the same party can decide which one governs.

The same shape is needed for runner approval, which is what ends the bootstrap
exception, so it lives here once rather than being written twice and drifting.

What this establishes, and what it does not
-------------------------------------------
MC1_ENFORCEMENT is CONVENTION_ONLY on this environment. There is one machine and
one account, so nothing here proves who wrote a file. Saying otherwise would be
the "claim stronger than its evidence" failure the review prompt asks reviewers
to flag, and it would be this module claiming it.

What it does establish is narrower and still worth having:

  * an approval must exist as a separate artifact before the action runs, so the
    decision leaves a record instead of living in a command-line flag;
  * it must name a person and a reason, so the record is attributable;
  * it must bind to the exact bytes it approves, by hash, so an approval cannot
    be recycled for a different action later. This is the mechanical part, and
    it is the part that holds regardless of who wrote the file;
  * the hashes it must name are not knowable until the action has been attempted
    and refused once, so obtaining one is an out-of-band step rather than a
    flag the implementing agent can add to its own command.

Under CONVENTION_ONLY a determined implementing agent can still write the
approval itself. The change is that doing so is a deliberate forgery naming a
specific person, rather than passing a flag. That is a real difference in kind,
and it is the most this environment supports. A write boundary would give more,
and needs a second machine.
"""

from __future__ import annotations

import json
from pathlib import Path

MIN_REASON = 20


class NotAuthorized(Exception):
    """No usable approval for this action. The caller refuses and changes nothing."""


def _fail(path: Path, why: str, bindings: dict[str, str], kind: str) -> None:
    lines = [why, "",
             f"  Expected an approval record at:  {path}", "",
             "  It has to be written by someone other than the implementing "
             "agent, and name:",
             f"    schema          {kind}/1",
             "    authorized_by   the person approving, by name",
             f"    reason          why, in at least {MIN_REASON} characters",
             "    at              when, ISO 8601"]
    for k, v in bindings.items():
        lines.append(f"    {k:<15} {v}")
    lines += ["",
              "  The hashes above are what bind the approval to this exact "
              "action. They are",
              "  printed here because they are not knowable until now, which is "
              "what makes",
              "  obtaining the approval a step outside this command."]
    raise NotAuthorized("\n".join(lines))


def require_approval(path: Path, kind: str, bindings: dict[str, str]) -> dict:
    """Load and check an approval, or refuse.

    `bindings` are field name -> required value. Every one must appear in the
    record and match exactly. That is what stops an approval for one supersession
    being reused for the next.
    """
    if not path.is_file():
        _fail(path, "This action requires an approval from outside the "
                    "implementing agent, and none is recorded.", bindings, kind)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise NotAuthorized(f"the approval record at {path} is not valid JSON: {e}")

    if rec.get("schema") != f"{kind}/1":
        raise NotAuthorized(
            f"the approval record declares schema {rec.get('schema')!r}, "
            f"expected {kind + '/1'!r}.\n"
            "  An approval for one kind of decision does not authorize another.")

    who = str(rec.get("authorized_by", "")).strip()
    if not who:
        raise NotAuthorized(
            "the approval record names no one in authorized_by.\n"
            "  An unattributed approval is indistinguishable from the "
            "implementing agent\n  approving its own action, which is the thing "
            "this record exists to prevent.")

    reason = str(rec.get("reason", "")).strip()
    if len(reason) < MIN_REASON:
        raise NotAuthorized(
            f"the approval record's reason is {len(reason)} characters; at least "
            f"{MIN_REASON} are required.\n"
            "  The reason is what a later reader uses to judge whether the "
            "decision was sound.\n  A placeholder leaves the record looking "
            "complete while saying nothing.")

    if not str(rec.get("at", "")).strip():
        raise NotAuthorized("the approval record has no `at` timestamp, so it "
                            "cannot be placed in the sequence of events.")

    wrong = []
    for field, expected in bindings.items():
        got = str(rec.get(field, "")).strip()
        if got != expected:
            wrong.append(f"    {field}\n      approved  {got or '(absent)'}\n"
                         f"      actual    {expected}")
    if wrong:
        raise NotAuthorized(
            "the approval record does not match the action being attempted:\n"
            + "\n".join(wrong) +
            "\n\n  An approval binds to the exact bytes it approved. If this is "
            "a different\n  action, it needs its own approval rather than "
            "inheriting one.")

    return rec


def describe(rec: dict) -> str:
    return f"approved by {rec['authorized_by']} at {rec['at']}: {rec['reason']}"
```

## `scripts/run_pins.py`

`sha256 4c476f304c7688c188eb62f940227e2f688b0f1c2dc59feca43e1fe7a352d344`

```
#!/usr/bin/env python3
"""Which artifacts govern a run, and which are under review. Never both.

Alex Zamurko, 10 September 2026, the Run-Pin and Review-Target Separation
Specification. Its governing invariant:

    No review process may require an artifact to remain byte-invariant for the
    duration of a run while simultaneously requiring that same artifact version
    to change in order to resolve review findings.

BOOTSTRAP-001 required exactly that. It pinned `specs/evidence-schema-v1.0.md`
as its only run-level spec, and the same file was the first of cycle 01's six
review targets. Cycle 01 raised findings that could only be repaired by editing
it, and editing it broke the run's own pin, so the runner refused to open
cycle 02 — the cycle whose purpose was to demonstrate those repairs and move
eighteen findings out of OPEN. The loop was stopped by its own correctness.

Amendments are history, not edits
---------------------------------
run.json is evidence of what was pinned when the run was created, and it stays
true about that. Rewriting it so a failing check passes is the move this whole
repository exists to prevent, and it would destroy the only record of what
cycle 01 was actually conducted under.

So a change to the pin set is appended to `pin-amendments.json` instead, with
the five fields the specification requires: reason, affected artifacts, prior
pin set, new pin set, effective cycle. The pin set governing any cycle is then
computed by replaying that history rather than read from a single mutable field.

That matters beyond tidiness. Cycle 01 was conducted under the original pins and
cycle 02 under the amended ones, and both statements have to stay recoverable.
B01-F07, still open by Alex Zamurko's deferral, is the finding that no check ties
a cycle's recorded protocol_sha256 and spec_sha256 back to the run. When that is
repaired it must tie each cycle to the pins in force AT THAT CYCLE, which is what
`pins_for_cycle` returns. Tying every cycle to the latest pin set would
retroactively invalidate cycle 01, which is the same defect in a new place.

What this does not do
---------------------
It does not decide whether an amendment was wise. It records that one was made,
by whom, and why, and it refuses an amendment whose prior_pin_set does not match
what the history actually shows, so the chain cannot be quietly rewritten in the
middle. Under MC1_ENFORCEMENT: CONVENTION_ONLY that is drift detection, not
prevention.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "run-pin-amendments/1"
MIN_REASON = 30


class PinError(Exception):
    """The pin history cannot be read, or does not describe a coherent chain."""


def amendments_path(run_dir: Path) -> Path:
    return run_dir / "pin-amendments.json"


def initial_pin_set(run: dict) -> list[str]:
    """What run.json pinned at init: the protocol and every spec file."""
    out = [run["protocol"]["path"]]
    out += [e["path"] for e in run.get("spec_files", [])]
    return sorted(set(out))


def load_amendments(run_dir: Path) -> list[dict]:
    p = amendments_path(run_dir)
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PinError(f"pin-amendments.json is not valid JSON: {e}")
    if d.get("schema") != SCHEMA:
        raise PinError(f"pin-amendments.json declares schema {d.get('schema')!r}, "
                       f"expected {SCHEMA!r}")
    items = d.get("amendments")
    if not isinstance(items, list):
        raise PinError("pin-amendments.json has no amendments list")
    return items


def validate_chain(run: dict, items: list[dict]) -> None:
    """Each amendment must name the five required fields and follow the last.

    The prior_pin_set check is the load-bearing one. Without it an amendment
    could assert any starting point, and the recorded history would no longer
    reconstruct what actually governed each cycle: someone could insert a pin
    set that never existed and every later replay would agree with them.
    """
    required = ("reason", "affected_artifacts", "prior_pin_set", "new_pin_set",
                "effective_cycle", "authorized_by", "at")
    current = initial_pin_set(run)
    last_cycle = 0
    for i, a in enumerate(items):
        missing = [k for k in required
                   if a.get(k) in (None, "", [], {})]
        if missing:
            raise PinError(
                f"amendment {i} is missing {', '.join(missing)}.\n"
                "  The specification requires reason, affected artifacts, prior "
                "pin set, new pin\n  set and effective cycle. Attribution and a "
                "timestamp are required too: a pin\n  change with nobody's name "
                "on it is the implementing agent changing what governs\n  its own "
                "review.")
        if len(str(a["reason"]).strip()) < MIN_REASON:
            raise PinError(
                f"amendment {i}'s reason is {len(str(a['reason']).strip())} "
                f"characters; at least {MIN_REASON} are required.")
        if sorted(a["prior_pin_set"]) != current:
            raise PinError(
                f"amendment {i} does not follow the pin history.\n"
                f"    it claims the prior set was  {sorted(a['prior_pin_set'])}\n"
                f"    the history says it was      {current}\n"
                "  An amendment that starts from a set that never existed makes "
                "every later\n  replay agree with a history nobody lived.")
        if int(a["effective_cycle"]) <= last_cycle:
            raise PinError(
                f"amendment {i} takes effect at cycle "
                f"{a['effective_cycle']}, which is not after the previous "
                f"amendment's cycle {last_cycle}. Amendments apply forward.")
        affected = set(a["affected_artifacts"])
        changed = set(current) ^ set(a["new_pin_set"])
        if affected != changed:
            raise PinError(
                f"amendment {i}'s affected_artifacts do not match what it "
                "changes.\n"
                f"    declared  {sorted(affected)}\n"
                f"    actual    {sorted(changed)}\n"
                "  The declared list is what a reader checks against; if it can "
                "differ from the\n  real change, the record describes an "
                "amendment that did not happen.")
        current = sorted(set(a["new_pin_set"]))
        last_cycle = int(a["effective_cycle"])


def pins_for_cycle(run: dict, items: list[dict], cycle_n: int) -> list[str]:
    """The run-level governing pin set in force for cycle `cycle_n`.

    An amendment effective at cycle k governs cycle k and every cycle after it,
    and does not reach back. Cycle 01 keeps the pins it was conducted under.
    """
    pins = initial_pin_set(run)
    for a in items:
        if int(a["effective_cycle"]) <= cycle_n:
            pins = sorted(set(a["new_pin_set"]))
    return pins


def governing_pins(run: dict, run_dir: Path, cycle_n: int) -> list[str]:
    items = load_amendments(run_dir)
    validate_chain(run, items)
    return pins_for_cycle(run, items, cycle_n)


def separation_violations(pins: list[str], targets: list[str]) -> list[str]:
    """Artifacts asked to be invariant and under review at the same time.

    §2 of the specification: the same artifact version must not serve as both an
    immutable run-governing input and a mutable review candidate. Without
    explicit ACTIVE/CANDIDATE version separation an artifact belongs to exactly
    one role.
    """
    return sorted(set(pins) & set(targets))
```

