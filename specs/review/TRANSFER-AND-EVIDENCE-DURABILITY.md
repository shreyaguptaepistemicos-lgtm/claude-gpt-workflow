# What survives a repository transfer, tested rather than assumed

22 October 2026. Alex Zamurko asked whether moving `epistemicos` into a
GitHub organisation was the right way forward, and the honest answer was that
one part of it was unknown: GitHub documents that issues, pull requests,
wikis, stars and watchers move with a repository, and says nothing at all
about Actions run history or artifacts.

That silence matters here more than it would elsewhere. Every execution
evidence record this repository holds points at an Actions run URL. If those
did not survive a transfer we would destroy the evidence in the act of
protecting it, and every automated check would keep reporting it as present,
because the checks verify that a record names a run rather than that the run
can still be opened.

So it was tested on something disposable first, which is what he agreed to.

## The test

```text
repository   S-hreyaGupta/transfer-probe, private, created for this
workflow     one job: writes a file, renders a step summary from it,
             uploads it as an artifact with retention-days 400
run          probe #1, success, 13s, commit 2a223d5
destination  epistemicos-probe, a free organisation created for this
```

Private deliberately. A public repository might behave differently and the
case we care about is a private one.

## The result

All four survived.

```text
the run            probe #1 present under the new owner, still Success
the log            opens, job still listed at 9s
the step summary   renders, with its original timestamp
                   "evidence produced at Thu Oct 22 13:52:29 UTC 2026"
the artifact       downloads, 50 bytes, same contents
the old URL        github.com/S-hreyaGupta/transfer-probe/... redirects
                   to the organisation rather than 404ing
```

The redirect is the most important line. It means the evidence records
already written, which name the old owner, keep resolving after a move.

## What this does not establish

The probe repository had one run and one small artifact. A repository with
three hundred runs may behave differently, and GitHub's own documentation
notes that a transfer can permanently retire the old name when a repository
had more than a hundred Actions uses in the preceding week, which
`epistemicos` has. Retiring a name prevents its reuse; it is not the same as
breaking redirects, and this test did not exercise that path.

It also says nothing about timing. The transfer moved within a minute or two
at this size.

## The related finding

Checking this turned up something unrelated to transfers and worse.
`SELF-F27`: the sweep artifact had no retention period, so GitHub's
ninety-day default applied, and EC-2's evidence would have deleted itself
around 19 January 2027 with every control still green. Retention is now
stated, and the real repair is that the log is committed into the repository
rather than held only on a service that expires it.

Evidence that lives somewhere with a clock on it is evidence with a clock on
it, and the clock was not visible from inside.
