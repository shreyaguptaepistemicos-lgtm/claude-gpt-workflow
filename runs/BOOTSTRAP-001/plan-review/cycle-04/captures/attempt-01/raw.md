TARGET_SHA256 0fa90c4b80cc1650c58db1574daa26e64b349a858f59bb21485822949c7e9ff9

**Five claimed repairs remain OPEN. The review has not converged.**

I verified the target digest, all ten artifact hashes, the protocol hash, and the auxiliary manifest and suite hashes. All five control suites exited successfully under WSL Python. Additional probes reproduced the failures below. Production files and review records remain unchanged.

## Repair assessment

“Demonstrated” below means supported by the inspected implementation and passing controls for the stated repair. I did not independently repeat every claimed mutation experiment.

| Finding | Assessment |
|---|---|
| B01-F02 | **OPEN:** clearing STALLED at the fourth valid cycle restores CONTINUE. |
| B01-F04 | Demonstrated: amended specifications enter the composed input. |
| B01-F07 | **OPEN:** header repaired; governing-digest validation still accepts invalid evidence. |
| B01-F11 | **OPEN:** a backdated acceptance bypasses the reopening repair. |
| B01-F14 | **OPEN:** missing `run.json` bypasses the metadata check. |
| B02-F04 | **OPEN:** an earlier non-atomic log write defeats interruption recovery. |
| B02-F05 | Demonstrated: retained-pin hash overrides are rejected and excluded from replay. |
| B02-F06 | Demonstrated for recorded assignments: both loops and recorded versions are checked. |
| B02-F08 | Demonstrated: failed history queries withhold the exception. |
| B03-F01 | Demonstrated for the reported controller failures and conflicting statuses. |
| B03-F02 | Demonstrated as an auxiliary evidence record; it is not an MC-2-enforced binding. |

## Recurring findings

Finding ID: B01-F02
Status: REPAIR NOT DEMONSTRATED
Artifact: scripts/loop_state.py
Location: scripts/loop_state.py:534
Evidence:
A fixture with four MC-2-valid cycles had OPEN counts 3, 2, 1, 1. Repairs were demonstrated in cycles 2 and 3; cycle 4 stalled. With an authorization naming STALLED at valid-cycle boundary 4, the real controller exited 0 and reported:

```text
VALID_CYCLE_COUNT: 4
STALLED at n=4 cleared by recorded authorization: Fixture human
LOOP_STATUS: CONTINUE
```

It then instructed the operator to open another cycle. The runner’s budget check still refuses that continuation.

Finding:
The repair prevents authorization of the literal MAX_4_REACHED outcome, but does not prevent authorization from extending an exhausted budget through another outcome. STALLED precedes the budget test, and clearing it restores CONTINUE without checking remaining capacity. The controller and runner still disagree.

The named control tests a boundary that already produces MAX_4_REACHED. Its mismatched STALLED authorization does not exercise a boundary that actually produces STALLED.

Required correction:
Before any cleared outcome becomes CONTINUE, enforce the four-valid-cycle ceiling. Add a control with actual STALLED at boundary 4 and matching authorization; verify that the controller grants no continuation and agrees with the runner.

---

Finding ID: B01-F07
Status: REPAIR NOT DEMONSTRATED
Artifact: scripts/validate_cycle.py
Location: scripts/validate_cycle.py:331
Evidence:
I constructed a target containing both modern governing fields:

```json
{
  "governing_pins": ["missing-protocol.md"],
  "governing_pin_hashes": {
    "missing-protocol.md": "not-a-hash"
  },
  "protocol_sha256": "not-a-hash",
  "spec_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

The referenced protocol file did not exist. With the target digest and input binding recomputed, the validator exited 0, reported check 9 PASS, and returned MC2_CONFORMANCE: PASS.

Finding:
The gate checks agreement between asserted fields rather than whether they identify valid governing artifacts. `_owner` accepts any map entry whose value equals `protocol_sha256`, including a non-digest. It neither establishes protocol identity nor verifies the referenced bytes.

This reproduction does not use the disclosed legacy-field deletion exception. The named negative controls change one assertion while retaining the other, leaving consistent false assertions untested.

Required correction:
Validate digest syntax, establish which governing artifact is the protocol, and verify the governing versions against preserved evidence and the applicable run-pin history. Preserve legitimate historical evidence through an explicit compatibility rule. Add a control where both assertions agree on invalid or nonexistent evidence.

---

Finding ID: B01-F11
Status: REPAIR NOT DEMONSTRATED
Artifact: scripts/ledger.py; scripts/cycle_projection.py
Location: scripts/ledger.py:340; scripts/cycle_projection.py:247
Evidence:
With cycles 1–4 valid, these ledger commands all exited 0:

```text
RAISED(1)
ACCEPT(1)
DEMONSTRATED(2)
REOPENED(3)
ACCEPT(2)          recorded after REOPENED(3)
DEMONSTRATED(4)
```

The final stored state was RESOLVED. No acceptance belonged to the reopening cycle or a later cycle.

Finding:
The ledger permits an acceptance backdated before the reopening, while replay and `last_authorized` process insertion order. The appended cycle-2 acceptance therefore re-arms a finding reopened in cycle 3.

The named reopening control demonstrates refusal when no additional ACCEPT exists. It does not test whether a subsequently appended ACCEPT is causally eligible.

Required correction:
Reject dispositions that predate the transition they respond to. Make replay validate cycle ordering and prerequisites consistently, including existing out-of-order histories. Add this backdated-acceptance sequence as a negative control.

---

Finding ID: B01-F14
Status: REPAIR NOT DEMONSTRATED
Artifact: scripts/loop_state.py
Location: scripts/loop_state.py:351
Evidence:
On the same completed valid-cycle fixture:

```text
run.json contains valid mc1_enforcement:
    exit 0, LOOP_STATUS: CONVERGED

run.json exists but mc1_enforcement is absent:
    exit 2, no LOOP_STATUS

run.json is absent:
    exit 0, LOOP_STATUS: CONVERGED
```

Finding:
Missing `run.json` returns classification UNKNOWN before the shared metadata check runs. UNKNOWN subsequently receives an unqualified outcome. Removing the entire metadata record bypasses the refusal demonstrated for removing one field.

The controls cover missing and unrecognized enforcement values inside an existing file, but not absence of that file.

Required correction:
Refuse authoritative calculation when run metadata or classification cannot be established. Any explicitly supported legacy analysis must carry a non-authoritative label. Add a missing-file control alongside the missing-field controls.

---

Finding ID: B02-F04
Status: REPAIR NOT DEMONSTRATED
Artifact: scripts/run_review.py
Location: scripts/run_review.py:1384
Evidence:
Before the new atomic designation replacement at line 1556, recording still calls ordinary `write_lf` on `capture-log.json` at line 1384, and again on the invalid-capture path at line 1389.

In an isolated supersession probe, with approval checking stubbed to succeed, I injected an interruption after the first log write opened and truncated the file. The log contained partial JSON. Calling `publish_from_designation` then refused:

```text
capture-log.json is not valid JSON
```

The old generation remained on disk, but recovery could no longer read its designation.

Finding:
The claimed single atomic commit point is preceded by a destructive write to the same authoritative pointer file. An interruption during preparation can destroy the previous designation before the atomic replacement is reached.

The named controls corrupt working copies while retaining a readable designation. They demonstrate publication recovery, not survival of this earlier write boundary.

Required correction:
Make every capture-log update atomic, or separate attempt journaling from the authoritative designation so preparation cannot destroy the last committed pointer. Inject failures during each log-write boundary and verify deterministic recovery.

## Conclusion

The five recurrences above are demonstrated failures, not speculative concerns. The six other claimed repairs are supported within the scope stated in the assessment table. I did not re-verify the six earlier repairs explicitly excluded from this cycle.

**I make no claim that the review has converged. These unresolved findings should reach the human reviewer when cycle 04 closes.**
