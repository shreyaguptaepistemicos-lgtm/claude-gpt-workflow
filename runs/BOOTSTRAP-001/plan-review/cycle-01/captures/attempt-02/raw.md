TARGET_SHA256 22c86a1b4bd6b9b0c304bb4113b552df30801b61c35e134df95db1882d2e07b8

Verified the target, governing protocol, and all six artifact hashes. All five supplied control suites and `test_prompts.py` passed with consistent UTF-8 handling. Passing controls do not establish the requirements identified below. Repository artifacts were not changed.

---

Finding ID: B01-F01  
Class: CONTRADICTORY IMPLEMENTATION MAPPING  
Artifact: scripts/run_review.py  
Location: `next_cycle`, `cmd_freeze`, lines 247–350  
Evidence: `cmd_freeze` refuses when the next directory number exceeds four, without counting MC-2-valid cycles. An isolated fixture containing four invalid cycles refused cycle 05 despite having zero valid cycles. `test_run_review.py::budget` expressly expects this refusal.  
Finding: Invalid cycles consume the runner’s available budget, contradicting MC-2 and §§2 and 10.  
Required correction: Separate attempt numbering from the valid-cycle count. Permit replacement attempts until four valid cycles have occurred, subject to earlier mandatory exits. Correct the budget control.

---

Finding ID: B01-F02  
Class: CONTRADICTORY IMPLEMENTATION MAPPING  
Artifact: scripts/loop_state.py; scripts/run_review.py  
Location: `loop_state.main`, lines 147–241; `cmd_freeze`  
Evidence: The controller evaluates only the latest valid-cycle boundary. A probe with one finding accepted in cycle 01, unchanged in cycle 02, and resolved in cycle 03 returned `CONVERGED`, although cycle 02 required `STALLED`. The runner checks previous output existence, not the previous loop exit.  
Finding: Later cycles can override an earlier mandatory termination. The supplied `four_then_resolved` control reinforces this incorrect behavior.  
Required correction: Evaluate valid cycles chronologically and retain the first terminal outcome. Refuse further automated cycles after that outcome unless an explicitly recorded human transition authorizes another loop.

---

Finding ID: B01-F03  
Class: WRONG OWNERSHIP  
Artifact: specs/evidence-schema-v1.0.md; scripts/run_review.py; scripts/ledger.py; scripts/loop_state.py  
Location: Schema directory layout; `cmd_record`; `ledger_path`; `load_ledger`  
Evidence: The schema assigns per-cycle `findings.json` creation to the runner. The runner never creates it; the ledger instead writes a mutable review-level file. The controller treats an absent ledger as an empty finding set. Recording raw output containing `C01-F01` and immediately running the controller produced `CONVERGED`.  
Finding: Authoritative finding capture has no implemented completion boundary. Missing extraction is interpreted as a review reporting no findings.  
Required correction: Implement explicit runner-owned finding capture, including an affirmative empty result. Separate authoritative findings from response/state history, reconcile the documented layout, and refuse loop classification until capture is complete.

---

Finding ID: B01-F04  
Class: MISSING REQUIREMENT  
Artifact: scripts/run_review.py  
Location: `compose_input`; `cmd_freeze`, lines 369–427  
Evidence: Plan input contains the selected plan files and protocol, but not the pinned specification. Implementation input contains only the diff and test results as artifacts; the target’s candidate commit, tree hash, and approved-plan hash are not supplied by `compose_input`, nor is `target.json` embedded. A probe confirmed that the pinned specification text was absent.  
Finding: The runner does not supply the frozen implementation target or its complete referenced content as §2.2 requires. It also omits the specification and approved plan needed to assess the review target.  
Required correction: Compose input from the frozen target manifest, including its exact identifiers and the verified specification, approved plan, and relevant candidate content. Test actual input contents for both review types.

---

Finding ID: B01-F05  
Class: NONDETERMINISTIC WHERE D POSSIBLE  
Artifact: scripts/run_review.py; scripts/validate_cycle.py  
Location: `cmd_freeze`, lines 379–389; implementation checks 11–12  
Evidence: The runner stores `args.candidate_commit` verbatim while resolving only its tree. Values such as `HEAD` are accepted. Advancing that reference to another commit with the same tree leaves checks 11–12 passing while changing the identified commit.  
Finding: The target does not necessarily freeze the exact candidate commit required by §10.1.  
Required correction: Resolve and store the full commit object ID, derive its tree from that ID, and reject mutable revision expressions in frozen targets.

---

Finding ID: B01-F06  
Class: MISSING REQUIREMENT  
Artifact: scripts/validate_cycle.py; specs/evidence-schema-v1.0.md  
Location: Check 13, lines 263–289; concretisation F  
Evidence: Check 13 compares two recorded strings. It neither hashes the approved plan nor checks the approval decision. An isolated implementation fixture continued to pass all fifteen checks after the approved plan’s contents changed.  
Finding: Decision F provides a comparison against an approval record, but does not establish the required match against the frozen approved plan.  
Required correction: Resolve and hash the approved plan artifact or manifest, verify its recorded approval, and require agreement between the artifact, approval record, and implementation target.

---

Finding ID: B01-F07  
Class: MISSING REQUIREMENT  
Artifact: scripts/validate_cycle.py  
Location: Common-field validation and check 9, lines 181–231  
Evidence: `protocol_sha256` and `spec_sha256` are checked only for key presence. Check 9 validates plan-file references or implementation-field presence; it never verifies the protocol/specification digests or their relationship to the run pins.  
Finding: MC-2 can pass targets declaring arbitrary protocol and specification hashes despite requiring mandatory hashed artifacts to be present and matching.  
Required correction: Resolve the pinned protocol and specification set, verify their hashes and target/run agreement, and add independent mismatch and missing-artifact controls.

---

Finding ID: B01-F08  
Class: MISSING REQUIREMENT  
Artifact: scripts/run_review.py; scripts/loop_state.py  
Location: Bootstrap check in `cmd_init`; `cmd_freeze`; controller cycle admission  
Evidence: Bootstrap approval is evaluated only at initialization. A probe approved bootstrap, initialized a real run, changed `validate_cycle.py`, and successfully froze a cycle. Exempt runs are labeled in `run.json`, but the controller never reads that label.  
Finding: Existing runs can use tooling whose approval is stale, and development evidence can enter authoritative loop-state calculations.  
Required correction: Recheck current bootstrap approval before real cycle operations. Explicitly exclude bootstrap-exempt evidence from authoritative protocol-loop outcomes.

---

Finding ID: B01-F09  
Class: MISSING REQUIREMENT  
Artifact: scripts/bootstrap_gate.py  
Location: `cmd_record`, lines 303–337; `evaluate`, lines 189–252  
Evidence: Recording a decision checks only that four evidence files are nonempty, then hashes the current component files. It never compares those files with the frozen review target. Evaluation subsequently ignores the recorded evidence hashes.  
Finding: Components changed after review but before decision recording can receive approval under old review evidence. Removing or replacing that evidence afterward does not invalidate approval.  
Required correction: Bind the decision to the reviewed target and its component hashes, reject intervening drift, and verify continued presence and integrity of the referenced review evidence.

---

Finding ID: B01-F10  
Class: MISSING REQUIREMENT  
Artifact: scripts/bootstrap_gate.py  
Location: `COMPONENTS`, `ALWAYS`, `covered`, lines 65–78 and 171–180  
Evidence: The required hash set contains five Python files. It omits `specs/evidence-schema-v1.0.md`, although the frozen review target contains six artifacts and the schema is expressly subject to bootstrap review.  
Finding: Bootstrap approval does not cover the complete reviewed artifact set. Editing the schema does not invalidate that approval.  
Required correction: Include the frozen evidence schema in the mandatory approval hash set and demonstrate that schema drift blocks approval.

---

Finding ID: B01-F11  
Class: CONTRADICTORY IMPLEMENTATION MAPPING  
Artifact: scripts/ledger.py; scripts/loop_state.py  
Location: `cmd_respond`, `cmd_resolve`, `last_event`; controller `state_after`  
Evidence: The ledger authorizes transitions from its unfiltered stored state and history, while the controller filters events by valid cycles. A resolution recorded in an invalid cycle leaves the ledger permanently `RESOLVED`, so a subsequent valid resolution is refused although the controller still sees `OPEN`. Conversely, an ACCEPT in an invalid cycle can authorize a later resolution that the controller counts.  
Finding: Decision G is implemented only in the controller. Invalid events still affect transition authority, creating incompatible states and allowing an invalid acceptance to support closure.  
Required correction: Use the same valid-event projection for ledger transition authorization and loop calculation. Preserve invalid events as evidence without allowing them to authorize or permanently block valid transitions.

---

Finding ID: B01-F12  
Class: MISSING REQUIREMENT  
Artifact: scripts/ledger.py  
Location: `cmd_respond`, lines 177–230; `cmd_resolve`, lines 233–264  
Evidence: Responses have no check against the finding’s creation cycle or latest event cycle. A finding raised in cycle 03 can receive an ACCEPT labeled cycle 01 and a resolution labeled cycle 02. History is then interpreted in append order.  
Finding: Backdated events can make a finding resolved before it was raised, defeating the later-target requirement in decision D and §5.  
Required correction: Validate cycle existence and event chronology, including creation, acceptance, and resolution order. Refuse backdated transitions and add controls for them.

---

Finding ID: B01-F13  
Class: CONTRADICTORY IMPLEMENTATION MAPPING  
Artifact: scripts/ledger.py  
Location: `cmd_raise`, lines 148–151  
Evidence: The duplicate-ID refusal instructs that “a re-raised issue in a later cycle is a new finding” rather than a reuse of its persistent ID. The protocol requires persistent identifiers; its V40 criterion explicitly says the same issue retains the same ID.  
Finding: The prescribed workflow changes the identity of recurring findings, distorting finding-set comparisons and dispute tracking.  
Required correction: Preserve the existing identifier when a review repeats an existing issue. Record a later observation separately without creating another actionable finding or another new dispute.

---

Finding ID: B01-F14  
Class: MISSING REQUIREMENT  
Artifact: scripts/run_review.py  
Location: `cmd_init` run record, lines 174–191  
Evidence: The run record contains bootstrap status but no `MC1_ENFORCEMENT` field. The isolated runner probe confirmed its absence. The enforcement status appears only in general documentation.  
Finding: MC-1 requires each run to record its enforcement status; a repository-wide statement does not fulfill that requirement.  
Required correction: Record `MC1_ENFORCEMENT: CONVENTION_ONLY` in each run and validate its presence.

---

Finding ID: B01-F15  
Class: CONTRADICTORY IMPLEMENTATION MAPPING  
Artifact: specs/evidence-schema-v1.0.md; scripts/run_review.py; scripts/bootstrap_gate.py  
Location: Schema line 116; `compose_input` documentation; bootstrap self-hashing commentary, lines 72–76  
Evidence: The schema and runner say freezing “proves the artifact did not change.” Bootstrap commentary presents self-hashing as fixing the possibility of replacing `evaluate` with an unconditional success result. The same writable code performs that self-check; replacing the evaluation bypasses it.  
Finding: These claims exceed the guarantees available under `CONVENTION_ONLY`. Hash recording and voluntary self-checking do not establish immutability or an independent enforcement boundary.  
Required correction: Describe these mechanisms as procedural capture and drift detection when the checks execute faithfully. Remove the implied technical guarantee from self-hashing.

---

Finding ID: B01-F16  
Class: UNTESTED RULE  
Artifact: scripts/bootstrap_gate.py; supplied scripts/test_bootstrap_gate.py  
Location: `PY_REF`; `closure`; dependency controls  
Evidence: Dependency discovery recognizes filename strings ending in `.py`. Ordinary `import helper_module` and `from helper_module import VALUE` are not recognized. The dependency control inserts `_HELPER = "helper_module.py"` without loading that module.  
Finding: The supplied control establishes filename-string discovery, not the claimed executable dependency closure. An imported local helper can remain outside the approval hash set.  
Required correction: Discover repository-local imports and explicitly handle supported dynamic loading. Test a helper that actually affects component behavior, then verify that changing it invalidates approval.

---

Finding ID: B01-F17  
Class: UNTESTED RULE  
Artifact: scripts/run_review.py; supplied scripts/test_run_review.py  
Location: Implementation refusals in `cmd_freeze`, lines 379–411; suite refusal cases  
Evidence: The suite claims every refusal fires, but implementation controls cover only missing and malformed approved-plan hashes. They do not exercise missing or unresolvable candidate commits, missing diff input, or missing test-result input.  
Finding: The declared control count does not substantiate the stronger claim that every runner refusal has been demonstrated. These are distinct guards, beyond the disclosed shared file-existence weakness.  
Required correction: Add controls that reach each distinct missing implementation refusal and assert its specific reason, or narrow the coverage claim.

---

Finding ID: B01-F18  
Class: UNTESTED RULE  
Artifact: Supplied scripts/test_interfaces.py, as evidence for scripts/validate_cycle.py  
Location: Seam 1 missing-field probes, lines 157–168  
Evidence: The valid implementation fixture lives under `runs/I-001/implementation-review/cycle-01`, but missing-field probes live under `runs/I-001/probe-<field>`. Consequently, check 13 looks for approval under `runs/plan-approval`, rather than the populated `runs/I-001/plan-approval`. The probe accepts any nonzero exit.  
Finding: Every missing-field probe can pass because the approval record is misplaced, even if enforcement of the field under test is removed. The claimed schema/checker seam is not independently demonstrated.  
Required correction: Place probes in equivalent cycle layouts, establish a passing unmodified fixture at each location, and assert failure of the specific check responsible for the removed field.

---

SEMANTIC STEP TOO BROAD: No findings.