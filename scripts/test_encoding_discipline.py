#!/usr/bin/env python3
"""No file in this repository is read or written at the locale's mercy.

    python scripts/test_encoding_discipline.py

Exit 0 = every text read and write names its encoding.

Why this file exists
--------------------
Two defects in two days, both the same shape, neither found by a control:

SELF-F11, 14 October. Every local mutation sweep log was written by
PowerShell's `>` redirect, which emits UTF-16LE. `exit_criteria.py` read it as
UTF-8 with errors="replace", so a complete and clean sweep arrived as
replacement characters and the checker reported that the log said nothing.

SELF-F12, 14 October. `test_citation_extract.py` opened its own subject's
source with a bare `open(...)`, which uses the machine's locale code page.
On Linux that is UTF-8 and the suite passed. On Windows it is cp1252,
`citation_extract.py` holds a byte cp1252 has no character for, and the suite
crashed before reporting anything. It had been passing on Windows only in
shells where somebody had typed `PYTHONUTF8=1` by hand.

The second one is the reason this file scans rather than fixing one line. A
suite whose result depends on an environment variable someone remembered to
set is not a control, and the fault was never in that one call: it was in
nothing ever asking. Fixing the example and leaving the rule is the single
largest source of rework in this repository, and this is the rule.

What it checks
--------------
Every `open()`, `.read_text()` and `.write_text()` in scripts/ and _probe/
must name an encoding. Binary modes are exempt, because bytes do not decode.
`.read_bytes()` and `.write_bytes()` are not examined for the same reason.

Parsed with `ast` rather than matched with a regular expression, so a call
spread across lines is seen and the word "encoding" inside a comment or a
string is not mistaken for an argument.

What it does NOT check
----------------------
It says nothing about whether the encoding named is the right one. A file
written as UTF-8 and read as UTF-16 would satisfy every line here. That is a
narrower defect than the one this exists for, and naming the limit is cheaper
than implying it is covered.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Which calls decode is decided in kind() below rather than by a name list,
# because three different functions here are spelled `open` and only two of
# them have an encoding at all. read_bytes and write_bytes are absent on
# purpose: bytes do not decode.

# The probe's disposable checkouts are copies of this repository, so scanning
# them would report every finding twice and would report a finding at all for
# a directory that exists only while a sweep is running.
SKIP_DIRS = {".probe-sandboxes", "__pycache__", ".git", "runs"}


def sources() -> list[Path]:
    out = []
    for d in ("scripts", "_probe"):
        for p in sorted((REPO / d).rglob("*.py")):
            if SKIP_DIRS & set(p.relative_to(REPO).parts):
                continue
            out.append(p)
    return out


def kind(node: ast.Call) -> str:
    """Which decoding call this is, or "" for calls that are none of them.

    Three things in this repository are spelled `open` and only two of them
    decode anything. The first version of this function matched on the name
    alone and reported all four of its first findings wrongly, which is the
    defect it was written to catch, arriving in the catcher:

      open(path, "rb")   builtin, mode in the SECOND argument
      p.open("rb")       Path.open, mode in the FIRST argument
      os.open(path, …)   a file descriptor, no encoding parameter at all

    Reporting os.open is not a strict reading of the rule. It is a check
    firing for a reason other than the one it names.
    """
    f = node.func
    if isinstance(f, ast.Name):
        return "builtin_open" if f.id == "open" else ""
    if isinstance(f, ast.Attribute):
        if f.attr in ("read_text", "write_text"):
            return f.attr
        if f.attr == "open":
            base = f.value
            if isinstance(base, ast.Name) and base.id == "os":
                return ""
            if isinstance(base, ast.Name) and base.id == "io":
                return "builtin_open"
            return "path_open"
    return ""


def binary(node: ast.Call, what: str) -> bool:
    """open(path, "rb") and p.open("rb"), which decode nothing.

    The mode's position differs between the two, which is the whole reason
    `what` is passed in rather than guessed at.
    """
    idx = 1 if what == "builtin_open" else 0
    mode = None
    if len(node.args) > idx and isinstance(node.args[idx], ast.Constant):
        mode = node.args[idx].value
    for k in node.keywords:
        if k.arg == "mode" and isinstance(k.value, ast.Constant):
            mode = k.value.value
    return isinstance(mode, str) and "b" in mode


# A scan that reports nothing is indistinguishable from a clean repository,
# and after the four false positives above were removed the obvious next
# mistake was removing too much. Every line marked FLAG must be found and no
# other line may be. The probe holds a mutation that removes an encoding from
# a real read elsewhere, which covers the same ground from the other side; this
# is here so the suite does not depend on the probe having been run.
SAMPLE = '''import os
import io
from pathlib import Path
p = Path("x")
a = open("f")                          # FLAG builtin, no encoding
b = open("f", "rb")                    # binary
c = open("f", encoding="utf-8")        # named
d = p.open("rb")                       # Path.open binary, mode in arg 0
e = p.open()                           # FLAG Path.open text, no encoding
f = os.open("f", 0)                    # a file descriptor, no encoding exists
g = p.read_text()                      # FLAG
h = p.read_text(encoding="utf-8")      # named
i = p.read_bytes()                     # bytes do not decode
j = io.open("f", "rb")                 # binary
k = p.write_text("s")                  # FLAG
'''


def self_check() -> list[str]:
    """Run the scan over SAMPLE and compare against its FLAG markers."""
    lines = SAMPLE.splitlines()
    want = {n for n, ln in enumerate(lines, 1) if "# FLAG" in ln}
    got = set()
    for node in ast.walk(ast.parse(SAMPLE)):
        if not isinstance(node, ast.Call):
            continue
        what = kind(node)
        if not what:
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue
        if what in ("builtin_open", "path_open") and binary(node, what):
            continue
        got.add(node.lineno)
    out = []
    for n in sorted(want - got):
        out.append(f"line {n} should have been flagged and was not: "
                   f"{lines[n - 1].strip()}")
    for n in sorted(got - want):
        out.append(f"line {n} was flagged and should not have been: "
                   f"{lines[n - 1].strip()}")
    return out


def main() -> int:
    bad: list[str] = []
    unreadable: list[str] = []
    files = sources()

    wrong = self_check()
    if wrong:
        print("encoding discipline")
        print("  the scan does not agree with its own sample, so nothing it "
              "says about\n  the repository below can be relied on:")
        for w in wrong:
            print(f"    FAIL: {w}")
        return 1

    for p in files:
        rel = p.relative_to(REPO).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            unreadable.append(f"{rel}: {e.__class__.__name__}: {e}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            what = kind(node)
            if not what:
                continue
            if any(k.arg == "encoding" for k in node.keywords):
                continue
            if what in ("builtin_open", "path_open") and binary(node, what):
                continue
            shown = "open" if what.endswith("open") else what
            bad.append(f"{rel}:{node.lineno}  {shown}() names no encoding")

    print("encoding discipline")
    print("  [ok] the scan agrees with its own sample: every FLAG line found, "
          "no others")
    print(f"  {len(files)} source file(s) in scripts/ and _probe/")

    if unreadable:
        for u in unreadable:
            print(f"  FAIL: a source file could not be parsed: {u}")
        return 1

    if bad:
        print()
        for b in bad:
            print(f"  FAIL: {b}")
        print("\n  Each of these decodes at the mercy of whatever locale the "
              "process happens\n  to have. That is how test_citation_extract "
              "passed on Linux and in one\n  Windows shell and crashed in "
              "another, with nothing to say which it was.\n  Name the "
              "encoding: read_text(encoding=\"utf-8\").")
        return 1

    print("  [ok] every text read and write names its encoding")
    print("\n  Note: this does not check that the encoding named is the "
          "right one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
