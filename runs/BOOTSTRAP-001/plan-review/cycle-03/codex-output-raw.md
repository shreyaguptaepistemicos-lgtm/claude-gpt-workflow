TARGET_SHA256 ddec223b3a5297a5064f8a4c20fcefcd07cc5d62e12328b71b8cefaf172e1738

I checked all twenty claimed repairs. Eleven hold within the limits stated below; nine are not demonstrated and should remain OPEN. I found two additional defects. Passing the supplied suites does not establish all twenty repair claims.

I verified the SHA-256 of target.json and verified that all ten working-tree artifacts match its recorded hashes. I reviewed the supplied protocol and those matching artifacts. I also inspected the named controls and ran all five auxiliary suites. With Python 3.11.9 and PYTHONUTF8=1, every suite exited 0:

| Suite | Observed [ok] records |
|---|---:|
| scripts/test_validate_cycle.py | 24 |
| scripts/test_run_review.py | 95 |
| scripts/test_ledger.py | 73 |
| scripts/test_bootstrap_gate.py | 42 |
| scripts/test_interfaces.py | 29 |
| Total | 263 |

These are observed success records, not 263 independently demonstrated mechanisms. I checked subprocess exit codes as well as output. An initial run with PYTHONIOENCODING=utf-8 but without PYTHONUTF8=1 crashed in the runner and interface suites because child-output decoding still used cp1252. I discarded those incomplete runs; the subsequent consistent-UTF-8 runs completed. I did not use refresh_counts.py to obtain these numbers and make no finding merely because that utility is outside the covered set.

The reproductions below used temporary repositories containing copies of the reviewed scripts, or explicitly identified in-memory fault injection. They did not modify the reviewed implementation or the authoritative review evidence. The supplied tests are auxiliary evidence rather than hash-bound members of this target; that distinction is addressed separately below.

Repair verdicts:

| Persistent identifier | Verdict | Verification and limit |
|---|---|---|
| B01-F01 | Holds | Freeze counts the shared projection's valid cycles rather than directory numbers. The controls exercise invalid directories without exhausting the budget and four valid cycles exhausting it. Authorized restart semantics are the separate B01-F02 issue below. |
| B01-F02 | REPAIR NOT DEMONSTRATED | Latest-boundary STALLED authorization now works through the runner. Authorization of MAX_4_REACHED still produces controller permission that the runner refuses. |
| B01-F04 | REPAIR NOT DEMONSTRATED | Original pinned specs and implementation identifiers reach the input. An amendment-added governing spec does not. |
| B01-F05 | Holds | Freeze resolves the supplied candidate reference with rev-parse --verify to a full commit SHA, derives its tree from that resolved SHA, and preserves the supplied reference separately. The mutable-reference and unresolvable-reference controls exercise the relevant paths. This fixes ordinary reference movement; it is not an MC-1 protection claim. |
| B01-F07 | REPAIR NOT DEMONSTRATED | Target construction now derives cycle-specific digests, but input composition still uses run-level digests, and validation still accepts arbitrary protocol/spec digest strings. |
| B01-F08 | Holds | The ordinary controller rejects EXEMPT runs; explicit development evaluation carries the development label through the normal status interface, and the runner derives that mode from the run. Seam 9 and the development runner/controller controls exercise this distinction. This verdict concerns the declared EXEMPT classification, not completeness of all run metadata. |
| B01-F09 | Holds | Bootstrap evaluation rechecks the recorded evidence hashes and frozen target hash as well as covered component hashes. The controls delete evidence and alter both output and target after approval. This establishes subsequent drift detection while the checks run faithfully; it does not authenticate the reviewer or approver. |
| B01-F11 | REPAIR NOT DEMONSTRATED | Invalidated ACCEPT prerequisites are replayed correctly, but nonexistent cycles still authorize ledger transitions, and the named nonexistent-cycle control can pass with the horizon repair removed. |
| B01-F12 | Holds | Respond, resolve and reopen call the raising-cycle ordering check. The pre-raise controls exercise refusals while same/later-cycle operations remain available. This checks ordering relative to the raising cycle; it does not establish arbitrary event-history chronology. |
| B01-F14 | REPAIR NOT DEMONSTRATED | Init and freeze enforce the field, and BOOTSTRAP-001 honestly labels its reconstruction. The controller can still emit an authoritative protocol outcome for a run without it. |
| B02-F01 | Holds | The loose-boundary reconciliation runs regardless of whether another block parsed. The one-space-indented block is detected and refused rather than silently omitted. Mixed canonical/noncanonical and lone noncanonical controls exercise this repair. |
| B02-F02 | Holds | The parser accepts the recurrence form without Class, and record resolves its class from the ledger. Unknown identifiers, incompatible Class/Status combinations and unrecognized statuses are refused by the supplied controls. |
| B02-F03 | Holds | Ledger ID validity comes from findings_format.canonical_id_grammar(); cycle extraction is separate. The zero-, one- and two-letter identifier controls exercise the former divergence. |
| B02-F04 | REPAIR NOT DEMONSTRATED | Ordinary validation refusal preserves the old authoritative files, but the replacement is still not transactional. Fault injection between the renames leaves mixed generations and an old designation. |
| B02-F05 | REPAIR NOT DEMONSTRATED | Dropping the protocol and adding an unhashed/drifted pin are refused. Extra keys in added_pin_hashes can nevertheless replace the hash of a retained governing protocol. |
| B02-F06 | REPAIR NOT DEMONSTRATED | Recorded path sets catch the tested backdated amendment within one review directory. They do not protect the other review directory in the same run or compare frozen pin hashes. |
| B02-F07 | Holds | Current freeze preserves the diff, results, approved plan and approval record. Check 13 and checks 14–15 use those copies when present. Seam 11 changes the live evidence and then corrupts a preserved result, demonstrating survival of ordinary later work and continued detection of snapshot corruption. The legacy live-file fallback is a limitation, not evidence that current snapshots are technically protected. |
| B02-F08 | REPAIR NOT DEMONSTRATED | Normal exempt init/freeze expiry and successful approval committing work. Failure to read git history is still interpreted as no historical approval, making the expiry check fail open. |
| B02-F09 | Holds | authority.py explicitly disclaims forced sequencing, proven authorship and an independent write boundary. The former claim that the hashes cannot be computed in advance is identified as false, not asserted as current behavior. |
| B02-F10 | Holds | The prose scan takes its file list from covered(), including the four formerly omitted modules, and the malformed-JSON and absent-timestamp authority controls now exercise their refusals. This verifies the scope and added controls, not the claim that a keyword scan can certify all prose. |

Finding ID: B01-F02
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/run_review.py:694 refuses whenever valid_used >= MAX_CYCLES, before consulting check_loop_not_terminated. scripts/loop_state.py explicitly describes clearing MAX_4_REACHED as a human-authorized continuation and returns CONTINUE when that latest boundary is cleared. In a temporary fixture with four valid cycles, progress at every intervening boundary and one remaining OPEN finding, I recorded an authorization naming after_valid_cycle=4 and outcome=MAX_4_REACHED. The controller exited 0 with LOOP_STATUS: CONTINUE, labeled as development evidence. Freeze exited 1 with "has already used its 4-cycle budget". Seam 10 exercises STALLED at two valid cycles, so it cannot expose this ordering conflict.
Finding:
The repair fixes one terminal outcome, but the runner still does not act on the permission the controller says it has granted at the budget boundary. The general repair claim and decision I are not demonstrated. The code also lacks a coherent distinction between restarting an authorized loop and exceeding the governing protocol's four-valid-cycle maximum within the same loop.
Required correction:
Define and implement one consistent, explicitly authorized restart/budget transition in both components. Preserve the protocol's four-cycle limit for an automated loop; do not silently extend it. If authorization starts another loop, record that loop and its budget explicitly. If the current authorization format cannot authorize such a restart, the controller must not announce permission that the runner cannot honor. Add an end-to-end budget-boundary test with matching, missing and mismatched authorization.

Finding ID: B01-F04
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/run_review.py:956 constructs spec_texts by iterating run.get("spec_files", []), filtering that original list through _gov. It never iterates newly added governing paths. In a runner-created temporary run, I completed cycle 01, added specs/extra.md with a valid SHA-256 through an amendment effective at cycle 02, and froze cycle 02 successfully. Its target included specs/extra.md in governing_pins and governing_pin_hashes. Its codex-input.md did not contain the unique requirement text in that file. The named B01-F04 control checks an original spec, and the B02-F05 added-pin control checks drift refusal; neither checks successful input composition after a valid addition.
Finding:
The reviewer can still be asked to judge against a governing specification it was not given. The original missing-spec defect survives on the amendment path introduced by these repairs.
Required correction:
Compose the governing specification content from the complete effective path-to-hash map for this cycle, excluding only the separately supplied protocol. Use those same effective hashes when checking and labeling the embedded content. Add a successful amendment-addition control asserting the complete new specification text appears in the input, alongside a drift refusal control.

Finding ID: B01-F07
Status: REPAIR NOT DEMONSTRATED
Evidence:
The actual reviewed cycle demonstrates the mismatch without any mutation: target.json records spec_sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 for the empty non-protocol governing set, while codex-input.md line 6 records SPEC_SHA256 ad7f1099b66263123795dc2bf15f8275ad290bf91cdb0f5efaa09a942a8f321f from run.json. compose_input still reads run['protocol_sha256'] and run['spec_sha256']; cmd_freeze passes the original run object. Separately, validate_cycle.py checks that these target fields exist but does not validate their digests against the cycle's pins. In a temporary plan fixture, setting both fields to the literal "not-a-hash" before computing target.sha256 still produced MC-2 exit 0. The named repair controls inspect target construction and preservation of an older target; they do not test the input header or rejection of false governing digests.
Finding:
The prompt's statement that the recorded hashes describe this cycle's pin set is false for the input under review. Deriving target values at freeze is also not the requested validation of the relationship: a self-consistent target checksum does not establish correctness of its protocol/spec fields.
Required correction:
Use the frozen cycle's effective digest values throughout target and input composition. Validate the governing digest relationships against that cycle's effective pins, with explicit historical handling where older evidence lacks newer fields. Add negative controls for syntactically valid but wrong digests as well as malformed digests, and an amendment test comparing the target with its actual composed header. Do not reinterpret historical cycles under the latest pin set.

Finding ID: B01-F11
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/cycle_projection.py:101 sets the default horizon to max(known)+1, and authorizes at line 128 accepts every non-invalid number at or below it. Projection([1, 3], {}) therefore authorizes nonexistent cycle 02 and nonexistent cycle 04. In a temporary repository with only valid cycle-01 and cycle-03 directories, ledger raise in 01, ACCEPT in nonexistent 02, and resolve in 03 all exited 0. Ledger show reported RESOLVED; the controller, which uses only valid cycles, retained the finding OPEN and returned STALLED.

The supplied nonexistent-cycle control in scripts/test_ledger.py accepts in cycle 99 and attempts resolution in that same cycle 99. In an isolated copy I replaced the horizon authorization expression with unconditional True. The control's operation still refused resolution, solely because acceptance and resolution were in the same cycle. Thus this control does not demonstrate the claimed nonexistent-cycle refusal, and the prompt's mutation-testing assurance is false for this case.

There is another incomplete prerequisite calculation: last_authorized retains its previous ACCEPT result across REOPENED, even though replay disarms acceptance there. For RAISED(1), ACCEPT(1), DEMONSTRATED(2), REOPENED(3), replay returns OPEN while last_authorized(..., 'ACCEPT', ...) still returns the cycle-01 event. Ledger resolve uses that stale result as its precondition.
Finding:
The repair correctly withdraws a resolution whose ACCEPT was invalidated, but it does not establish one shared authoritative transition history. Nonexistent-cycle events still authorize ledger closures that the controller rejects, and the acceptance lookup can return an acceptance that is no longer in force. A named control passes for an unrelated refusal.
Required correction:
Use actual authoritative cycle membership for effective transitions. If provisional events must be stored, distinguish storage from authority and exclude them from effective state until their prerequisite cycle is valid. Make replay and prerequisite lookup share the same transition state, including invalidation of an ACCEPT on reopen. Replace the cycle-99 control with one that would otherwise have legal later-cycle resolution, and require it to fail when the membership repair is removed. Add a missing-interior-cycle test and a reopen-without-new-ACCEPT test that check both command outcome and controller state.

Finding ID: B01-F14
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/run_review.py:250 validates mc1_enforcement in load_run, which freeze calls. scripts/loop_state.py:291 independently reads run.json through run_classification and examines only bootstrap_review. It never applies that metadata validation. I created a normal, bootstrap-approved protocol run, froze and recorded a valid zero-finding cycle, then removed only mc1_enforcement from its run.json. The ordinary controller exited 0 with the unqualified line "LOOP_STATUS: CONVERGED". The named controls remove or corrupt the field before freeze, not before authoritative controller use. BOOTSTRAP-001's reconstructed metadata itself is explicitly and appropriately labeled.
Finding:
MC1_ENFORCEMENT is required for newly initialized and subsequently frozen runs, but not for every protocol run whose evidence is consumed to produce an authoritative outcome. The repair repeats the earlier pattern of enforcing the field at one entry point while leaving another consumer permissive.
Required correction:
Share mandatory run-metadata validation across authoritative consumers, including the controller and recording path where applicable. Refuse an authoritative outcome when the required enforcement status is missing or unrecognized. Preserve the honest reconstructed provenance for historical records. Add controller-level missing-field and invalid-value controls after a completed protocol cycle, checking that no authoritative LOOP_STATUS is emitted.

Finding ID: B02-F04
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/run_review.py:1325 replaces the authoritative raw file, line 1326 separately replaces findings.json, and only afterward writes the new capture-log designation. The nearby implementation comment expressly admits this is not a transaction. In a temporary, valid, authorized supersession, I injected OSError on the second os.replace. The resulting state was: raw capture changed, findings.json unchanged, authoritative designation still attempt 1, and .findings.json.staged left behind. The existing refusal control tests a pre-swap --zero-findings conflict; the staging-debris assertion is reached after a successful swap. Neither interrupts a rename or the later pointer write. The review prompt nevertheless calls the repair "staging and an atomic swap".
Finding:
Ordinary refusal no longer deletes the old evidence, but the required transactional supersession is not implemented. A partial replacement still leaves the authoritative representation internally inconsistent. Preserving both attempts makes recovery possible; it does not make the designation change atomic. The prompt claims a stronger repair than the code explicitly says it provides.
Required correction:
Fully stage and validate an immutable capture generation, then atomically replace a single authoritative pointer that every consumer follows, or implement an equivalent recoverable transaction with a defined commit point. Do not depend on separate mutable raw/findings/log files all changing together. Test interruption at every publication boundary and verify consumers observe a complete old or new generation, with deterministic recovery. Correct the prompt's atomicity claim until that mechanism is demonstrated.

Finding ID: B02-F05
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/run_pins.py validates added_pin_hashes only for paths in new_pin_set minus current. It does not reject other keys. pin_hashes_for_cycle at line 283 then applies the entire supplied dictionary using out.update. I passed validate_chain an otherwise valid amendment adding "extra", with added_pin_hashes containing both extra's digest and a replacement digest for the retained "proto" path. Validation returned normally, and pin_hashes_for_cycle returned the replacement protocol digest. The declared affected_artifacts contained only "extra". The supplied controls remove the protocol path or omit/corrupt an added path's hash; they do not attempt to change a retained pin through this dictionary.
Finding:
Keeping the governing protocol's path is not sufficient to constrain its role and version. An amendment can change the protocol bytes accepted by the pin checker without declaring a protocol change, without removing the protocol path and without changing run.json. The repair's role constraint can therefore be bypassed through its new hash mechanism.
Required correction:
Require the keys of added_pin_hashes to match exactly the newly added paths, and reject hash overrides for retained or unrelated paths. Apply only validated additions during replay. Any permitted version change needs an explicit, validated transition with the appropriate role constraints; it must not arrive as an undeclared dictionary key. Add a control that supplies a retained-protocol override alongside a legitimate new pin and requires refusal for that override.

Finding ID: B02-F06
Status: REPAIR NOT DEMONSTRATED
Evidence:
cmd_freeze passes only its current review_dir to check_pins_still_hold. frozen_assignments therefore examines only that directory, although pin-amendments.json belongs to the whole run. In a temporary run I froze plan-review/cycle-01 under protocol plus spec, appended an amendment effective at cycle 1 removing the spec, and froze implementation-review/cycle-01. Implementation freeze exited 0. The earlier plan target still recorded both paths, while the same run-level amendment history now assigned only the protocol to cycle 1. The earlier frozen assignment was never examined on this path.

In addition, frozen_assignments retains only governing_pins, and check_frozen_assignments compares only path lists, discarding governing_pin_hashes. A changed digest with unchanged membership is invisible to this check; the retained-pin override described in B02-F05 supplies one route. The named controls change membership within the plan-review directory only.
Finding:
The prospective-only guarantee holds for the tested directory and path-set change, not for the entire run or the full identity of its governing artifacts. A later operation can accept amendment history contradicting a previously frozen cycle without modifying that cycle's evidence.
Required correction:
Define the effective-cycle coordinate unambiguously across plan and implementation reviews. Validate amendments against every affected frozen cycle in the run, preserving review identity rather than collapsing equal cycle numbers from separate loops. Compare the effective path-to-hash assignments, not just membership. Add a cross-review backdating control and a same-path/different-hash control; both must refuse while legitimate prospective amendments remain usable.

Finding ID: B02-F08
Status: REPAIR NOT DEMONSTRATED
Evidence:
scripts/bootstrap_gate.py:321 reads historical approvals with git log. On any nonzero return code it returns [], the same value used for a successful search with no historical approvals. bootstrap_exception_available then returns True when no live record is found. With an empty live list and a fault-injected git result of exit 128, the actual functions reported the exception available. The supplied controls exercise successful history reads before/after approval deletion, successful approval commits, and exempt init/freeze after expiry. They do not exercise inability to read the historical evidence on which deletion resistance depends.
Finding:
The successful-path repairs hold, but the claimed one-way expiry still becomes permission when its historical check cannot run. An unavailable history is not evidence that no approval ever existed. This is the review's "check never ran" failure mode at the authority boundary.
Required correction:
Distinguish a successful empty history query from an unsuccessful query. If history cannot be inspected, refuse reliance on the bootstrap exception and report the reason. Add a control combining no live approval file with a failed history query, and require init/freeze to refuse exemption. Also exercise approval staging/commit failures. Git history is a defensible conventional durability mechanism for ordinary deletion, provided read failure is not treated as absence; it is not a technical one-way boundary against history rewriting or all interruption windows.

Finding ID: B03-F01
Class: MISSING REQUIREMENT
Artifact: scripts/run_review.py; scripts/loop_state.py; scripts/cycle_projection.py
Location: run_review.py:472–529, particularly the return-code check at line 500; cycle_projection.py:213; loop_state.py main exception handling.
Evidence:
check_loop_not_terminated refuses controller exit code 2 and recognized terminal status strings. It does not require exit code 0 or a recognized CONTINUE result. The newly added replay raises UnknownEvent, while loop_state.main catches only CannotCalculate. In a temporary runner-created cycle with one ledger finding, I added an unknown event to that finding's history. The controller exited 1 with an UnknownEvent traceback and emitted no LOOP_STATUS. A subsequent ordinary freeze nevertheless exited 0 and created cycle-02. This is an executed runner/controller probe, not merely a hypothetical missing return code.
Finding:
Failure to calculate loop state is interpreted as permission to open another cycle. The new defensive replay exception becomes fail-open behavior at the runner boundary, contradicting the stated requirement that an undeterminable loop must not continue.
Required correction:
Require successful controller completion and exactly one recognized permission result before continuing. Refuse nonzero exit codes, missing/malformed/unknown statuses and conflicting status lines. Translate known evidence/replay errors into CannotCalculate for a useful diagnosis, while keeping the caller independently fail-closed. Add an end-to-end control for the UnknownEvent path and controls for nonzero exit/missing status; assert that no new cycle directory is created.

Finding ID: B03-F02
Class: CONTRADICTORY IMPLEMENTATION MAPPING
Artifact: runs/BOOTSTRAP-001/plan-review/cycle-03/codex-input.md; runs/BOOTSTRAP-001/plan-review/cycle-03/target.json
Location: codex-input.md:142–147, especially "The suites are in the target"; target.json plan_files.
Evidence:
target.json binds ten artifacts, all matching the declared covered production set. None of test_validate_cycle.py, test_run_review.py, test_ledger.py, test_bootstrap_gate.py or test_interfaces.py appears in plan_files. The composed input also does not embed their contents. I could inspect and run the working-tree suites, but their versions are not bound by the quoted TARGET_SHA256. Thus the observed 263 success records are reproducible evidence from the auxiliary suites I ran, not evidence that this target freezes those suites or their claimed mutation results.
Finding:
The repair-verification instructions describe unbound auxiliary controls as members of the frozen target. That overstates what the target hash establishes and leaves a later reader unable to identify the exact control versions from this review target alone.
Required correction:
Correct the scope statement. If these controls are to substantiate the frozen repair claims, preserve their exact versions through a separate hash-bound auxiliary-evidence manifest or an explicitly supported extension of the review target. Do not silently widen the gate's covered production set: target_drift currently rejects extra target artifacts, so the chosen representation must be coordinated. Whether refresh_counts.py itself should enter the covered set remains Alex Zamurko's decision; no such scope change is required merely to describe the current evidence honestly.

Assessment of the declared decisions and the two requested failure modes:

- A, B, C and E retain the stated cycle-02 acceptance within their limits. I found no new reason here to change those dispositions.
- D remains qualified. Replay of the invalidated-ACCEPT example is repaired, but the missing-cycle and stale-acceptance paths in B01-F11 still prevent agreement between ledger authority and controller state.
- F is materially improved. The reviewed implementation now preserves and uses the approved-plan evidence in the ordinary snapshot path, and the controls exercise plan-content and approval-decision checks.
- G remains qualified, exactly as the prompt warns. Ignoring invalid resolutions can delay an exit, but ignoring a RAISED event or a REOPENED event can remove an actionable finding. Therefore the assertion in loop_state.py's opening documentation that this "can only ever delay an exit, never manufacture one" remains unjustified. The correct claim is that the calculation excludes invalid-cycle events, not that this exclusion is monotonically conservative. This is the already-declared outstanding qualification, not a newly invented repair claim.
- H is not satisfied by the narrower successful-path preservation repair. B02-F04 still leaves a mixed authoritative generation after interruption.
- I is only partially repaired. Latest STALLED continuation works; the budget-boundary contradiction is B01-F02.
- J is now described at its actual conventional strength. The B02-F09 correction removes the asserted forced external step. Sharing its commit with B02-F10 is defensible: expanding the scan and correcting the newly visible prose are coupled changes. I found no additional defect caused merely by that shared commit.
- K improves ordinary deletion resistance and checks existing exemptions at freeze, but remains incomplete on inability to inspect history, as B02-F08 demonstrates. Committing the record with --only appropriately avoids including unrelated staged work. A successful commit is durable against ordinary working-tree deletion; the command is not an atomic transaction from human decision through filesystem write and git commit. Its control's phrase "no uncommitted window" overstates that successful-path observation.
- L remains qualified. The specific bootstrap deadlock is relieved, but added governing content, retained-pin hashes and cross-review history still expose the failures recorded in B01-F04, B02-F05 and B02-F06.

For MC-2, the supplied controls exercise the common file-existence mechanism through check 4, nonempty evidence, target digest mismatch, duplicate identifiers, missing commits, bad artifact hashes, absent input binding and implementation checks 11–15. I do not re-report the known grouping of checks 1–4. These controls do not establish the missing protocol/spec digest relationship in B01-F07. A PASS for the implemented checks is not proof that every stated requirement has a check.

For runner, authority and projection refusals, I do not endorse the suites' blanket closing claims that every refusal is reachable or every rule demonstrated. The nonexistent-cycle control demonstrably survives removal of its purported fix. The supersession controls do not test interrupted publication, the resumption seam covers STALLED rather than the exhausted budget, and the history controls omit query failure. The added malformed-approval and absent-timestamp controls are real and relevant, but do not establish approver identity or an out-of-band sequence.

For each of the five suites, checking its process exit code detects an uncaught crash; checking its observed count against the independently stated expectation detects a shortened run in this review. The current observed counts match 24/95/73/42/29. The suites' final success strings alone do not establish completion of a fixed inventory: they follow accumulated failure lists and can survive removal or skipping of a control. Counts also cannot show that the intended refusal caused a test to pass, as B01-F11 demonstrates. A durable completeness claim needs an independently maintained expected control inventory and its execution results, not only a refreshed count agreeing with another consumer of that count. I have not inspected or certified the out-of-target count-refresh and prompt-checking pipeline.

The principal remaining claims stronger than their evidence are the prompt's atomic-swap claim, its assertion that the suites belong to the target, the mutation assurance contradicted by the nonexistent-cycle control, and the already-qualified monotonicity claim under G. The runner's opening "Write-once evidence" description also needs to reflect authorized supersession: its statement that raw output is never overwritten and record refuses whenever raw output is present does not describe the current capture-log-based replacement behavior. None of these mechanisms establishes technical immutability or proves that the retained output came from the recorded input.

New-finding category accounting: MISSING REQUIREMENT has B03-F01; CONTRADICTORY IMPLEMENTATION MAPPING has B03-F02. I found no additional new findings classified WRONG OWNERSHIP, NONDETERMINISTIC WHERE D POSSIBLE, SEMANTIC STEP TOO BROAD or UNTESTED RULE. The nine recurrences retain their existing ledger classifications; their blocks intentionally do not reassert Class.

The explicit repair verdict is therefore: demonstrated—B01-F01, B01-F05, B01-F08, B01-F09, B01-F12, B02-F01, B02-F02, B02-F03, B02-F07, B02-F09 and B02-F10. Not demonstrated—B01-F02, B01-F04, B01-F07, B01-F11, B01-F14, B02-F04, B02-F05, B02-F06 and B02-F08. The latter nine remain OPEN, alongside the two new findings. I make no claim that the review has converged.
