# Human review package — BOOTSTRAP-001, plan review

Assembled by `scripts/approval_package.py` from the run's own records. Every figure below is quoted from the tool that owns it; none is recomputed here.

**This package decides nothing.** The decision is recorded separately, by a person, with `bootstrap_gate.py record`. §7.3 permits exactly three outcomes: `APPROVE`, `RETURN_FOR_REWORK`, `REJECT`.

## MC-1 enforcement status

`CONVENTION_ONLY`

Every check in this layer is detection that holds while the checks run faithfully and nobody edits the records they read. The same writable code performs the checks on itself. Nothing here is technically enforced.

Reconstructed rather than recorded at the time:

```text
{
  "added": "2026-09-11",
  "reconstructed": true,
  "why": "This run was created on 9 September, before cmd_init wrote mc1_enforcement. The field was absent and nothing required it when the run was consumed, which is B01-F14. It is added now so the requirement holds for every run rather than only for runs that already met it.",
  "basis": "CONVENTION_ONLY was the enforcement status on 9 September and has not changed since. One machine, one account, no write boundary. The value is reconstructed from that fact, not from a record kept at the time, because no such record was kept.",
  "authority": "Alex Zamurko, 10 September 2026: 'For BOOTSTRAP-001, record CONVENTION_ONLY as explicitly reconstructed metadata, not as if it had existed originally.'",
  "note": "Cycles 01 and 02 were frozen and reviewed while this field was absent. Adding it does not change what governed them and is not a claim that it was present at the time."
}
```

> **Development evidence, not a protocol outcome.** This run is marked `NOT_A_PROTOCOL_CYCLE`. Nothing in this package may be cited as a protocol result.

## Loop status and valid iteration count

The controller refuses to state an authoritative loop result for this run, and says why:

```text
REFUSED: BOOTSTRAP-001 is marked EXEMPT — BOOTSTRAP / DEVELOPMENT EVIDENCE, NOT_A_PROTOCOL_CYCLE

  Its cycles are development evidence. A loop state computed over them is not a
  protocol outcome, and nothing in the output would have said so.

  Pass --development to compute it anyway. The result is labelled and must not be
  cited as an authoritative protocol result.
```

Recomputed with `--development`. The result is labelled and is not a protocol outcome:

```text
loop state — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review

DEVELOPMENT EVIDENCE — NOT A PROTOCOL OUTCOME
  EXEMPT — BOOTSTRAP / DEVELOPMENT EVIDENCE, NOT_A_PROTOCOL_CYCLE
  The status below describes bootstrap evidence and does not establish a protocol
  result. §2 and §3 reserve authoritative outcomes to valid protocol cycles.

cycles
  cycle-01  VALID    -> n=1
  cycle-02  VALID    -> n=2
  cycle-03  VALID    -> n=3
  cycle-04  VALID    -> n=4

VALID_CYCLE_COUNT: 4

authoritative findings
  cycle-01  18 finding(s): B01-F01, B01-F02, B01-F03, B01-F04, B01-F05, B01-F06, B01-F07, B01-F08, B01-F09, B01-F10, B01-F11, B01-F12, B01-F13, B01-F14, B01-F15, B01-F16, B01-F17, B01-F18
  cycle-02  15 finding(s): B01-F02, B01-F08, B01-F09, B01-F11, B01-F14, B02-F01, B02-F02, B02-F03, B02-F04, B02-F05, B02-F06, B02-F07, B02-F08, B02-F09, B02-F10
  cycle-03  11 finding(s): B01-F02, B01-F04, B01-F07, B01-F11, B01-F14, B02-F04, B02-F05, B02-F06, B02-F08, B03-F01, B03-F02
  cycle-04  5 finding(s): B01-F02, B01-F07, B01-F11, B01-F14, B02-F04
  every recorded finding is accounted for in the ledger

boundaries, in order
  n=1 (cycle-01)  OPEN 18  DISPUTED 0  RESOLVED 0   -> CONTINUE
  n=2 (cycle-02)  OPEN 20  DISPUTED 0  RESOLVED 8   -> CONTINUE
  n=3 (cycle-03)  OPEN 17  DISPUTED 0  RESOLVED 13   -> CONTINUE
  n=4 (cycle-04)  OPEN 5  DISPUTED 0  RESOLVED 25   -> MAX_4_REACHED

§6 sets and exits at the governing boundary, n=4
  OPEN_4           5  B01-F02, B01-F07, B01-F11, B01-F14, B02-F04
  DISPUTED_4       0  -
  RESOLVED_4      25  B01-F01, B01-F03, B01-F04, B01-F05, B01-F06, B01-F08, B01-F09, B01-F10, B01-F12, B01-F13, B01-F15, B01-F16, B01-F17, B01-F18, B02-F01, B02-F02, B02-F03, B02-F05, B02-F06, B02-F07, B02-F08, B02-F09, B02-F10, B03-F01, B03-F02
  OPEN_3          17  B01-F02, B01-F04, B01-F07, B01-F11, B01-F14, B02-F01, B02-F02, B02-F03, B02-F04, B02-F05, B02-F06, B02-F07, B02-F08, B02-F09, B02-F10, B03-F01, B03-F02
  RESOLVED_NEW_4  12  B01-F04, B02-F01, B02-F02, B02-F03, B02-F05, B02-F06, B02-F07, B02-F08, B02-F09, B02-F10, B03-F01, B03-F02
  DISPUTED_NEW_4   0  -
  C STALLED                      |OPEN_4| >= |OPEN_3| (5 >= 17) and no new resolved/disputed   no
  D MAX_4_REACHED                VALID_CYCLE_COUNT = 4                  yes

LOOP_STATUS: MAX_4_REACHED  [DEVELOPMENT EVIDENCE — NOT A PROTOCOL OUTCOME]
Budget exhausted with findings still open. Proceed to human plan review with the unresolved matters exposed.
```

## Findings

§7.2 requires disputes and unresolved findings to be presented separately. They are separate headings below; the full ledger follows both.

### Unresolved findings — the human decides each one

§7.2: the human determines whether each requires correction, is explicitly waived or accepted, or causes rejection of the plan.

- **B01-F02** · CONTRADICTORY IMPLEMENTATION MAPPING · S6
  - repair status: `IMPLEMENTED_AWAITING_DEMONSTRATION` — descriptive, not a lifecycle state
  - found by: `CODEX_REVIEW`
- **B01-F07** · MISSING REQUIREMENT · MC-2
  - repair status: `IMPLEMENTED_AWAITING_DEMONSTRATION` — descriptive, not a lifecycle state
  - found by: `CODEX_REVIEW`
- **B01-F11** · CONTRADICTORY IMPLEMENTATION MAPPING · S6
  - repair status: `IMPLEMENTED_AWAITING_DEMONSTRATION` — descriptive, not a lifecycle state
  - found by: `CODEX_REVIEW`
- **B01-F14** · MISSING REQUIREMENT · MC-1
  - repair status: `IMPLEMENTED_AWAITING_DEMONSTRATION` — descriptive, not a lifecycle state
  - found by: `CODEX_REVIEW`
- **B02-F04** · CONTRADICTORY IMPLEMENTATION MAPPING
  - repair status: `IMPLEMENTED_AWAITING_DEMONSTRATION` — descriptive, not a lifecycle state
  - found by: `CODEX_REVIEW`

### Disputes — the human adjudicates

§7.1: a dispute is a Codex finding plus a Claude `REJECT_WITH_REASON`.

None.

### Resolved findings

25 resolved.

`RESOLVED` under §5 means a repair was demonstrated in a later review target. It does not mean the repair was re-verified afterwards.

<details><summary>Full ledger</summary>

```text
findings ledger — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review

  B01-F01  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING  (MC-2)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  next_cycle counts directories, not valid cycles, so four inv
      cycle 03  DEMONSTRATED       -> RESOLVED  cycle 03: repair verdict demonstrated

  B01-F02  [OPEN]  CONTRADICTORY IMPLEMENTATION MAPPING  (S6)
      repair:   IMPLEMENTED_AWAITING_DEMONSTRATION  [descriptive, not a state]
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The controller tests exits only at the latest boundary and t

  B01-F03  [RESOLVED]  WRONG OWNERSHIP  (MC-1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The schema assigns per-cycle findings.json to the runner; th
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F04  [RESOLVED]  MISSING REQUIREMENT  (S2.2)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  compose_input carries the protocol but not the pinned spec, 
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: amended specifications enter the c

  B01-F05  [RESOLVED]  NONDETERMINISTIC WHERE D POSSIBLE  (S10.1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  candidate_commit is stored verbatim, so HEAD is accepted and
      cycle 03  DEMONSTRATED       -> RESOLVED  cycle 03: repair verdict demonstrated

  B01-F06  [RESOLVED]  MISSING REQUIREMENT  (S10.2)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  Check 13 compares two recorded strings and never hashes the 
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F07  [OPEN]  MISSING REQUIREMENT  (MC-2)
      repair:   IMPLEMENTED_AWAITING_DEMONSTRATION  [descriptive, not a state]
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  protocol_sha256 and spec_sha256 are checked for presence onl

  B01-F08  [RESOLVED]  MISSING REQUIREMENT  (MC-2)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The bootstrap gate runs at init and never again, so componen
      cycle 03  DEMONSTRATED       -> RESOLVED  cycle 03: repair verdict demonstrated

  B01-F09  [RESOLVED]  MISSING REQUIREMENT  (MC-1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  cmd_record hashes whatever is on disk at decision time and n
      cycle 03  DEMONSTRATED       -> RESOLVED  cycle 03: repair verdict demonstrated

  B01-F10  [RESOLVED]  MISSING REQUIREMENT  (MC-1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The review target carries six artifacts; the gate covers fiv
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F11  [OPEN]  CONTRADICTORY IMPLEMENTATION MAPPING  (S6)
      repair:   IMPLEMENTED_AWAITING_DEMONSTRATION  [descriptive, not a state]
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The ledger authorises transitions from unfiltered history wh

  B01-F12  [RESOLVED]  MISSING REQUIREMENT  (S5)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  No event is checked against the finding's raising cycle, so 
      cycle 03  DEMONSTRATED       -> RESOLVED  cycle 03: repair verdict demonstrated

  B01-F13  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING  (V40)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The duplicate-id refusal instructs that a re-raised issue be
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F14  [OPEN]  MISSING REQUIREMENT  (MC-1)
      repair:   IMPLEMENTED_AWAITING_DEMONSTRATION  [descriptive, not a state]
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  MC-1 requires each run to record MC1_ENFORCEMENT. run.json d

  B01-F15  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING  (MC-1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  The schema says freezing proves the artifact did not change,
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F16  [RESOLVED]  UNTESTED RULE  (MC-1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  PY_REF matches filename strings, so a real import is invisib
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F17  [RESOLVED]  UNTESTED RULE  (S10.1)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  Two of five implementation refusals are exercised while the 
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B01-F18  [RESOLVED]  UNTESTED RULE  (MC-2)
      cycle 01  RAISED             -> OPEN  transcribed verbatim from codex-output-raw.md, B01 numbering
      cycle 01  ACCEPT             -> OPEN  Seam-1 probes sit outside a cycle layout, so check 13 fails 
      cycle 02  DEMONSTRATED       -> RESOLVED  cycle 02 review, 'Claimed repairs checked and found to hold'

  B02-F01  [RESOLVED]  MISSING REQUIREMENT
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: the reconciliation runs regardless

  B02-F02  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: the parser accepts the recurrence 

  B02-F03  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: ledger identifier validity comes f

  B02-F04  [OPEN]  CONTRADICTORY IMPLEMENTATION MAPPING
      repair:   IMPLEMENTED_AWAITING_DEMONSTRATION  [descriptive, not a state]
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r

  B02-F05  [RESOLVED]  MISSING REQUIREMENT
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: retained-pin hash overrides are re

  B02-F06  [RESOLVED]  MISSING REQUIREMENT
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: demonstrated for recorded assignme

  B02-F07  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: freeze preserves the diff, results

  B02-F08  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: failed history queries withhold th

  B02-F09  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: the module disclaims forced sequen

  B02-F10  [RESOLVED]  UNTESTED RULE
      cycle 02  RAISED             -> OPEN  transcribed from cycle-02 findings.json by identifier and cl
      cycle 03  ACCEPT             -> OPEN  accepted by Alex Zamurko 14 September; recorded at cycle 3 r
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 03: the prose scan takes its file list

  B03-F01  [RESOLVED]  MISSING REQUIREMENT
      cycle 03  RAISED             -> OPEN  failure to calculate loop state is read as permission to ope
      cycle 03  ACCEPT             -> OPEN  accepted on 15 September by repairing it while cycle 3 was t
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: demonstrated for the reported cont

  B03-F02  [RESOLVED]  CONTRADICTORY IMPLEMENTATION MAPPING
      cycle 03  RAISED             -> OPEN  the cycle-03 prompt states the suites are in the target; tar
      cycle 03  ACCEPT             -> OPEN  accepted on 15 September by repairing it while cycle 3 was t
      cycle 04  DEMONSTRATED       -> RESOLVED  demonstrated by cycle 04: demonstrated as an auxiliary evide

  OPEN      5
  RESOLVED  25
  DISPUTED  0
```

</details>

## MC-2 conformance, every cycle

The gate is run now, against the frozen evidence, rather than quoted from a stored result. A recorded PASS is a claim about the past; this is the gate's answer today.

### cycle-01 — `MC2_CONFORMANCE: PASS`

<details><summary>full gate output</summary>

```text
MC-2 conformance — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review/cycle-01

   1. [PASS] target.json exists
   2. [PASS] target.sha256 exists
   3. [PASS] codex-input.md exists
   4. [PASS] codex-output-raw.md exists
   5. [PASS] all required files non-empty
   6. [PASS] target.sha256 matches target
   7. [PASS] cycle identifier unique
          cycle 1 in plan-review
   8. [PASS] referenced git commit exists
          resolved: 63939ecbe0f5271569bba09a203c8df534612e64
   9. [PASS] mandatory hashed artifacts present and matching
  10. [PASS] codex-input.md contains target SHA-256 verbatim
  11. [N/A ] candidate commit present and exists
          review_type is 'plan'; §10.2 applies to implementation review only
  12. [N/A ] candidate tree hash matches the candidate tree
          review_type is 'plan'; §10.2 applies to implementation review only
  13. [N/A ] approved-plan hash matches the frozen approved plan
          review_type is 'plan'; §10.2 applies to implementation review only
  14. [N/A ] diff hash matches the reviewed diff
          review_type is 'plan'; §10.2 applies to implementation review only
  15. [N/A ] test-result hash matches the supplied test results
          review_type is 'plan'; §10.2 applies to implementation review only

MC2_CONFORMANCE: PASS
```

</details>

### cycle-02 — `MC2_CONFORMANCE: PASS`

<details><summary>full gate output</summary>

```text
MC-2 conformance — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review/cycle-02

   1. [PASS] target.json exists
   2. [PASS] target.sha256 exists
   3. [PASS] codex-input.md exists
   4. [PASS] codex-output-raw.md exists
   5. [PASS] all required files non-empty
   6. [PASS] target.sha256 matches target
   7. [PASS] cycle identifier unique
          cycle 2 in plan-review
   8. [PASS] referenced git commit exists
          resolved: 63939ecbe0f5271569bba09a203c8df534612e64
   9. [PASS] mandatory hashed artifacts present and matching
  10. [PASS] codex-input.md contains target SHA-256 verbatim
  11. [N/A ] candidate commit present and exists
          review_type is 'plan'; §10.2 applies to implementation review only
  12. [N/A ] candidate tree hash matches the candidate tree
          review_type is 'plan'; §10.2 applies to implementation review only
  13. [N/A ] approved-plan hash matches the frozen approved plan
          review_type is 'plan'; §10.2 applies to implementation review only
  14. [N/A ] diff hash matches the reviewed diff
          review_type is 'plan'; §10.2 applies to implementation review only
  15. [N/A ] test-result hash matches the supplied test results
          review_type is 'plan'; §10.2 applies to implementation review only

MC2_CONFORMANCE: PASS
```

</details>

### cycle-03 — `MC2_CONFORMANCE: PASS`

<details><summary>full gate output</summary>

```text
MC-2 conformance — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review/cycle-03

   1. [PASS] target.json exists
   2. [PASS] target.sha256 exists
   3. [PASS] codex-input.md exists
   4. [PASS] codex-output-raw.md exists
   5. [PASS] all required files non-empty
   6. [PASS] target.sha256 matches target
   7. [PASS] cycle identifier unique
          cycle 3 in plan-review
   8. [PASS] referenced git commit exists
          resolved: 63939ecbe0f5271569bba09a203c8df534612e64
   9. [PASS] mandatory hashed artifacts present and matching
  10. [PASS] codex-input.md contains target SHA-256 verbatim
  11. [N/A ] candidate commit present and exists
          review_type is 'plan'; §10.2 applies to implementation review only
  12. [N/A ] candidate tree hash matches the candidate tree
          review_type is 'plan'; §10.2 applies to implementation review only
  13. [N/A ] approved-plan hash matches the frozen approved plan
          review_type is 'plan'; §10.2 applies to implementation review only
  14. [N/A ] diff hash matches the reviewed diff
          review_type is 'plan'; §10.2 applies to implementation review only
  15. [N/A ] test-result hash matches the supplied test results
          review_type is 'plan'; §10.2 applies to implementation review only

MC2_CONFORMANCE: PASS
```

</details>

### cycle-04 — `MC2_CONFORMANCE: PASS`

<details><summary>full gate output</summary>

```text
MC-2 conformance — /sessions/elegant-wizardly-bardeen/mnt/epistemicos/runs/BOOTSTRAP-001/plan-review/cycle-04

   1. [PASS] target.json exists
   2. [PASS] target.sha256 exists
   3. [PASS] codex-input.md exists
   4. [PASS] codex-output-raw.md exists
   5. [PASS] all required files non-empty
   6. [PASS] target.sha256 matches target
   7. [PASS] cycle identifier unique
          cycle 4 in plan-review
   8. [PASS] referenced git commit exists
          resolved: 63939ecbe0f5271569bba09a203c8df534612e64
   9. [PASS] mandatory hashed artifacts present and matching
  10. [PASS] codex-input.md contains target SHA-256 verbatim
  11. [N/A ] candidate commit present and exists
          review_type is 'plan'; §10.2 applies to implementation review only
  12. [N/A ] candidate tree hash matches the candidate tree
          review_type is 'plan'; §10.2 applies to implementation review only
  13. [N/A ] approved-plan hash matches the frozen approved plan
          review_type is 'plan'; §10.2 applies to implementation review only
  14. [N/A ] diff hash matches the reviewed diff
          review_type is 'plan'; §10.2 applies to implementation review only
  15. [N/A ] test-result hash matches the supplied test results
          review_type is 'plan'; §10.2 applies to implementation review only

MC2_CONFORMANCE: PASS
```

</details>

## What is being approved

From `cycle-04`, the most recent frozen cycle.

Target digest: `0fa90c4b80cc1650c58db1574daa26e64b349a858f59bb21485822949c7e9ff9`

10 artifact(s):

- `specs/evidence-schema-v1.0.md` · `4203ba64bd5ba1db9cd56357c8bf9dd8e6efb419fab7f7635a415c272d3a739c`
- `scripts/validate_cycle.py` · `8cd856a51b02ff5408ace42f5758eb2f927b6e01595702bda1ad5b7dd8e0f1b8`
- `scripts/run_review.py` · `e14c0bce742ab1aa4b2486a0490664052e55acc4f783a38660aa18260278cb23`
- `scripts/ledger.py` · `8b3ed30c0b90370abbf0611774fc0d632684e0e6693a76870f5bbecd901d04d5`
- `scripts/loop_state.py` · `1d2c31d85b76a7d9019c512822451b9166dd5481f5fba9012455bf8126e03d67`
- `scripts/bootstrap_gate.py` · `44e292a85ae299663e3713c403a04f34bc17d673fce6b31f5167b51a4190eb1c`
- `scripts/findings_format.py` · `27dcf377b0014b3ac2563da61597675fc0bca9c95bce18d1b776bcb22ee53a90`
- `scripts/cycle_projection.py` · `f822bd57d4f0643a4c7083d23b7082b003ba6bc6e558430841e41a617f0c9832`
- `scripts/authority.py` · `c0a394d68ba5f13168dfc78b029ed6799f7bd16b25a21ba5f4ff4401e2efa6d6`
- `scripts/run_pins.py` · `20a22852b3a2c3642ea8a2c0a01ae23e58aedf8e421e1135dc592fcfdb149753`

The bytes reviewed are preserved under `cycle-04/artifacts/`. They are what the reviewer saw, and they do not change when the working tree does.

## §7 coverage

Checked against §7's list rather than against what this package managed to produce, so an item that stopped being generated shows as absent instead of vanishing.

- [x] final plan
- [x] final plan hash
- [x] loop status
- [x] valid iteration count
- [ ] SPEC -> CODE -> TEST mapping
- [x] resolved findings
- [x] disputes
- [x] unresolved findings
- [x] MC-1 enforcement status
- [x] MC-2 conformance results for every valid cycle

**1 of 10 not present.**

- *SPEC -> CODE -> TEST mapping*: the output of a §1 plan audit. A bootstrap run reviews code directly and has no plan, so there is no mapping to produce. Named here rather than omitted, because a reviewer who cannot see what is missing cannot weigh it.

---

## Recording the decision

§7.3 permits `APPROVE`, `RETURN_FOR_REWORK`, `REJECT`. Nothing in this file records one.

```text
python scripts/bootstrap_gate.py record \
    --decision APPROVE|RETURN_FOR_REWORK|REJECT \
    --decided-by "<name>" \
    --note "<where the decision was made, and on what>"
```
