#!/usr/bin/env python3
"""Convert the protocol docx to Markdown and verify the result two ways.

    python scripts/convert_protocol.py \
        --docx "Untitled document (4).docx" \
        --out specs/implementation-review-protocol-v1.1.md \
        --terminal "Preservation verdict"

Exit 0 = both checks passed and the file was written.
Exit 1 = a check failed; nothing is written.
Exit 2 = could not run.

Why two checks
--------------
Conversion fidelity catches a lossy conversion. It cannot catch a truncated
input, because a faithful conversion of a truncated document passes perfectly.
That is how v1.0 was first committed from a source that stopped mid-row after
V21: the fidelity check was correct and the answer it gave was correct, and the
document was still incomplete. Completeness is a separate question and needs a
separate check.

What each check establishes, and what it does not
-------------------------------------------------
FIDELITY compares the alphanumeric word sequence of the docx against the
Markdown. It establishes that no word was dropped, added or reordered. It does
NOT establish that punctuation, emphasis, or table alignment survived, because
markdown syntax is punctuation and is excluded from the comparison by
construction.

COMPLETENESS establishes that the verification table runs from V01 with strictly
increasing identifiers, no gaps, uniform field count, and that a declared
terminal marker follows the last row. It does NOT establish that the source is
the newest draft, nor that V44 is the correct final row. It establishes that the
document does not stop in the middle of itself.

Neither check establishes that this docx is the document Alex intended to send.
That remains a human confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:
    print("python-docx is required:  pip install python-docx --break-system-packages",
          file=sys.stderr)
    raise SystemExit(2)

WORD = re.compile(r"[0-9A-Za-z]+(?:['’][0-9A-Za-z]+)*")
VROW = re.compile(r"\A\s*\|?\s*V(\d{1,3})\s*\|")


def words(text: str) -> list[str]:
    return WORD.findall(text)


def source_lines(path: Path) -> list[str]:
    """The document as one flat list of logical lines, in document order.

    A docx can carry the verification table two ways, and both have arrived:
    as pipe-delimited paragraphs, or as a real Word table. Normalising both to
    the same pipe form here means the three checks below do not each need to
    know which kind of document they were handed.

    python-docx exposes paragraphs and tables as separate collections with no
    document order between them, so the body XML is walked directly.
    """
    doc = Document(str(path))
    body = doc.element.body
    out: list[str] = []
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            # A paragraph can carry soft line breaks, which python-docx returns
            # as \n inside one paragraph's text. They are line breaks the author
            # typed, so each becomes its own logical line. Without this the
            # structure check counts one source line against several output
            # lines and fails on a document that is perfectly fine.
            out.extend(Paragraph(child, doc).text.split("\n"))
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                out.append("| ".join(cells))
    return out


def write_lf(p: Path, text: str) -> None:
    """LF on every platform, so PROTOCOL_HASH is a property of the content."""
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ------------------------------------------------------------------ convert

def to_markdown(paras: list[str]) -> str:
    """One source paragraph to one output line. Nothing is promoted.

    The docx carries no heading styles: every paragraph is 'normal'. Any heading
    in the output would therefore be this script's invention, not the author's
    structure. An earlier version promoted numbered paragraphs to '##' and turned
    sixteen list items into sections, including the steps inside the
    PLAN_DEVIATION control. Word-sequence fidelity passed it clean, because '##'
    contributes no words.

    So the only things added here are markdown table separator rows and cell
    padding. A document whose hash becomes PROTOCOL_HASH should not be improved
    in transit; if headings are wanted, that is a declared transform of its own.
    """
    out: list[str] = []
    in_table = False

    for raw in paras:
        line = raw.rstrip()

        if not line.strip():
            in_table = False
            out.append("")
            continue

        # A pipe-delimited row: the header opens a table, V-rows continue it.
        if "|" in line and (VROW.match(line) or re.match(r"\A\s*\|?\s*ID\s*\|", line)):
            cells = [c.strip() for c in line.split("|")]
            out.append("| " + " | ".join(cells) + " |")
            if not in_table:
                out.append("|" + "---|" * len(cells))
                in_table = True
            continue

        in_table = False
        out.append(line.strip())

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


SEPARATOR = re.compile(r"\A\|(?:-+\|)+\Z")


def check_structure(paras: list[str], md: str) -> Check:
    """One source paragraph, one output line.

    Word-sequence fidelity is blind to anything made only of punctuation, which
    is what markdown syntax is. This is the check that would have caught the
    invented headings: it counts lines rather than words.
    """
    c = Check()
    src = [p.strip() for p in paras if p.strip()]
    got = [l for l in md.splitlines() if l.strip() and not SEPARATOR.match(l)]
    seps = sum(1 for l in md.splitlines() if SEPARATOR.match(l))
    c.add(f"one output line per source paragraph "
          f"({len(src)} paragraphs, {len(got)} lines, {seps} table separators)",
          len(src) == len(got),
          "" if len(src) == len(got) else
          f"the conversion {'added' if len(got) > len(src) else 'dropped'} "
          f"{abs(len(got) - len(src))} line(s)")
    added = [l for l in got if l.startswith("#")]
    c.add("no headings invented", not added,
          "" if not added else
          f"{len(added)} line(s) promoted to headings, e.g. {added[0][:70]!r}\n"
          "the source has no heading styles, so any heading is invented here")
    return c


# ------------------------------------------------------------------ checks

class Check:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(o for _, o, _ in self.rows)

    def report(self) -> str:
        out = []
        for name, o, detail in self.rows:
            out.append(f"  [{'PASS' if o else 'FAIL'}] {name}")
            if detail:
                for ln in detail.splitlines():
                    out.append(f"         {ln}")
        return "\n".join(out)


def check_fidelity(paras: list[str], md: str) -> Check:
    c = Check()
    src = [w for p in paras for w in words(p)]
    got = words(md)
    c.add(f"word sequence identical ({len(src)} words)", src == got,
          "" if src == got else _first_divergence(src, got))
    return c


def _first_divergence(a: list[str], b: list[str]) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return (f"first divergence at word {i}\n"
                    f"  source   ... {' '.join(a[max(0,i-5):i+5])}\n"
                    f"  markdown ... {' '.join(b[max(0,i-5):i+5])}")
    return f"length differs: source {len(a)}, markdown {len(b)}"


def check_completeness(paras: list[str], terminal: str) -> Check:
    c = Check()

    header_i = next((i for i, p in enumerate(paras) if re.match(r"\A\s*\|?\s*ID\s*\|", p)), None)
    if header_i is None:
        c.add("verification table header found", False,
              "no row beginning 'ID|'; the table may be absent entirely")
        return c
    c.add("verification table header found", True)
    n_fields = len(paras[header_i].split("|"))

    rows = [(i, p) for i, p in enumerate(paras) if VROW.match(p)]
    if not rows:
        c.add("verification rows present", False, "no V-rows matched")
        return c
    ids = [int(VROW.match(p).group(1)) for _, p in rows]

    # C1 strictly increasing from V01, in document order.
    inc = ids[0] == 1 and all(b > a for a, b in zip(ids, ids[1:]))
    c.add(f"identifiers increase from V01 ({len(ids)} rows, "
          f"V{ids[0]:02d}–V{ids[-1]:02d})", inc,
          "" if inc else f"sequence not strictly increasing: {ids}")

    # C2 no gaps.
    gaps = [n for n in range(1, max(ids) + 1) if n not in set(ids)]
    c.add("no gaps in the sequence", not gaps,
          "" if not gaps else f"missing: {', '.join(f'V{n:02d}' for n in gaps)}")

    # C3 uniform field count. This is the one that catches a row cut in half:
    # a dangling "V2" parses as an identifier already seen, so contiguity alone
    # passes on a truncated document. Field count does not.
    ragged = [(f"V{int(VROW.match(p).group(1)):02d}", len(p.split("|")))
              for _, p in rows if len(p.split("|")) != n_fields]
    c.add(f"every row has {n_fields} fields", not ragged,
          "" if not ragged else
          "rows with the wrong field count: " +
          ", ".join(f"{k} has {v}" for k, v in ragged) +
          "\na row shorter than the header is a row cut off mid-write")

    # C4 the document continues past the table into a declared terminal section.
    last_row_i = rows[-1][0]
    after = [p for p in paras[last_row_i + 1:] if p.strip()]
    found = any(terminal.lower() in p.lower() for p in after)
    c.add(f"terminal marker {terminal!r} follows the last row", found,
          "" if found else
          f"nothing after V{ids[-1]:02d} matches it; only "
          f"{len(after)} non-empty paragraph(s) follow, ending "
          f"{after[-1].strip()[:60]!r}" if after else
          f"nothing at all follows V{ids[-1]:02d}; the document ends mid-table")

    return c


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--terminal", required=True,
                    help="section title expected after the last V-row")
    ap.add_argument("--dry-run", action="store_true",
                    help="run both checks and report, write nothing")
    a = ap.parse_args(argv[1:])

    src = Path(a.docx)
    if not src.is_file():
        print(f"not found: {src}", file=sys.stderr)
        return 2

    paras = source_lines(src)
    md = to_markdown(paras)

    print(f"source   {src.name}")
    print(f"         {len(paras)} paragraphs")
    print()
    print("CONVERSION FIDELITY")
    fid = check_fidelity(paras, md)
    print(fid.report())
    print()
    print("CONVERSION STRUCTURE")
    struct = check_structure(paras, md)
    print(struct.report())
    print()
    print("SOURCE COMPLETENESS")
    comp = check_completeness(paras, a.terminal)
    print(comp.report())
    print()

    if not (fid.ok and struct.ok and comp.ok):
        print("RESULT: FAIL — nothing written.")
        return 1

    if a.dry_run:
        print("RESULT: PASS (dry run, nothing written)")
        return 0

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_lf(out, md)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()

    print("RESULT: PASS")
    print(f"wrote {out}  ({out.stat().st_size} bytes)")
    print()
    print(f"PROTOCOL_HASH  {digest}")
    print("Record this with the commit as PROTOCOL_HASH; PROTOCOL_COMMIT is the")
    print("commit that contains it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
