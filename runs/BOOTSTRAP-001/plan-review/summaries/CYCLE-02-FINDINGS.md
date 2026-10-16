# Cycle 02 findings — fifteen

**This is a summary for reading, not the authoritative record.** The authoritative
finding set is `cycle-02/findings.json`, extracted from `cycle-02/codex-output-raw.md`;
state lives in `ledger.json`. Where this file and those disagree, they govern and
this is wrong.

Status as at commit `e1e3c04`. `LOOP_STATUS: CONTINUE`, three of four cycles
used.

Cycle 03 examined the ten repair claims this file made and demonstrated six.
It rejected four, and those four have been repaired again since.

**The ledger reads `OPEN` for all ten, including the six.** This is the one
place where this file and the authoritative record appear to disagree, so it is
worth setting out rather than leaving a reader to trip over.

Alex Zamurko ruled on 14 September that these findings be marked accepted on the
day he accepted them rather than backdated to cycle 02, so their `ACCEPT` events
sit at cycle 3. `ledger.py:465` refuses to resolve a finding in the same cycle it
was accepted in, because §5 wants the demonstration to land in the *next* review
target after the acceptance. Six findings that cycle 03 demonstrated therefore
could not be recorded as resolved at cycle 03, and no later cycle re-examines a
repair it has already judged.

Two of our own rules, each defensible, producing a finding that could not close.
He ruled on 15 September that the six be recorded at cycle 4 with a note naming
cycle 03 as what demonstrated them. Until that entry is written the ledger is
right and this file is describing a state the ledger has not reached.

## What cycle 02 was, and how it differs from cycle 01

Cycle 01 asked one question: is this code correct against the protocol. Cycle 02
asks two.

1. **Do the claimed repairs hold?** §5 gives a finding `RESOLVED` only "once the
   repair is demonstrated in the next review target". Cycle 02 is that target,
   so it is the cycle that closes cycle 01's findings, or declines to.
2. **Is anything new wrong?** The repairs added three files and changed five,
   and a fourth file had been load-bearing since before cycle 01 without ever
   appearing in a reviewer's list.

The target grew from six artifacts to ten: `findings_format.py`,
`cycle_projection.py`, `authority.py` and `run_pins.py` had never been reviewed
by anyone. They entered the reviewed set through the gate's own import
discovery rather than by being declared.

The prompt was written by the implementing agent describing its own repairs, and
says so. It names the commits as the evidence and tells the reviewer that a
repair listed as done but not done is exactly what the cycle exists to catch.
Five such listings were found.

**Where the two lists apply.** Cycle 01's list is the historical record of what
was wrong on 9 September, and thirteen of its eighteen entries are now closed.
The five entries that appear in both lists are not duplicates: they are cycle 01
findings whose repair cycle 02 rejected, and they keep their original
identifiers because §6's re-raise detection needs the identity to persist.

Since cycle 03, neither of these is the live work queue on its own. Eleven
findings were open after cycle 03, spread across all three lists, and the
cycle 03 summary carries the consolidated view.

---

## Repairs rejected — five

Full text in the cycle 01 summary. Listed here because they are part of cycle
02's authoritative finding set.

| ID | What cycle 02 found undone | Where it stands after cycle 03 |
|----|---------------------------|--------------------------------|
| B01-F02 | authorised continuation fails at the point the runner needs it | rejected again; settled by Alex Zamurko's ruling of 15 September and repaired at `e1e3c04` |
| B01-F08 | the controller cannot tell development evidence from protocol evidence | **demonstrated, closed** |
| B01-F09 | approval survives deletion of the review evidence it rests on | **demonstrated, closed** |
| B01-F11 | a resolution resting on an invalid acceptance still survives | rejected again; repaired at `4bac2b6` |
| B01-F14 | enforcement status is written but never required, and this run lacks it | rejected again; repaired at `a576489` |

---

## New — ten

### Demonstrated by cycle 03 — six

Each verdict carries the limit Codex put on it. Recording only the first half of
a qualified verdict is how a summary ends up more reassuring than the review it
summarises. These six are awaiting their ledger entry at cycle 4, as set out at
the top of this file.

**B02-F01** MISSING REQUIREMENT · `findings_format.py`, `run_review.py`, `loop_state.py`
A finding block indented by one space was invisible to the strict parser, and
the safeguard that would have caught it only ran when nothing parsed at all. One
successful block switched off the protection for the rest. *Cycle 03:* the
reconciliation now runs regardless of whether another block parsed, and the
indented block is detected and refused rather than silently omitted.

**B02-F02** CONTRADICTORY IMPLEMENTATION MAPPING · `cycle-02/codex-input.md`, `findings_format.py`
The cycle 02 prompt specified a recurrence block with no `Class:` line, and the
parser required one on every block. Following the review instructions exactly
produced a response the capture runner refused. Codex reported the
incompatibility as the finding rather than reformatting to make it pass.
*Cycle 03:* the parser accepts the recurrence form, and record resolves the
class from the ledger, so the reviewer never re-asserts a classification it is
not making.

**B02-F03** CONTRADICTORY IMPLEMENTATION MAPPING · schema, `findings_format.py`, `ledger.py`
The schema permitted zero to two capital letters at the start of a finding
identifier; the ledger's independently written expression permitted at most one.
`AB02-F01` parsed cleanly and the ledger then refused it. *Cycle 03:* ledger
identifier validity now comes from the canonical grammar, and cycle extraction
is a separate concern.

**B02-F07** CONTRADICTORY IMPLEMENTATION MAPPING · `run_review.py`, `validate_cycle.py`
For implementation review, checks 14 and 15 hashed the live diff and test
results rather than the preserved copies, and the approved plan was not
snapshotted at all. *Cycle 03:* freeze preserves the diff, results, approved
plan and approval record, and checks 13 to 15 use those copies when present.
*Limit: the legacy live-file fallback is a limitation, not evidence that current
snapshots are technically protected.*

**B02-F09** CONTRADICTORY IMPLEMENTATION MAPPING · `authority.py`
The module stated that the approval hashes were "not knowable until the action
has been attempted and refused once". They are computable in advance, and no
prior-refusal state is checked. An over-claim inside the module written to avoid
over-claims. *Cycle 03:* the module now disclaims forced sequencing, proven
authorship and an independent write boundary, and the former claim is identified
as false rather than quietly dropped.

**B02-F10** UNTESTED RULE · the control suites
The no-over-claim scanner read a hard-coded list of six files and omitted all
four newly reviewed modules, including the one containing B02-F09. Two authority
refusals had no control at all. *Cycle 03:* the scan takes its file list from
`covered()`, and the two refusals gained controls. *Limit: this verifies the
scope and the added controls, not the idea that a keyword scan can certify
prose.*

---

### Open — four

Cycle 03 rejected these four. In every case the ordinary path was repaired and
the adversarial one was not, which is the shape most of this ledger takes.

**B02-F04** CONTRADICTORY IMPLEMENTATION MAPPING · `run_review.py`
*Was:* superseding a capture deleted the authoritative evidence before the
consistency check ran, so a conflicting flag combination destroyed the working
records and then reported "Nothing written."
*Now:* ordinary refusal no longer deletes anything, but the replacement was
still not transactional. Fault injection between the two renames left mixed
generations and a stale designation.

**B02-F05** MISSING REQUIREMENT · `run_pins.py`, `run_review.py`
*Was:* a structurally valid amendment could remove the governing protocol from
the pin set, or add a path the pin check never looked at.
*Now:* dropping the protocol and adding an unhashed pin are both refused. Extra
keys in `added_pin_hashes` could still replace the hash of a *retained*
protocol, so the role constraint was bypassable through the hash mechanism added
to enforce it.

**B02-F06** MISSING REQUIREMENT · `run_pins.py`
*Was:* amendments were compared only against the preceding amendment, so one
appended after a review could retroactively change what governed a completed
cycle.
*Now:* recorded path sets catch a backdated amendment within one review
directory. They did not protect the other review directory in the same run, and
compared path lists while discarding the recorded hashes.

**B02-F08** CONTRADICTORY IMPLEMENTATION MAPPING · `run_review.py`, `bootstrap_gate.py`
*Was:* the expiry check ran only when `init` received `--bootstrap-exempt`, so
an already-exempt run kept working after a runner had been approved.
*Now:* the ordinary expiry and approval paths work. Failure to read git history
was still read as no historical approval, so the one-way expiry became
permission whenever its check could not run. The review's own "check never ran"
failure mode, at the authority boundary.

---

## Repairs claimed, awaiting cycle 04 — four

**Read this as a claim, not a status.** Written by the implementing agent about
its own work. Cycle 03 rejected nine of the twenty repair claims it examined;
that is the rate this section should be read against.

Each repair was checked by mutation: the fix deliberately broken, and the named
control confirmed to fail *for its own reason* while the others stayed green.
The qualifier matters. B02-F04's control was rewritten four times before it
discriminated, and B02-F06's version control turned red under mutation for pin
drift rather than for the thing it names, which a weaker check would have
recorded as success.

| ID | Commit | What changed | Control that fails without it |
|----|--------|--------------|-------------------------------|
| B02-F04 | `2ad9ccd` | one commit point instead of two renames; the attempt directory holds its own raw bytes and findings and is never edited again; publication re-runs before any new recording, so an interrupted publish heals itself | `test_run_review.py` · "a half-published cycle is recovered even by a command that does not write" and "the working copies match the designated generation" |
| B02-F05 | `a8922fa` | `added_pin_hashes` binds the bytes of newly added pins only, so a version change cannot arrive as an undeclared dictionary key against a retained artifact | `test_run_review.py` · "refused: an amendment that rewrites a retained pin's hash" |
| B02-F06 | `61d6c6f` | the frozen check covers every review directory in the run rather than the one freeze is working in, records keep which loop they came from, and the recorded hashes are compared as well as the paths | `test_run_review.py` · "refused: one loop freezing against history that contradicts the other loop's completed cycle" and "refused: same governing paths under a completed cycle, different versions" |
| B02-F08 | `674a394` | an unreadable git history is reported as unreadable rather than as evidence that no approval was ever recorded, so the expiry check can no longer fail open | `test_bootstrap_gate.py` · "the exception is withheld when the history cannot be read" |

**On B02-F04 and B02-F06 sharing a defect.** Both were repairs that fixed the
ordinary path and left the adversarial one standing, and in both cases the first
repair's control could not have caught the remainder. That is the pattern worth
watching in the four claims above, because it is the pattern that produced them.

---

## Raised here, not by a reviewer — one

**B02-F11** A refused capture attempt was recorded on disk but not in the
capture log, so the log and the directory disagreed about what had been
attempted. Addressed in `0629bbd`. This was found by the implementing agent
rather than by Codex, so it carries no cycle 02 identifier from the reviewer
and is not in the authoritative finding set. It is listed here so the record
is complete. **Awaiting a decision from Alex Zamurko** on whether it should be
entered into the ledger as a finding or left as a repair with no finding
attached.

*Still outstanding as at 15 September.* It has now been open longer than any
finding a reviewer raised, which is the quiet way an item stops being a decision
and becomes an omission.

---

## Codex on the declared decisions

Cycle 02's assessment, kept as the record of what it said:

> A, B, C and E remain defensible within their stated limits. D holds in the
> ordinary path but does not cure the invalid-prerequisite defect. F is
> materially improved. G's filtering is observable, but the claim that filtering
> can only delay an exit is not justified when invalidation can remove
> actionable findings. H requires the authority/staging separation above. I
> retains the first exit correctly but fails authorised resumption. J provides a
> useful conventional record, not its claimed forced external step. K is not
> fully enforced at its stated boundary. L solves the specific deadlock but its
> amendment mechanism is insufficiently constrained.

Cycle 03 revisited all twelve:

**A, B, C, E** keep their cycle-02 acceptance within their limits. No new reason
to change those dispositions.

**D** remains qualified. The invalidated-`ACCEPT` replay is repaired, but the
missing-cycle and stale-acceptance paths in B01-F11 still prevent the ledger's
authority and the controller's state from agreeing.

**F** is materially improved: the approved-plan evidence is preserved and used
in the ordinary snapshot path, and the controls exercise plan-content and
approval-decision checks.

**G** remains qualified, and the qualification is sharper than cycle 02 put it.
Ignoring an invalid resolution can delay an exit; ignoring an invalid `RAISED`
or `REOPENED` can remove an actionable finding. So `loop_state.py`'s claim that
exclusion "can only ever delay an exit, never manufacture one" is unjustified.
The defensible claim is that the calculation excludes invalid-cycle events, not
that the exclusion is conservative in one direction.

**H** is not satisfied. B02-F04's narrower repair still left a mixed
authoritative generation after interruption. *Repaired since, at `2ad9ccd`.*

**I** is partially repaired: latest-boundary `STALLED` continuation works, and
the budget-boundary contradiction is B01-F02. *Settled since by Alex Zamurko's
ruling of 15 September, at `e1e3c04`.*

**J** is now described at its actual conventional strength. Sharing a commit
with B02-F10 is defensible, since expanding the scan and correcting the prose it
newly sees are coupled changes.

**K** improves ordinary deletion resistance and checks exemptions at freeze, but
is incomplete on inability to inspect history, which is B02-F08. A successful
commit is durable against ordinary deletion; the command is not an atomic
transaction from human decision through to git commit, and its control's phrase
"no uncommitted window" overstates what the successful path shows.

**L** remains qualified. The bootstrap deadlock is relieved, but added governing
content, retained-pin hashes and cross-review history exposed B01-F04, B02-F05
and B02-F06. *All three repaired since.*
