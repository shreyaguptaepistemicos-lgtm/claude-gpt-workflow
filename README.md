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
- `runs/`, the real frozen review cycles

The last of those is worth explaining. The review evidence from actual runs
lives in cycle directories that also carry copies of the citation test suites,
so including it would have exceeded the scope and been the largest leak risk
in the exercise. The cost is that you are looking at the machinery rather than
at a completed review. `dry_run.py` exists to close most of that gap.

**A consequence worth knowing before you run anything:** several controls bind
evidence to git commits. In the original repository those commits exist. Here
they do not, so anything asking "was this cycle frozen at that commit" has
nothing to resolve. That is the copy being a copy, not a defect.

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
