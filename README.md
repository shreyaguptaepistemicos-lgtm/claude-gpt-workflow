# EpistemicOS review workflow

The machinery that reviews implementation work against a governing protocol.
A plan or an implementation is reviewed by a second party, up to four times.
Each cycle freezes exactly what was reviewed, captures the reviewer's reply
verbatim, and records every finding and its disposition. A loop controller
decides from that record alone whether to continue, and a human decides at the
end. The point of the machinery is that none of those steps can be skipped
quietly.

## Start here

```
python scripts/dry_run.py
```

That drives the whole sequence against a throwaway repository and prints what
an operator would see. Under a minute, and it is the fastest way to understand
the layer.

```
python scripts/test_ledger.py        # or any other suite
```

## What this repository is, and is not

This is a **scope-limited copy** of the review and verification workflow from a
private repository. It was assembled deliberately, file by file, and carries a
clean history with no connection to the original.

**Not here, and not by accident:**

- the citation extractor and the research-object extraction code
- the manuscript corpus used to test them
- product-specific research rules and their specifications
- `runs/BOOTSTRAP-002` and `runs/BOOTSTRAP-003`

**Here, and the most useful thing in the repository:** `runs/BOOTSTRAP-001`,
a complete four-cycle review of this machinery by a second party. Every
frozen target, every reviewer reply verbatim, the finding ledger and the
summaries. It is the difference between reading how a review is supposed to
work and reading one that happened, including its unresolved findings.

The two runs that are absent are absent whole. BOOTSTRAP-002's fourth cycle
carries copies of the citation control suites, as evidence of what that cycle
examined, and the cycle's recorded digests cover them. A partial copy with
inconsistent hashes would undermine the verification principle this workflow
exists to implement, so it is not here at all rather than here in pieces.

**A consequence worth knowing before you run anything:** a frozen cycle binds
to the commit it was frozen against, in the repository where the review was
performed. This repository has its own history, so MC-2 check 8, "referenced
git commit exists", cannot resolve those commits and reports the cycles as
INVALID here. Every other check on them passes.

That is the protocol working rather than failing. A review record cannot be
moved into a different repository and still claim to be anchored there, and
the gate says so instead of pretending otherwise. It does mean the loop
controller reports no valid cycles for BOOTSTRAP-001 in this copy, so read the
cycle directories as the historical record they are. Whether "this checkout
cannot resolve that commit" should be reported as a distinct state from "that
commit does not exist" is an open question, tracked in the issues.

## The order

```
run_review.py init      pin the protocol and specs for a run
run_review.py freeze    open a cycle, snapshot what is reviewed, compose the
                        reviewer's input - the implementing agent does not
                        author it
run_review.py record    store the reply verbatim, extract findings, run MC-2
validate_cycle.py       the MC-2 gate; a cycle that fails is INVALID and does
                        not consume the four-cycle budget
ledger.py               raise / respond / resolve, with persistent identifiers
loop_state.py           CONTINUE, CONVERGED, HUMAN_ADJUDICATION_REQUIRED,
                        STALLED or MAX_4_REACHED, computed from the ledger
approval_package.py     assemble the package a human decides from
bootstrap_gate.py       record that decision
exit_criteria.py        the four exit conditions, machine-checkable half
```

`_probe/mutate_repairs.py` is the mutation probe. It breaks each repair on
purpose and requires the control named for it to go red. A control that cannot
fail is not a control, and this layer has contained several.

## Nothing here is technically enforced

`MC1_ENFORCEMENT` is `CONVENTION_ONLY`. Every check is detection that holds
while the checks run faithfully and nobody edits the records they read, and the
same writable code performs the checks on itself. That is recorded in each run
rather than assumed, and the machinery refuses to claim more.
