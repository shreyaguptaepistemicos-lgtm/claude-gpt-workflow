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

# The first run of the console scan below crashed here, in the line that
# prints its own findings, because this file is a program, it now holds an
# arrow and an en dash in MUTE_SAMPLE, and it had never told its console what
# it was reading. The scan's first finding was the scanner. That is the
# cheapest possible demonstration that it reports something real, and it is
# also the fourth instance of SELF-F16 arriving while the rule for SELF-F16
# was being written.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

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


def runnable(tree: ast.Module) -> bool:
    """Whether this file is a program, by the presence of a __main__ guard."""
    for node in tree.body:
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Name) and sub.id == "__name__":
                    return True
    return False


def configures_console(tree: ast.Module, stream: str = "stdout") -> bool:
    """Whether this file tells that stream what encoding to write in.

    One stream, named, rather than either of them. The first version accepted
    a reconfigure on stdout OR stderr as proof the program could speak, which
    is two different streams treated as one fact: a program configuring stderr
    alone and printing to stdout dies exactly as before, and this said it was
    fine.

    Found on 21 October 2026 by mutation SELF-F25a, which removed the stdout
    line from ledger.py and watched the suite pass anyway, because the stderr
    line below it was still there. That is the shape this whole file exists
    for, arriving in the file itself: a check answering a question next to the
    one it was asked.
    """
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "reconfigure"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == stream):
            return True
    return False


def unprintable(tree: ast.Module) -> list[tuple[int, str]]:
    """String literals holding a character cp1252 has no room for.

    Docstrings are included on purpose. Nineteen programs here hand their
    module docstring to argparse as `description=__doc__` and two print it to
    stderr on a usage error, so a docstring is console output and a curly
    quote in one takes the program down on `--help`. Exempting docstrings
    would have been the obvious simplification and would have left the most
    common path in the repository uncovered.
    """
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            bad = sorted({c for c in node.value if ord(c) > 127})
            if bad:
                out.append((node.lineno, "".join(bad)))
    return sorted(set(out))


# The same discipline as SAMPLE above: the scan is run against a sample whose
# answers are written down, so a scan that has stopped finding anything is
# distinguishable from a repository with nothing to find.
def deaf(tree: ast.Module) -> list[tuple[int, str]]:
    """Calls that read a child process's output at the locale's mercy.

    The other half of the same defect, and not a separate one. A program
    told to emit UTF-8 is speaking a language its parent may not read:
    subprocess decodes with the locale when `text=True` is given without an
    encoding, which on Windows is cp1252. The child's bytes then fail to
    decode, `stdout` comes back None rather than raising where it happened,
    and the next line asks whether a string is in None.

    Established on 20 October 2026 rather than reasoned about. The guard was
    added to forty programs, and test_interfaces.py and test_run_review.py,
    both green until then, died with UnicodeDecodeError on byte 0x9d followed
    by TypeError: argument of type 'NoneType' is not iterable. Repairing the
    writing side alone is what broke them, which is why the two land together.

    A call with no `text=True` is exempt, for the same reason binary mode is
    exempt above: it returns bytes, and bytes do not decode.
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = (f.attr if isinstance(f, ast.Attribute)
                else f.id if isinstance(f, ast.Name) else "")
        if name not in ("run", "check_output", "Popen"):
            continue
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if "encoding" in kw:
            continue
        for flag in ("text", "universal_newlines"):
            v = kw.get(flag)
            if isinstance(v, ast.Constant) and v.value is True:
                out.append((node.lineno, flag))
                break
    return sorted(set(out))


# Same discipline again. Every DEAF line must be found and no other.
# A finding is recorded at the call's opening line, so every marker sits on
# the opening line too. The first version of this sample put one on a closing
# line and the self-check reported the scan as broken, which it was not.
DEAF_SAMPLE = '''import subprocess
a = subprocess.run(["x"], capture_output=True, text=True)        # DEAF
b = subprocess.run(["x"], capture_output=True)                   # bytes
c = subprocess.run(["x"], capture_output=True, text=True,        # named
                   encoding="utf-8")
d = subprocess.run(["x"], universal_newlines=True)               # DEAF
e = subprocess.check_output(["x"], text=True)                    # DEAF
f = some.run(["x"])                                              # no text
'''


def deaf_self_check() -> list[str]:
    lines = DEAF_SAMPLE.splitlines()
    want = {n for n, ln in enumerate(lines, 1) if "# DEAF" in ln}
    got = {ln for ln, _ in deaf(ast.parse(DEAF_SAMPLE))}
    out = []
    for n in sorted(want - got):
        out.append(f"subprocess line {n} should have been flagged and was "
                   f"not: {lines[n - 1].strip()}")
    for n in sorted(got - want):
        out.append(f"subprocess line {n} was flagged and should not have "
                   f"been: {lines[n - 1].strip()}")
    return out


MUTE_SAMPLE = [
    # (source, should_be_flagged, why)
    ('import sys\nx = "→"\nif __name__ == "__main__":\n    print(x)\n',
     True, "a program with an arrow and no console configuration"),
    ('import sys\nsys.stdout.reconfigure(encoding="utf-8")\nx = "→"\n'
     'if __name__ == "__main__":\n    print(x)\n',
     False, "the same program, configured"),
    ('x = "→"\n',
     False, "not a program; whoever runs it configures the console"),
    ('import sys\nif __name__ == "__main__":\n    print("plain")\n',
     False, "a program with nothing cp1252 cannot hold"),
    ('"""A docstring with an en dash – in it."""\nimport sys\n'
     'if __name__ == "__main__":\n    print(__doc__)\n',
     True, "a docstring is console output on --help"),
    # The case mutation SELF-F25a exposed. Configuring the stream it does not
    # print on is not configuring the stream it does.
    ('import sys\nsys.stderr.reconfigure(encoding="utf-8")\nx = "→"\n'
     'if __name__ == "__main__":\n    print(x)\n',
     True, "stderr configured, stdout left at the locale, printing to stdout"),
]


def mute_self_check() -> list[str]:
    out = []
    for src, want, why in MUTE_SAMPLE:
        tree = ast.parse(src)
        got = bool(runnable(tree) and not configures_console(tree)
                   and unprintable(tree))
        if got != want:
            out.append(f"{why}: expected {'a flag' if want else 'no flag'}, "
                       f"got {'a flag' if got else 'none'}")
    return out


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

    mute: list[str] = []

    unheard: list[str] = []

    wrong = self_check() + mute_self_check() + deaf_self_check()
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

        if runnable(tree) and not configures_console(tree):
            for ln, chars in unprintable(tree):
                mute.append(f"{rel}:{ln}  holds {chars!r} and the console is "
                            f"never told what it is reading")

        for ln, flag in deaf(tree):
            unheard.append(f"{rel}:{ln}  {flag}=True with no encoding, so the "
                           f"child is decoded at the locale")

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

    if mute:
        print()
        for m in mute:
            print(f"  FAIL: {m}")
        print("\n  Each of these is a program that can compute the right "
              "answer and die trying\n  to say it. The Windows console "
              "encodes at the locale code page, cp1252, and\n  a character "
              "outside it raises UnicodeEncodeError at the print, after the\n"
              "  work is done. That is SELF-F16, SELF-F20 and SELF-F25: the "
              "same defect three\n  times, repaired as an instance each time "
              "and never as a rule.\n\n  Two lines at the top, below the "
              "imports:\n"
              "      if hasattr(sys.stdout, \"reconfigure\"):\n"
              "          sys.stdout.reconfigure(encoding=\"utf-8\")")
        return 1

    if unheard:
        print()
        for u in unheard:
            print(f"  FAIL: {u}")
        print("\n  These are the listening half of the same defect. A child "
              "told to emit UTF-8\n  is speaking a language its parent cannot "
              "read: subprocess decodes with the\n  locale when text=True "
              "carries no encoding, the decode fails, and stdout comes\n  "
              "back None rather than raising where it happened. The next line "
              "then asks\n  whether a string is in None.\n\n  Name it at the "
              "call: subprocess.run(..., text=True, encoding=\"utf-8\").")
        return 1

    print("  [ok] every program that holds a character cp1252 cannot encode "
          "configures its console")
    print("  [ok] every call that reads a child as text names the encoding "
          "it reads with")
    print("\n  Note: this does not check that the encoding named is the "
          "right one.")
    print("  Note: a module with no __main__ guard is not examined for "
          "console output. Its\n  strings are printed by whichever program "
          "imported it, and reconfigure applies\n  to the process, so the "
          "program is the right place to ask. A program with no\n  "
          "non-ASCII of its own that prints a library's is therefore not "
          "covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
