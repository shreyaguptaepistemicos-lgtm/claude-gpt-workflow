#!/usr/bin/env python3
"""Verify that the governing protocol differs from its source by declared edits only.

    python scripts/verify_amendment.py --docx <source docx>

Exit 0 = the committed protocol equals the conversion of that docx plus exactly
the amendments declared below, and nothing else.
Exit 1 = it does not.
Exit 2 = could not run.

Why this exists
---------------
§0.1 makes the git artifact authoritative, not the docx. So an amendment made
directly to the markdown is legitimate. But it costs something: once the markdown
is no longer a byte-faithful conversion, `convert_protocol.py` can no longer
establish that nothing else was changed at the same time, and "I only changed one
line" becomes an assertion rather than a check.

This restores the check. It reconverts the docx, applies each declared amendment
in order, and requires the result to be byte-identical to the committed file. An
undeclared edit — a word softened, a rule loosened, a line dropped — fails here,
because the reconstruction would no longer match.

The amendments are data, not prose. Adding one means adding a tuple, which is a
diff someone reviews, rather than a sentence someone reads past.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONVERTER = REPO / "scripts" / "convert_protocol.py"
PROTOCOL = REPO / "specs" / "implementation-review-protocol-v1.1.md"

# (old, new, why, authorised_by). Applied in order, once each.
AMENDMENTS: list[tuple[str, str, str, str]] = [
    (
        "specs/implementation-review-protocol-v1.0.md",
        "specs/implementation-review-protocol-v1.1.md",
        "§0.1's recommended location named the superseded filename, so the "
        "governing document pointed at a document it had replaced. That is "
        "operational metadata rather than an inert typo: it creates exactly the "
        "which-copy-are-you-reading ambiguity §0.1 exists to remove.",
        "Alex Zamurko, 8 September 2026, in #gap: \"fix it. Do not merely "
        "record it.\"",
    ),
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docx", required=True)
    ap.add_argument("--terminal", default="Preservation verdict")
    a = ap.parse_args(argv[1:])

    if not Path(a.docx).is_file():
        print(f"not found: {a.docx}", file=sys.stderr)
        return 2
    if not PROTOCOL.is_file():
        print(f"not found: {PROTOCOL}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        conv = Path(td) / "as_converted.md"
        r = subprocess.run([sys.executable, str(CONVERTER), "--docx", a.docx,
                            "--out", str(conv), "--terminal", a.terminal],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("the source docx does not pass conversion, so the committed "
                  "file cannot be reconstructed from it:\n")
            print(r.stdout)
            return 1

        text = conv.read_text(encoding="utf-8")
        as_converted = hashlib.sha256(text.encode()).hexdigest()

        print(f"source docx    {hashlib.sha256(Path(a.docx).read_bytes()).hexdigest()}")
        print(f"as converted   {as_converted}")
        print()
        print(f"declared amendments: {len(AMENDMENTS)}")

        for i, (old, new, why, who) in enumerate(AMENDMENTS, start=1):
            n = text.count(old)
            if n == 0:
                print(f"  {i}. NOT APPLICABLE — {old!r} is not in the converted text")
                print("     Either the source already carries the amendment, or the "
                      "amendment is stale and should be removed from this list.")
                return 1
            text = text.replace(old, new, 1)
            print(f"  {i}. {old}")
            print(f"     -> {new}")
            print(f"     {why}")
            print(f"     authorised: {who}")
            if n > 1:
                print(f"     note: {n} occurrences present, only the first replaced")

        reconstructed = hashlib.sha256(text.encode()).hexdigest()
        committed = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()

        print()
        print(f"reconstructed  {reconstructed}")
        print(f"committed      {committed}")
        print()

        if reconstructed == committed:
            print("PASS — the committed protocol is the conversion of this docx plus "
                  "the declared amendments, and nothing else.")
            return 0

        print("FAIL — the committed protocol contains changes this file does not "
              "declare.")
        import difflib
        d = list(difflib.unified_diff(
            text.splitlines(), PROTOCOL.read_text(encoding="utf-8").splitlines(),
            "reconstructed", "committed", lineterm="", n=1))
        print("\n".join(d[:60]))
        if len(d) > 60:
            print(f"... {len(d) - 60} more diff lines")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
