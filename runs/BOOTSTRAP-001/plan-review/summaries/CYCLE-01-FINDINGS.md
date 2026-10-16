# Cycle 01 findings — eighteen, with current status

**This is a summary for reading, not the authoritative record.** The authoritative
finding set is `cycle-01/findings.json`, extracted from `cycle-01/codex-output-raw.md`;
state lives in `ledger.json`. Where this file and those disagree, they govern and
this is wrong. It is written by hand and can drift; they cannot.

Status as at commit `e1e3c04`, after cycle 03 and the repair work of 14 to 15
September.

Cycle 03 examined the ten repair claims this file made and demonstrated five of
them. Those five are now `RESOLVED` and have moved into **Closed** below. The
five it rejected keep their identifiers and have been repaired again since.

What was done to each is set out in **Repairs claimed, awaiting cycle 04** at
the end of this file. That section is the implementing agent's own account of
its own work, and cycle 03 rejected nine of the twenty such claims it examined,
which is the rate it should be read against. §5 gives `RESOLVED` only once the
repair is demonstrated in the next review target, so the ledger reads `OPEN` for
all five and is right to.

## What cycle 01 was

The first independent review of the execution layer, frozen 9 September against
the protocol at `296594a3…`. Six artifacts: the evidence schema, the MC-2 gate,
the runner, the ledger, the loop controller and the bootstrap gate.

It exists because the orchestrator constrains the implementing agent and the
implementing agent wrote it. Nothing here could pass through the process it
enables, because the process did not exist until it did.

Codex returned eighteen findings. All eighteen were accepted.

---

## Closed — thirteen

Confirmed as repaired by Codex, not by the implementing agent: eight in cycle 02
and five in cycle 03.

### By cycle 02 — eight

**B01-F03** WRONG OWNERSHIP · MC-1
The schema assigned per-cycle `findings.json` to the runner; the runner never
wrote it, and the ledger wrote a review-level file with the same name instead.
An absent ledger read as a review that found nothing.

**B01-F06** MISSING REQUIREMENT · §10.2
Check 13 compared two recorded strings and never hashed the approved plan, so
the plan could change while both records still agreed.

**B01-F10** MISSING REQUIREMENT · MC-1
The review target carried six artifacts; the gate covered five. Editing
`evidence-schema-v1.0.md` did not invalidate its own approval.

**B01-F13** CONTRADICTORY IMPLEMENTATION MAPPING · V40
The duplicate-id refusal told the operator that a re-raised issue becomes a new
finding, contradicting persistent identifiers and defeating §6's re-raise
detection. The refusal was right; its guidance was wrong.

**B01-F15** CONTRADICTORY IMPLEMENTATION MAPPING · MC-1
The schema said freezing proves an artifact did not change, and the
implementing agent had told Alex Zamurko that self-hashing closed the
replace-and-evaluate hole. Neither holds under `CONVENTION_ONLY`: the same
writable code performs the check.

**B01-F16** UNTESTED RULE · MC-1
Dependency discovery matched filename strings, so a real import was invisible to
it, and the control inserted a string rather than an import. The closure claim
was stronger than its evidence.

**B01-F17** UNTESTED RULE · §10.1
Two of five implementation refusals were exercised while the suite printed that
every refusal was reachable.

**B01-F18** UNTESTED RULE · MC-2
Seam-1 probes sat outside a cycle layout, so check 13 failed on all of them for
the wrong reason. Deleting check 12's enforcement outright still reported 7/7
enforced and exited 0.

---

### By cycle 03 — five

Each verdict is recorded with the limit Codex put on it. A repair that holds for
the case examined is not a repair that holds for every case, and writing down
only the first half is how a summary becomes more reassuring than the review it
summarises.

**B01-F01** CONTRADICTORY IMPLEMENTATION MAPPING · MC-2
`next_cycle` counted cycle directories rather than valid cycles, so four invalid
cycles could exhaust a budget MC-2 says they cannot consume. Freeze now counts
the shared projection's valid cycles. *Limit: restart semantics at the boundary
were the separate B01-F02 issue, still open at the time.*

**B01-F05** NONDETERMINISTIC WHERE D POSSIBLE · §10.1
`candidate_commit` was stored verbatim, so `HEAD` was accepted and stayed mutable
while checks 11 and 12 kept passing. Freeze now resolves the supplied reference
to a full commit SHA, derives the tree from that, and keeps what was supplied
alongside. *Limit: this fixes ordinary reference movement. It is not an MC-1
protection claim.*

**B01-F08** MISSING REQUIREMENT · MC-2
The bootstrap gate ran at init and never again, and the controller never read
the exempt label, so development evidence could reach authoritative loop state.
The ordinary controller now rejects `EXEMPT` runs, and development evaluation
carries its label through the normal status interface. *Limit: this concerns the
declared classification, not the completeness of all run metadata.*

**B01-F09** MISSING REQUIREMENT · MC-1
Recording a decision hashed whatever was on disk and never compared it to the
frozen target. Bootstrap evaluation now rechecks the recorded evidence hashes
and the frozen target hash as well as component hashes. *Limit: this establishes
drift detection while the checks run faithfully. It does not authenticate the
reviewer or the approver.*

**B01-F12** MISSING REQUIREMENT · §5
No event was checked against the finding's raising cycle, so a finding could be
accepted and resolved in cycles earlier than the one that raised it. Respond,
resolve and reopen now all call the ordering check. *Limit: this checks ordering
relative to the raising cycle. It does not establish chronology across the whole
event history.*

---

## Open — five

The five repair claims cycle 03 rejected. They keep their original identifiers,
because §6's re-raise detection needs the identity to persist, and they appear
again in the cycle 02 and cycle 03 lists.

B01-F01, F05 and F12 were among the five Alex Zamurko deferred on 9 September
with "just the critical ones, we need to start producing working code." That
deferral has now run its course: cycle 03 judged all of them and closed them.

**B01-F04** MISSING REQUIREMENT · §2.2
*Was:* the composed review input carries the protocol but not the pinned spec,
and for an implementation review omits the target identifiers entirely.
*Now:* the original pinned specs and the implementation identifiers reach the
input. A spec added by amendment does not, so the reviewer can still be asked to
judge against a governing document it was never given.

**B01-F07** MISSING REQUIREMENT · MC-2
*Was:* `protocol_sha256` and `spec_sha256` are checked for presence only. No
check ties them to the pinned artifacts or to `run.json`.
*Now:* target construction derives cycle-specific digests, but input composition
still used run-level ones, and validation still accepted arbitrary digest
strings. A self-consistent target checksum does not establish that its fields
are correct.

*Constraint added 10 September: whoever repairs this must bind each cycle to the
pins in force at that cycle. Binding every cycle to the latest pin set would
retroactively invalidate cycle 01. See `pin-amendments.json`.*

**B01-F02** CONTRADICTORY IMPLEMENTATION MAPPING · §6
*Was:* the controller tested exits only at the latest boundary and the runner
checked only that the previous cycle had output, so a terminal exit in an
earlier cycle could be overridden by a later one.
*Now:* a cleared `STALLED` at the latest boundary works through the runner. At
the budget boundary the controller still announced a permission the runner
refused, and the code had no coherent distinction between restarting an
authorised loop and exceeding the four-valid-cycle maximum within one.

*Ruled by Alex Zamurko, 15 September.* Three readings were put to him: an
authorisation starts a fresh loop with its own budget; an authorisation raises
the current loop's budget; or nothing clears the maximum. He chose the third.
The contradiction is settled by withdrawing the offer rather than by honouring
it, which keeps §2's sentence literal.

**B01-F11** CONTRADICTORY IMPLEMENTATION MAPPING · §6
*Was:* the ledger authorised transitions from unfiltered history while the
controller filtered by valid cycle, so an invalid event could deadlock a valid
one or authorise a closure.
*Now:* invalidated `ACCEPT` prerequisites are replayed correctly, but cycles
that do not exist still authorised ledger transitions. The control named as
proof of the repair passed with the repair removed, so anything concluded from
that suite before 15 September needs rechecking.

**B01-F14** MISSING REQUIREMENT · MC-1
*Was:* MC-1 requires each run to record `MC1_ENFORCEMENT`; `run.json` did not
carry it.
*Now:* init and freeze enforce the field, and `BOOTSTRAP-001` labels its
reconstruction honestly. The controller could still emit an authoritative
protocol outcome for a run without it: the same pattern of enforcing a rule at
one entry point and leaving another consumer permissive.

---

## Repairs claimed, awaiting cycle 04 — five

**Read this as a claim, not a status.** Every line below was written by the
implementing agent about its own work. Cycle 03 rejected nine of the twenty such
claims it examined, which is the base rate this section should be read against.
The ledger records none of it, correctly: a finding moves to `RESOLVED` on a
`DEMONSTRATED` event, and only cycle 04 can raise one.

Each repair was checked by mutation, meaning the fix was deliberately broken and
the named control confirmed to fail *for its own reason*, with the other
controls staying green. That last clause is not decoration. B01-F11's previous
control went red under mutation for an unrelated reason and was recorded as
proof; B02-F06's version control this time refused for pin drift rather than for
the thing it names, and would have passed a weaker check.

| ID | Commit | What changed | Control that fails without it |
|----|--------|--------------|-------------------------------|
| B01-F02 | `e1e3c04` | `MAX_4_REACHED` is not clearable by authorisation, and the one number four now lives in `cycle_projection` instead of one copy per component | `test_run_review.py` · "an authorization naming MAX_4_REACHED is read, refused, and said out loud" |
| B01-F04 | `2e8b1b4` | the embedded specs come from the cycle's effective pin set, so a spec added by amendment reaches the reviewer | `test_run_review.py` · "a spec added by amendment appears in the composed input" |
| B01-F07 | `c85eeee`, then `04572f9` | the input header quotes the cycle's own digests rather than the run's; and check 9 validates the governing digests a target records | `test_run_review.py` · "the input header quotes the cycle's own digests, not the run's"; `test_validate_cycle.py` · "a spec digest that does not describe the governing set" |
| B01-F11 | `4bac2b6` | authority rests on cycle membership, and a `REOPENED` withdraws the acceptance it rested on | `test_ledger.py` · "invalid cycles neither authorize nor block (B01-F11)" |
| B01-F14 | `a576489` | the controller and the runner share one run-metadata rule instead of each holding its own | `test_run_review.py` · "a protocol run recording its enforcement status" |

**On B01-F02.** This is the only one of the five that rests on a ruling rather
than on code alone. Alex Zamurko chose between three readings on 15 September;
the repair implements his third. A future reviewer who disagrees with the
reading should take it up with the ruling, not with the implementation.

**On B01-F07's two commits.** Cycle 03 found two separate defects under one
identifier: composition used run-level digests, and validation accepted any
digest string at all. Repairing either alone leaves the finding standing.

**On B01-F11.** Its old control was decorative. It passed with the repair
removed, which means anything concluded from `test_ledger.py` before 15
September needs rechecking rather than assuming.

**On B01-F14.** `BOOTSTRAP-001` predates the requirement. Its enforcement value
is marked as reconstructed rather than presented as though it had been recorded
at the time, because the alternative is a record that claims more than happened,
which is B01-F15.
