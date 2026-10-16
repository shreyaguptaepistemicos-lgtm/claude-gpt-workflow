TARGET_SHA256 8facc07a82004f21b12bd7df699d4b17156c562d4bcae61b15693647dd3b5107

Verified the target hash, the governing protocol hash, and all ten target artifact hashes against the reviewed code. Read the cycle-01 findings and decisions A–L. Ran test_validate_cycle.py, test_run_review.py, test_ledger.py, test_bootstrap_gate.py, test_interfaces.py and test_prompts.py under Ubuntu Python 3.14.4; all exited 0. Additional probes used disposable repositories and reproduced the failures below. Passing supplied controls do not demonstrate the missing cases.

The test suites are supporting working-tree evidence, not hashed entries in this target.json. The prompt's statement that “the suites are in the target” is inaccurate: its ten entries are the schema and nine implementation modules.

Claimed repairs checked and found to hold:

- B01-F03: cmd_record creates runner-owned per-cycle findings.json, records affirmative zero, and separates it from ledger.json. The controller refuses absent extraction or unaccounted finding IDs. The supplied positive and negative controls passed. The newly reviewed parser has a separate omission defect below.
- B01-F06: check 13 now hashes the named plan, compares its digest with the approval and target, and requires decision APPROVE. The interface controls establish a passing baseline and independently exercise changed plan bytes, absent artifact identification and RETURN_FOR_REWORK. This repairs the original two-string comparison. Preservation across subsequent implementation reviews remains defective as described below.
- B01-F10: the evidence schema is a required bootstrap component. The gate rejects target/covered-set disagreement and schema drift; the controls passed.
- B01-F13: reopen preserves the existing identifier, records a later recurrence with evidence and moves RESOLVED to OPEN. Duplicate-raise guidance now points to reopen. The recurrence controls passed. The independent schema/ledger grammar mismatch below remains.
- B01-F15: the original freezing-as-proof and self-hashing-as-protection claims were corrected. The schema and bootstrap self-hashing explanation now state the CONVENTION_ONLY limitation. The newly added authority module contains a different unsupported mechanism claim, and the prose control omits all four newly reviewed modules; both are reported below.
- B01-F16: AST import discovery repairs the original flat-module import omission. The current ten-file covered set includes findings_format.py, cycle_projection.py, authority.py and run_pins.py through actual dependencies. The zqx_probe_dep control uses a real import and reads its value; it does not depend on a matching filename in commentary. Its inclusion and subsequent drift controls passed. This verdict concerns the demonstrated flat-module case, not an unrestricted claim about every Python package or dynamic import form.
- B01-F17: the missing/unresolvable candidate, missing approved-plan hash, missing diff and missing test-result paths now have controls that assert their particular refusal reasons. They passed.
- B01-F18: seam-1 probes now use implementation-review/cycle-01 layouts with approval records, establish an unmodified passing control, and assert the responsible numbered check for each removed field. They passed.

B01-F02, B01-F08, B01-F09, B01-F11 and B01-F14 are only partially repaired and must remain OPEN for the reasons below. The cycle-02 prompt's shorter repair descriptions do not discharge the omitted parts of the original findings.

B01-F01, B01-F04, B01-F05, B01-F07 and B01-F12 remain OPEN by the stated deferral. They are not re-reported as new findings. Where new mechanisms interact with them, that interaction is identified explicitly.

Finding ID: B01-F02
Status: REPAIR NOT DEMONSTRATED
Evidence: scripts/loop_state.py::_run evaluates boundaries chronologically and correctly preserves the first uncleared exit. However, when every terminal boundary has been cleared, its `if governing is None` fallback calls decide again at the latest boundary without applying that boundary's authorization. A fixture with an OPEN finding unchanged across two valid cycles and an authorization naming n=2/STALLED printed both “STALLED at n=2 cleared by recorded authorization” and “LOOP_STATUS: STALLED”. scripts/run_review.py::check_loop_not_terminated consequently still refuses the next cycle. The supplied authorization control pre-creates four cycles and authorizes historical boundaries; it never tests resuming immediately after authorizing the latest exit.
Finding: The original unauthorized-overwrite defect is fixed, but the explicitly authorized continuation required by the original correction and decision I does not work at the point the runner needs it. The implementing agent's repair claim is therefore incomplete.
Required correction: Represent a cleared latest boundary as permission for the explicitly authorized continuation, without reinstating the cleared exit in the fallback. Define the resumed loop's budget and boundary semantics. Add a runner/controller test that stops, records the matching authorization, and then successfully freezes the next permitted cycle; mismatched or absent authorization must still refuse.

Finding ID: B01-F08
Status: REPAIR NOT DEMONSTRATED
Evidence: scripts/run_review.py::check_bootstrap_still_holds now correctly rechecks a nonexempt run at freeze, and the drift control passed. However, scripts/loop_state.py and scripts/cycle_projection.py still do not read the run's bootstrap classification. An isolated run initialized with --bootstrap-exempt, frozen and recorded through the runner with explicit zero findings returned `LOOP_STATUS: CONVERGED` through the ordinary controller interface.
Finding: The stale-approval-at-freeze half is repaired; the original requirement to exclude NOT_A_PROTOCOL_CYCLE development evidence from authoritative protocol-loop outcomes is not. The prompt claims repair while omitting this half of the finding.
Required correction: Distinguish explicitly requested development calculations from authoritative protocol calculations. Reject or distinctly label exempt evidence in the latter, and propagate that distinction through the runner/controller interface. Preserve the ability to analyze bootstrap evidence without representing it as a protocol cycle.

Finding ID: B01-F09
Status: REPAIR NOT DEMONSTRATED
Evidence: scripts/bootstrap_gate.py::cmd_record now requires a target and checks component drift. But evaluate still checks only the decision and component hashes, ignoring the recorded `evidence` and `reviewed_target` hashes. After recording approval in a fixture, deleting all four bootstrap evidence files left evaluate returning `(True, [])`. In addition, cmd_record does not establish that its separately supplied target is the target described by bootstrap-review/codex-input.md and the preserved review output.
Finding: Intervening component drift is detected, but the original requirement to verify continued review-evidence integrity remains unimplemented. Approval can survive deletion of the evidence on which it is said to rest, and the target/evidence association remains an assertion.
Required correction: Validate the recorded target and all referenced evidence for existence and hash agreement during evaluation. At recording, verify the frozen target hash and its association with the retained review input and capture. Add deletion, alteration and mismatched-target controls after a genuinely passing approval fixture.

Finding ID: B01-F11
Status: REPAIR NOT DEMONSTRATED
Evidence: scripts/cycle_projection.py::replay skips an invalid event but unconditionally assigns the state of later retained events. In a fixture, RAISED in valid cycle 01, ACCEPT in then-valid cycle 02, and DEMONSTRATED in valid cycle 03 were recorded successfully. Making cycle 02 fail MC-2 afterward caused show to mark ACCEPT “[no authority]” while retaining RESOLVED; the controller returned CONVERGED. The supplied controls invalidate an ACCEPT before attempting resolution, or invalidate the resolution itself. They do not invalidate a prerequisite after a dependent transition exists. Separately, Projection.authorizes returns true for every cycle number absent from its invalid map, including nonexistent cycles; the ledger can therefore authorize from UNJUDGED events while loop arithmetic excludes them.
Finding: Recomputing event membership is not recomputing transition authority. A resolution supported only by an invalid acceptance survives, reproducing the original forbidden outcome. Decision H's provisional authority also contradicts the claimed shared valid-event projection: staging an event does not require granting it authority to close a finding. This is a new interaction with the deferred chronology/existence weakness B01-F12, not a request to re-report that finding unchanged.
Required correction: Replay legal transitions and their prerequisites over authoritative events, rather than copying the last retained state. Invalidation of a prerequisite must invalidate the dependent transition's authority. Permit provisional recording separately from authoritative state transitions. Test validity loss after resolution and the nonexistent-cycle acceptance path, with ledger and controller required to agree.

Finding ID: B01-F14
Status: REPAIR NOT DEMONSTRATED
Evidence: scripts/run_review.py::cmd_init now writes `mc1_enforcement: CONVENTION_ONLY` for newly initialized runs. That portion holds. No supplied suite asserts this field, and load_run, freeze and MC-2 do not require its presence. The actual BOOTSTRAP-001/run.json still lacks it and was accepted for cycle 02. The cycle-01 correction explicitly required both recording the status in each run and validating its presence.
Finding: The newly generated field is an improvement, but missing run-level enforcement status remains accepted and the repair has no direct negative control. The prompt's unqualified “run.json records MC1_ENFORCEMENT” claim is not true of the run under review.
Required correction: Require an explicit recognized enforcement status when consuming a run, with an attributable compatibility record for older runs if run.json must remain unchanged. Add a positive creation assertion and an independent missing-status refusal control.

Finding ID: B02-F01
Class: MISSING REQUIREMENT
Artifact: scripts/findings_format.py; scripts/run_review.py; scripts/loop_state.py
Location: findings_format.extract, especially the `if raw_count == 0` signal check
Evidence: Parsing one canonical block followed by a second block whose `Finding ID:` line has one leading space returned only B02-F01 and an empty problems list. The second block contained its own class and Required correction. The broader signals are inspected only when no canonical headers were found. Both extraction and controller reconciliation reuse this parser, so both agree on the same incomplete ID list.
Finding: A partially parseable review silently loses findings. The claimed equality of raw and structured counts compares structured output with the same strict header detector, not with every apparent finding in the raw review. One successful parse disables the safeguard against unrecognized blocks.
Required correction: Detect and account for apparent finding boundaries throughout the entire response, including mixed canonical/noncanonical blocks. Reject ambiguity or normalize explicitly supported formatting without dropping identifiers. Add mixed-block controls that demonstrate capture refusal and prevent a smaller finding set from entering loop calculations.

Finding ID: B02-F02
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: runs/BOOTSTRAP-001/plan-review/cycle-02/codex-input.md; scripts/findings_format.py
Location: Output format for a repair not demonstrated; findings_format.extract
Evidence: The mandated recurrence block contains Finding ID, Status, Evidence, Finding and Required correction, but no Class. Passing exactly that form to the frozen parser returned `B01-F11 has no Class: line`. Protocol §4 retains the closed classification requirement, and the parser requires Class for every block. test_prompts.py checks the bootstrap identifier grammar but does not round-trip this recurrence template.
Finding: Following this review prompt exactly produces a response the capture runner refuses. The supplied alternative format disagrees with the protocol and its parser. The recurrence blocks in this response intentionally follow the requested form; their capture incompatibility is this finding, not an omitted review verdict.
Required correction: Make the recurrence format, protocol interpretation and parser agree. Either require the original class explicitly or define a deterministic, validated lookup of the existing class for persistent identifiers. Round-trip every advertised output form through the actual capture parser, including a mixture of new and persistent findings.

Finding ID: B02-F03
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: specs/evidence-schema-v1.0.md; scripts/findings_format.py; scripts/ledger.py
Location: FINDING_ID_GRAMMAR; ledger.FINDING_ID and check_id
Evidence: The schema permits zero to two capital prefix letters. The parser accepted `AB02-F01` with class UNTESTED RULE without problems. The ledger rejected the same identifier because its independently hard-coded expression permits at most one capital letter.
Finding: The declared single grammar still diverges at the parser/ledger seam. A valid captured finding cannot be entered unchanged, despite the explicit ruling against independent grammars. This is distinct from the repaired recurrence transition.
Required correction: Have the ledger consume the canonical grammar and preserve every valid identifier. Keep any origin-cycle validation separate from prefix-length assumptions. Test every allowed prefix length and representative invalid identifiers end to end.

Finding ID: B02-F04
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: scripts/run_review.py
Location: cmd_record, supersession deletion before the `found and args.zero_findings` refusal
Evidence: A fixture had a valid authoritative capture and a correctly hash-bound approval for a replacement containing one finding. Calling record with --supersede-capture, --reason and --zero-findings returned 1 with “Nothing written.” Both codex-output-raw.md and findings.json had nevertheless been deleted, while the on-disk capture log still designated attempt 1. Preserved attempt bytes remained available, but the authoritative cycle was broken.
Finding: An invalid replacement invocation destroys the working authoritative evidence before all refusal conditions have been checked. The original capture is not safely retained as the governing capture on failure, and the refusal misreports its effects.
Required correction: Complete replacement validation, including the zero/findings consistency check, before deleting or replacing authoritative files. Commit the replacement designation and derived files coherently, with recoverable failure behavior. Add a supersession-conflict control that asserts the old authoritative bytes, findings and designation remain intact on refusal.

Finding ID: B02-F05
Class: MISSING REQUIREMENT
Artifact: scripts/run_pins.py; scripts/run_review.py
Location: validate_chain; initial_pin_set; check_pins_still_hold
Evidence: A structurally valid amendment removing the governing protocol while retaining the spec passed validate_chain. After the protocol bytes changed, check_pins_still_hold accepted the amended cycle. A different amendment added `specs/nonexistent.md` to the governing set and also passed the pin check: checking iterates only the protocol and spec_files originally recorded in run.json. Amendments contain paths, not hashes for newly introduced artifacts.
Finding: The amendment mechanism can make an inconvenient mandatory governing pin disappear, or declare a new pin that is never checked. Decision L's role separation is implemented as unrestricted set editing. This newly bypasses the runner's previously effective pin checks and compounds the deferred target/run-binding defect B01-F07: input can embed changed protocol text while retaining the old declared digest.
Required correction: Enforce the governing-role constraints of an amendment, including retention of the authoritative protocol for this run. Bind every introduced governing artifact to an exact version/hash and check the complete effective set. Permit a role transfer only under the applicable recorded decision; do not treat a nonempty name and reason as sufficient to erase mandatory governance. Test removed mandatory pins, added missing artifacts and added-artifact drift.

Finding ID: B02-F06
Class: MISSING REQUIREMENT
Artifact: scripts/run_pins.py
Location: validate_chain and pins_for_cycle
Evidence: validate_chain compares effective_cycle only with the preceding amendment, starting at zero. After cycle 01 already existed, a first amendment effective at cycle 1 was accepted; pins_for_cycle then returned the amended set for cycle 01. There is no comparison against already frozen cycles or their recorded pin-set identities. The supplied forward-only control merely uses effective_cycle=2 and asks what replay returns for cycles 1 and 2.
Finding: “Amendments apply forward” means only that amendment numbers increase relative to each other. An amendment appended after review can retroactively change what governed an already completed cycle. This defeats decision L's historical reconstruction and makes the eventual B01-F07 repair depend on rewriteable historical assignments.
Required correction: Bind each frozen cycle to its effective pin-set record and refuse amendments that would change a previously frozen assignment. Validate the effective boundary against existing cycle evidence, not just the preceding amendment number. Add a control appending a backdated amendment after a completed cycle.

Finding ID: B02-F07
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: scripts/run_review.py; scripts/validate_cycle.py
Location: cmd_freeze snapshot loop; _hash_of_declared_file; checks 13–15
Evidence: The runner snapshots implementation diffs and test results, but checks 14 and 15 still hash repo_root/diff_path and repo_root/test_result_path. An implementation fixture passed initially with preserved copies present. Changing only its live diff and test-result files made checks 14 and 15 fail while the preserved copies were unchanged. Check 13 also depends on the current run-level approval record, and the runner does not snapshot the approved plan as part of its implementation artifacts.
Finding: The repair that preserves reviewed bytes is incomplete for implementation cycles. Normal later repairs or revised plan approval can invalidate prior evidence and remove its events from loop calculations. This directly interacts with B01-F11 and the rule that acting on a review must not erase the review that requested the repair.
Required correction: Bind and preserve the complete implementation evidence set, including the applicable approved plan and approval record. Validate historical cycles against those preserved bytes. Add a runner-created implementation fixture that remains valid after subsequent live diff/test changes and a later approved plan version, while snapshot tampering still fails.

Finding ID: B02-F08
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: scripts/run_review.py; scripts/bootstrap_gate.py
Location: check_bootstrap_still_holds; bootstrap_exception_available; cmd_approve_runner
Evidence: check_bootstrap_still_holds returns immediately for any run whose bootstrap_review starts with EXEMPT. In a fixture, an existing exempt run continued to pass that check after a runner approval record existed. The expiry check is performed only when init receives --bootstrap-exempt. Separately, test_bootstrap_gate.py expressly demonstrates that deleting an uncommitted runner approval reopens the exception; cmd_approve_runner writes such an uncommitted record and merely asks the operator to commit it.
Finding: Decision K and ruling 2 say the exception ends immediately at the first runner approval. The implementation blocks new exempt initialization but leaves existing exemptions usable, and its deletion protection starts only after a separate commit. The prompt's “deleting the approval does not reopen it” claim omits a counterexample already accepted by the supplied suite.
Required correction: Re-evaluate exception eligibility whenever exempt execution is attempted after approval. Define and enforce a durable termination boundary consistent with the ruling, or obtain and document a narrower ruling. Add existing-exempt-run and approval-before-commit deletion controls; do not present the latter bypass as successful enforcement.

Finding ID: B02-F09
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: scripts/authority.py; cycle-02 decision J
Location: Module explanation and _fail refusal text
Evidence: The module says approval hashes are “not knowable until the action has been attempted and refused once”. cmd_record obtains them from the existing capture-log authoritative_sha256 and SHA256 of the supplied replacement file; cycle.name is also already known. No nonce or prior-refusal state is checked. A valid approval may be written before the first supersession attempt using those public values. The successful supersession probe used this exact construction.
Finding: The separate-artifact and byte-equality checks work, but the claimed forced out-of-band step does not exist. Predictable hashes do not establish that refusal preceded approval or that approval came from another actor. This overstates the mechanism even though the module correctly disclaims proving who wrote the file.
Required correction: Describe the mechanism as a separately recorded, attributable convention with deterministic byte matching. Remove the unknowability and forced-sequence claims. If a refusal-before-approval sequence is required, implement and test that sequence explicitly, while retaining the CONVENTION_ONLY identity limitation.

Finding ID: B02-F10
Class: UNTESTED RULE
Artifact: Supplied scripts/test_bootstrap_gate.py and scripts/test_run_review.py, as evidence for scripts/authority.py and the covered module set
Location: Hard-coded `scanned` list; authority refusal controls
Evidence: The no-overclaim scanner checks six hard-coded files, omitting findings_format.py, cycle_projection.py, authority.py and run_pins.py even though all four are now covered and explicitly named for this review. The suite reports success for those six files. Authority controls exercise absent approval, empty name, short reason, binding mismatches and wrong schema, but do not exercise the malformed-JSON refusal or absent-timestamp refusal in require_approval. No supplied control establishes the claimed prior-refusal requirement discussed above.
Finding: The broadened review scope did not broaden its prose control, and the claim that every authority refusal is demonstrated is unsupported. Passing counts cannot establish these omitted rules. In particular, the new authority prose containing the unsupported claim is outside the purported safeguard against such claims.
Required correction: Derive the prose scan from the actual covered set, retaining appropriate handling for negated claims, and demonstrate that an injected overclaim in each newly covered module is detected. Add focused controls for the distinct uncovered authority refusals with an otherwise valid approval baseline. Report coverage by rule and scope rather than treating a matching control count as proof of completeness.

Decision assessment: A's filesystem concretisation, B's tree derivation, C's N/A behavior and E's automated DISPUTED boundary remain defensible within their stated limits. D's ACCEPT/later-target distinction holds in the ordinary path, but does not cure the invalid-prerequisite defect. F is materially improved by the demonstrated plan-byte and decision checks. G's current-validity filtering is observable, but its older assertion that filtering can only delay an exit is not justified when invalidation can remove actionable findings. H requires the authority/staging separation and transition replay correction above. I retains the first uncleared exit correctly but fails authorized resumption at the latest boundary. J provides a useful conventional record, not its claimed forced external step. K is not fully enforced at its stated boundary. L solves the specific schema/target deadlock, but its generalized amendment mechanism is insufficiently constrained.

Category accounting: MISSING REQUIREMENT and CONTRADICTORY IMPLEMENTATION MAPPING have findings above, including the persistent repair failures in their original classes. UNTESTED RULE has B02-F10. WRONG OWNERSHIP: no new finding. NONDETERMINISTIC WHERE D POSSIBLE: no new finding. SEMANTIC STEP TOO BROAD: no finding. The deferred cycle-01 findings retain their existing classifications and OPEN states.
