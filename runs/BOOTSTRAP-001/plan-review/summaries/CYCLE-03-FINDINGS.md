# Cycle 03 findings — eleven

**This is a summary for reading, not the authoritative record.** The authoritative
finding set is `cycle-03/findings.json`, extracted from `cycle-03/codex-output-raw.md`;
state lives in `ledger.json`. Where this file and those disagree, they govern and
this is wrong. It is written by hand and can drift; they cannot.

Status as at commit `03cb427`. `LOOP_STATUS: CONTINUE`, three of four cycles
used. Cycle 04 is the last before `MAX_4_REACHED`, which since 15 September is a
terminal exit no authorisation clears.

## What cycle 03 was

Frozen 14 September against the same ten artifacts as cycle 02, and captured the
same day. One attempt, valid on the first try, 31,864 bytes.

It asked two questions. The first was the one §5 turns on: **are the twenty
repairs demonstrated?** The second was the ordinary one: **is anything new
wrong?**

Codex did not take the prompt's word for the control counts. It built temporary
repositories containing copies of the reviewed scripts, ran its own probes, and
counted 263 controls — matching the frozen input exactly. Several of its
findings come from fault injection it performed itself rather than from reading.

*Not recorded anywhere in the evidence: which model produced this review.*
`capture-log.json` records the source file, its bytes, its digest and that the
invocation was manual. It does not record the reviewer. For a protocol whose
purpose is auditable evidence that is a gap, and it is the same gap Codex named
in its B01-F09 verdict: the checks establish drift detection, not who reviewed.

---

## The verdict on twenty repair claims

**Eleven demonstrated:** B01-F01, B01-F05, B01-F08, B01-F09, B01-F12, B02-F01,
B02-F02, B02-F03, B02-F07, B02-F09, B02-F10.

**Nine not demonstrated:** B01-F02, B01-F04, B01-F07, B01-F11, B01-F14,
B02-F04, B02-F05, B02-F06, B02-F08.

Cycle 02 rejected five of thirteen. Cycle 03 rejected nine of twenty. The rate
did not improve, and the pattern did not change: in almost every rejection the
ordinary path was repaired and the adversarial one was left standing.

Codex's closing sentence: *"I make no claim that the review has converged."*

---

## Recurrences — nine

These keep their original identifiers, because §6's re-raise detection needs the
identity to persist. Their blocks deliberately do not reassert a Class; they
retain the classification the ledger already holds. Full text lives in the
cycle 01 and cycle 02 summaries.

| ID | What the repair left undone |
|----|------------------------------|
| B01-F02 | latest-boundary `STALLED` continuation works; at the budget boundary the controller granted a permission the runner refused |
| B01-F04 | the original pinned specs reach the input; a spec added by amendment does not |
| B01-F07 | target construction derives cycle-specific digests; composition still used run-level ones, and validation accepted any digest string |
| B01-F11 | invalidated `ACCEPT` prerequisites replay correctly; nonexistent cycles still authorised transitions, and the named control passed with the fix removed |
| B01-F14 | init and freeze enforce the field; the controller could still emit an authoritative outcome for a run without it |
| B02-F04 | ordinary refusal preserves the old evidence; the replacement was not transactional, and interruption left mixed generations |
| B02-F05 | dropping the protocol and adding an unhashed pin are refused; extra keys could still rewrite a retained artifact's hash |
| B02-F06 | the tested backdating is caught within one review directory; not across the run, and membership was compared rather than versions |
| B02-F08 | ordinary expiry works; an unreadable history was read as no approval, so the check failed open |

---

## New — two

**B03-F01** MISSING REQUIREMENT · `run_review.py`, `loop_state.py`, `cycle_projection.py`
`check_loop_not_terminated` refused a controller exit code of 2 and the
recognised terminal strings. It did not require exit 0, or a recognised
`CONTINUE`. The defensive replay added for B01-F11 raises `UnknownEvent`, and the
controller caught only `CannotCalculate`, so an unrecognised ledger event exited
1 with a traceback and printed no `LOOP_STATUS` at all — and the runner read that
as neither terminal nor undeterminable and opened the next cycle.

Codex added an unknown event to a finding's history in a temporary run and
watched the controller crash and a subsequent freeze exit 0 and create cycle-02.
An executed probe, not a hypothesis.

*Failure to calculate the loop state was being read as permission to continue.*
The defence added in one repair became a fail-open path at the boundary of
another.

**B03-F02** CONTRADICTORY IMPLEMENTATION MAPPING · `cycle-03/codex-input.md`, `cycle-03/target.json`
The cycle 03 prompt told the reviewer "the suites are in the target." They were
not. `target.json` binds ten artifacts, all of them production modules, and none
of the five control suites appears in `plan_files` or is embedded in the composed
input. Codex could read and run the working-tree suites, but their versions were
not bound by the `TARGET_SHA256` it was asked to quote.

So the 263 control results it observed are reproducible evidence from the suites
it ran, and not evidence that this target froze those suites or the mutation
results claimed for them. A later reader cannot identify the exact control
versions from the review target alone.

*This is a finding about the prompt, written by the implementing agent, telling
the reviewer something untrue about what the target established.* It is the
thing cycle 03 was explicitly asked to catch.

---

## What Codex declined to endorse

Recorded because a summary that keeps only the findings and drops the
reservations makes the review sound more settled than it was.

On the suites' own closing claims: it does not endorse "every refusal is
reachable" or "every rule demonstrated." The nonexistent-cycle control survived
removal of its purported fix. The supersession controls did not test interrupted
publication. The resumption seam covered `STALLED` rather than the exhausted
budget. The history controls omitted query failure.

On counting: checking a suite's exit code detects a crash, and checking its
observed count against an independently stated expectation detects a shortened
run. But a suite's final success string follows an accumulated failure list and
can survive a control being removed or skipped, and **a count cannot show that
the intended refusal is what made a test pass** — which B01-F11 demonstrated. A
durable completeness claim needs an independently maintained inventory of
expected controls, not a refreshed number agreeing with another consumer of that
number.

On over-claims still standing: the prompt's atomic-swap claim, its assertion that
the suites belong to the target, the mutation assurance contradicted by the
nonexistent-cycle control, and the monotonicity claim under decision G. Also the
runner's own opening description, "Write-once evidence", which says raw output is
never overwritten and that record refuses whenever raw output is present. That
has not described the capture-log behaviour for some time.

*None of these mechanisms establishes technical immutability, or proves the
retained output came from the recorded input.* Under `MC1_ENFORCEMENT:
CONVENTION_ONLY` that is the honest ceiling.

---

## Repairs claimed, awaiting cycle 04 — eleven

**Read this as a claim, not a status.** Written by the implementing agent about
its own work. Cycle 03 rejected nine of twenty such claims; that is the rate to
read this against.

Each was checked by mutation: the fix deliberately broken, and the named control
confirmed to fail *for its own reason* while the others stayed green. The
qualifier is the lesson of B01-F11, whose previous control went red under
mutation for an unrelated reason and was recorded as proof anyway.

| ID | Commit | What changed | Control that fails without it |
|----|--------|--------------|-------------------------------|
| B01-F02 | `e1e3c04` | `MAX_4_REACHED` is not clearable by authorisation, and the one number four lives in `cycle_projection` rather than one copy per component | `test_run_review.py` · "an authorization naming MAX_4_REACHED is read, refused, and said out loud" |
| B01-F04 | `2e8b1b4` | embedded specs come from the cycle's effective pin set, so an amendment-added spec reaches the reviewer | `test_run_review.py` · "a spec added by amendment appears in the composed input" |
| B01-F07 | `c85eeee`, then `04572f9` | the input header quotes the cycle's own digests; and check 9 validates the governing digests a target records | `test_run_review.py` · "the input header quotes the cycle's own digests, not the run's"; `test_validate_cycle.py` · "a spec digest that does not describe the governing set" |
| B01-F11 | `4bac2b6` | authority rests on cycle membership, and a `REOPENED` withdraws the acceptance it rested on | `test_ledger.py` · "an acceptance in a gap between real cycles authorizes nothing" and "a reopened finding needs a new acceptance, not the spent one" |
| B01-F14 | `a576489` | the controller and the runner share one run-metadata rule | `test_run_review.py` · "a protocol run recording its enforcement status is concluded normally" |
| B02-F04 | `2ad9ccd` | one commit point instead of two renames; the attempt directory holds its own raw bytes and findings and is never edited again; publication repeats before any new recording | `test_run_review.py` · "a half-published cycle is recovered even by a command that is then refused" and "the working copies match the designated generation" |
| B02-F05 | `a8922fa` | `added_pin_hashes` binds the bytes of newly added pins only | `test_run_review.py` · "refused: an amendment that rewrites a retained pin's hash" |
| B02-F06 | `61d6c6f` | the frozen check covers every review directory in the run, records keep which loop they came from, and recorded hashes are compared as well as paths | `test_run_review.py` · "refused: one loop freezing against history that contradicts the other loop's completed cycle" and "refused: same governing paths under a completed cycle, different versions" |
| B02-F08 | `674a394` | an unreadable git history is reported as unreadable, not as evidence that no approval exists | `test_bootstrap_gate.py` · "the exception is withheld when the history cannot be read" |
| B03-F01 | `004ee0a` | only a completed controller run reporting exactly one recognised `CONTINUE` is permission to open a cycle | `test_run_review.py` · "refused: a controller that says CONTINUE and then fails", "refused: a controller that exits 0 and reports no status", "refused: a status this runner does not recognise", "refused: two statuses in one run" |
| B03-F02 | `89e3e3e` | the control suites are recorded in a hash-bound manifest beside the target rather than described as members of it | `test_run_review.py` · "the manifest records every suite at freeze", "target.json records the manifest digest, and target.sha256 covers target.json", "no control suite appears in the review target", "a later suite edit leaves the frozen record unchanged" |

**On B01-F02.** The only one of the eleven resting on a ruling rather than on
code alone. Three readings were put to Alex Zamurko on 15 September and he chose
the one that keeps §2's sentence literal: nothing clears the four-valid-cycle
maximum. A reviewer who disagrees should take it up with the ruling.

**On B03-F02.** The repair does not widen the gate's covered set, because
`target_drift` rejects extra target artifacts. Whether `refresh_counts.py` itself
belongs in the covered set remains Alex Zamurko's decision and is not settled
here.

---

## Found by the implementing agent, not by a reviewer — two

Neither carries a reviewer's identifier, so neither is in any authoritative
finding set. They are listed so the record is complete.

**B02-F11**, 10 September. A refused capture attempt was recorded on disk but not
in the capture log, so the log and the directory disagreed about what had been
attempted. Addressed in `0629bbd`.

**The count refresh rewrote finished cycles' prompts**, 15 September. It updated
every bootstrap prompt on every run, including cycles already frozen, so
`bootstrap-review-cycle-03.md` came to assert 298 controls for a review conducted
against 263 — and the check that should have caught it compared the rewritten
document against the same suites that had just been written into it. Two checks
agreeing, both measuring the same afternoon. `c2d5c4e` had restored these numbers
by hand once already and the tool put them straight back. Addressed in `c3a4020`,
which repairs the tool: a prompt whose cycle has a frozen input is left alone,
and a frozen cycle's prompt is checked against that cycle rather than against
today.

**Both raise the same unanswered question,** and two instances make it a policy
rather than an incident: *does a defect the implementing agent finds in its own
work enter the ledger as a finding, or stay a repair with no finding attached?*
Entering it means the agent raises findings against itself, which is the thing
the review exists to avoid relying on. Not entering it means the ledger
undercounts what was wrong. **Awaiting a decision from Alex Zamurko**, open since
10 September.
