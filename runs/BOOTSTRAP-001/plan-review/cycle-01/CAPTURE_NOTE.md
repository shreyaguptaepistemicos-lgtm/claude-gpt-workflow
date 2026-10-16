# Two captures of the same reviewer output

There are two files in this cycle carrying Codex's response. This note says why,
because a reader finding two should not have to guess which one governs.

```text
codex-output-raw.md              4f554ce182bd1202…  14,754 bytes  authoritative
codex-output-direct-capture.md   f34cf24cb291ed15…  15,080 bytes  more faithful
```

Both contain the same eighteen findings with identical finding text. Neither
contains anything the other omits in substance.

## What happened

The clipboard capture failed three times. Twice, `codex-output-raw.md` was
recorded containing seventy bytes of shell command text rather than the review,
because copying the capture command from a chat window overwrote the clipboard
holding the reply. MC-2 returned PASS on both of those, since check 5 asks only
whether the file is non-empty.

The third attempt reached the file by a different route: the reply had been
pasted into the implementing agent's chat transcript, and the agent wrote it back
out from there. That is what `codex-output-raw.md` now contains, and it is what
`invocation.json` records.

The operator's direct save from the Codex panel had in fact succeeded, into
`scripts/reply.md`, and was found afterwards. That file is
`codex-output-direct-capture.md` here.

## How they differ

The direct capture preserves what a retyped transcription loses:

```text
`---` horizontal rules between findings
trailing double-spaces (markdown hard line breaks)
curly punctuation: runner’s, “proves the artifact did not change.”
no trailing newline
```

`codex-output-raw.md` has straight quotes, no rules, no trailing spaces, and a
final newline. Every difference is punctuation or whitespace introduced by the
transcription. No word of any finding differs.

## Why the less faithful file is still the authoritative one

`codex-output-raw.md` is write-once under MC-1 and was recorded before the
direct capture was found. Replacing it would mean the implementing agent
overwriting recorded reviewer output after the fact, which is the specific act
MC-1 exists to prevent, and the justification available — that this run is
labelled `NOT_A_PROTOCOL_CYCLE` — had already been used three times today to
authorise deleting evidence. A rule that yields every time it is inconvenient is
not a rule.

So the record keeps both, and this note makes the discrepancy visible rather
than resolving it silently in favour of whichever file is nicer.

## What this is evidence of

The capture path has no owner. §2.2 gives the review runner ownership of
composing the input and writing the output to the evidence directory, but the
runner does not invoke the reviewer, so getting the reply from the reviewer to
the runner is a manual step performed by whoever is present. Here that produced
three junk captures, two of which passed MC-2, and a fourth that travelled
through the implementing agent.

This is the same gap as finding B01-F03, one step earlier in the chain, and it
is recorded here as a nineteenth observation rather than smoothed over.
