#!/usr/bin/env python3
"""Nothing operational may reference a superseded protocol version.

    python scripts/test_protocol_pin.py

Exit 0 = every operational reference names the governing protocol.

Why this exists
---------------
test_prompts.py reads the finding vocabulary out of the protocol rather than
restating it, so a hand-copied list cannot drift. But the *path* to the protocol
was itself hand-written, and it stayed pinned to v1.0 after v1.1 landed. It kept
passing, because the vocabulary happened not to change between the two versions,
so a green result meant the prompts agreed with a superseded document and looked
exactly like the right answer.

Alex Zamurko, 8 September 2026, in #gap:

    A green test against a superseded protocol is a false assurance failure.
    ... This should remain under test so future protocol-version changes cannot
    silently leave validators behind.

This is that test. It fails when a validator, runner or prompt names a protocol
version that is not the governing one.

What "governing" means here, and why it is not inferred
------------------------------------------------------
The governing version is read from specs/PROTOCOL_STATUS.md, the record document
that already declares it. It is deliberately NOT inferred by taking the highest
version file present in specs/, because that would make an unfinished v1.2 draft
governing the moment someone saved it, which is the ambiguity §0.1 exists to
remove.

Binding to the record document also means the record and the code cannot drift
apart: bumping the protocol without updating the record fails here, and updating
the record without repinning the code fails here too.

No whitelist
------------
One legitimate reference to a superseded version exists: the *old* side of a
declared amendment in verify_amendment.py, which must name v1.0 or the amendment
could not be applied. That exception is derived by importing the live AMENDMENTS
list, not by maintaining a list of blessed lines here. A hand-maintained
exception list is a list that grows every time this check is inconvenient, and
then the check means nothing.

specs/PROTOCOL_STATUS.md is excluded from the scan for the same reason: it is
the supersession record, so naming the superseded file is its job. Excluding it
is safe only because check 1 verifies it is internally consistent, and that is
the point of doing them in this order.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATUS = "specs/PROTOCOL_STATUS.md"

PROTO_REF = re.compile(r"implementation-review-protocol-v(\d+)\.(\d+)\.md")

# Files scanned for references. Prompts are included because they are handed to
# a model as instructions: a prompt naming the wrong protocol is operational
# metadata pointing at a superseded document, which is the defect Alex
# distinguished from an inert typo.
#
# Recursive deliberately. The first version used specs/*.md, which does not
# descend, so eighteen files were invisible to it including all thirteen A.1-E
# specifications. None of them referenced the protocol at the time, so the check
# was green and the hole was undetectable from its output. A scan that silently
# covers less than it appears to is the same shape as a check that cannot come
# back false.
SCAN = ("scripts/**/*.py", "specs/**/*.md")

# Not scanned, each for a stated reason rather than because it was failing.
EXCLUDE = {
    "specs/PROTOCOL_STATUS.md":
        "the supersession record; naming the superseded file is its purpose, "
        "and check 1 verifies it is internally consistent",
}


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"  [ok] {msg}")

    def bad(self, msg: str) -> None:
        self.failures.append(msg)


# ------------------------------------------------------------------ reading

def declared(root: Path) -> tuple[str, str, str]:
    """(version, governing path, protocol hash) as the record document states.

    Raises ValueError if the record cannot be read, which is itself a finding:
    a record document that cannot be parsed cannot govern anything.
    """
    p = root / STATUS
    if not p.is_file():
        raise ValueError(f"{STATUS} does not exist; nothing declares which "
                         "protocol version governs")
    text = p.read_text(encoding="utf-8")

    m = re.search(r"^VERSION\s+v(\d+\.\d+)\s*$", text, re.M)
    if not m:
        raise ValueError(f"{STATUS} has no 'VERSION vN.N' line")
    version = m.group(1)

    sec = re.search(r"^## The governing file\s*\n+`([^`]+)`", text, re.M)
    if not sec:
        raise ValueError(f"{STATUS} has no '## The governing file' section "
                         "naming a path in backticks")
    path = sec.group(1)

    h = re.search(r"^PROTOCOL_HASH\s+([0-9a-f]{64})\s*$", text, re.M)
    if not h:
        raise ValueError(f"{STATUS} has no 'PROTOCOL_HASH <sha256>' line")

    return version, path, h.group(1)


AMENDMENT_FILE = "scripts/verify_amendment.py"


def amendment_olds(root: Path) -> set[str]:
    """The old-side strings of declared amendments, read from the live list.

    Derived rather than listed. If an amendment is removed, its exception
    disappears with it and a stale reference starts failing again.
    """
    va = root / AMENDMENT_FILE
    if not va.is_file():
        return set()
    spec = importlib.util.spec_from_file_location("_va_probe", va)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {old for old, _new, _why, _who in getattr(mod, "AMENDMENTS", [])}


def is_declared_amendment_line(rel: str, line: str, olds: set[str]) -> bool:
    """True only for the literal old-side entry inside the declaring file.

    The first version of this asked whether the line *contained* a declared old
    string. That let every stale reference through, because a stale reference is
    a line containing exactly that path. Both of the controls below passed
    silently against it. The exception has to be narrow enough that only the
    declaration itself satisfies it: the right file, and a line that is the
    quoted string and nothing else.
    """
    if rel != AMENDMENT_FILE:
        return False
    s = line.strip().rstrip(",").strip()
    return any(s in (f'"{o}"', f"'{o}'") for o in olds)


# ------------------------------------------------------------------ checks

def check(root: Path, verbose: bool = True) -> list[str]:
    """Run every check against `root`. Returns the list of failures."""
    r = Result()

    def say(*a) -> None:
        if verbose:
            print(*a)

    # ---- 1  the record document is internally consistent ----
    say("record document")
    try:
        version, path, recorded_hash = declared(root)
    except ValueError as e:
        r.bad(str(e))
        return r.failures

    m = PROTO_REF.search(path)
    if not m:
        r.bad(f"the governing path in {STATUS} is not a protocol filename: {path!r}")
        return r.failures
    path_version = f"{m.group(1)}.{m.group(2)}"

    if path_version != version:
        r.bad(f"{STATUS} declares VERSION v{version} but its governing file is "
              f"{path}; the record contradicts itself and cannot be used to "
              "pin anything")
        return r.failures
    r.ok(f"declares v{version}, governing file agrees")

    gov = root / path
    if not gov.is_file():
        r.bad(f"{STATUS} names {path} as governing, but that file does not exist")
        return r.failures

    real = hashlib.sha256(gov.read_bytes()).hexdigest()
    if real != recorded_hash:
        r.bad(f"PROTOCOL_HASH in {STATUS} is {recorded_hash[:16]}… but {path} "
              f"hashes to {real[:16]}…; the record describes a file that is no "
              "longer on disk")
    else:
        r.ok(f"PROTOCOL_HASH matches the file on disk ({real[:16]}…)")

    # ---- 2  every protocol file in specs/ is accounted for ----
    say("")
    say("protocol files present")
    status_text = (root / STATUS).read_text(encoding="utf-8")
    present = sorted(p.name for p in (root / "specs").glob(
        "implementation-review-protocol-v*.md"))
    undeclared = [n for n in present if n != gov.name and n not in status_text]
    if undeclared:
        r.bad("protocol files exist in specs/ that the record document never "
              f"mentions: {', '.join(undeclared)}. An undeclared protocol file "
              "is exactly the which-copy-are-you-reading problem; record it as "
              "superseded or remove it")
    else:
        others = [n for n in present if n != gov.name]
        r.ok(f"{len(present)} protocol file(s): {gov.name} governs" +
             (f", {len(others)} recorded as superseded" if others else ""))

    # ---- 3  no operational reference names a superseded version ----
    say("")
    say("operational references")
    allowed_old = amendment_olds(root)
    if allowed_old and verbose:
        for a in sorted(allowed_old):
            print(f"        declared amendment may name {a}")

    files: list[Path] = []
    for pat in SCAN:
        files.extend(sorted((root).glob(pat)))

    stale: list[str] = []
    checked = 0
    for f in files:
        rel = f.relative_to(root).as_posix()
        if rel in EXCLUDE or f.name == gov.name or PROTO_REF.fullmatch(f.name):
            continue
        checked += 1
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for mm in PROTO_REF.finditer(line):
                found = f"{mm.group(1)}.{mm.group(2)}"
                if found == version:
                    continue
                if is_declared_amendment_line(rel, line, allowed_old):
                    continue
                stale.append(f"{rel}:{i} names v{found}, governing is v{version}\n"
                             f"        {line.strip()[:90]}")
    if stale:
        r.bad("references to a superseded protocol version:\n      " +
              "\n      ".join(stale))
    else:
        r.ok(f"{checked} operational file(s) scanned, every protocol reference "
             f"names v{version}")

    for rel, why in EXCLUDE.items():
        say(f"        not scanned: {rel}")
        say(f"                     {why}")

    return r.failures


# ------------------------------------------------------------------ controls

def controls() -> list[str]:
    """Each check demonstrated failing on a tree built to break it.

    A check that cannot come back false is the defect this repository has found
    more times than any other, so none of the three above is claimed without a
    fixture that makes it fail.
    """
    out: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="pin-"))

    # Fixture filenames are assembled rather than written out, so this file
    # contains no superseded-version literal and needs no exclusion of its own.
    # Excusing the checker from its own rule is the whitelist pattern the
    # docstring above refuses; building the name in two pieces costs nothing.
    stem = "implementation-review-protocol-v"

    def proto(v: str) -> str:
        return f"{stem}{v}.md"

    def fresh(name: str) -> Path:
        d = tmp / name
        (d / "specs" / "prompts").mkdir(parents=True)
        (d / "scripts").mkdir(parents=True)
        for f in ("verify_amendment.py",):
            shutil.copy2(REPO / "scripts" / f, d / "scripts" / f)
        for f in REPO.glob("specs/implementation-review-protocol-v*.md"):
            shutil.copy2(f, d / "specs" / f.name)
        shutil.copy2(REPO / STATUS, d / STATUS)
        return d

    def expect_fail(label: str, needle: str, d: Path) -> None:
        fails = check(d, verbose=False)
        if not fails:
            out.append(f"control '{label}': expected a failure, got none")
            return
        blob = "\n".join(fails).lower()
        if needle.lower() not in blob:
            out.append(f"control '{label}': failed for the wrong reason\n"
                       f"  wanted {needle!r}\n  got {blob[:200]}")
            return
        print(f"  [ok] caught: {label}")

    # the real tree must pass, or the controls below prove nothing
    d = fresh("clean")
    if check(d, verbose=False):
        out.append("control 'clean copy': an unmodified copy of the repo "
                   "already fails, so no control below is meaningful")
        return out
    print("  [ok] an unmodified copy passes")

    # a validator left pinned to the superseded version — the original defect,
    # and written the way it actually appeared: as a path constant, which is why
    # the first version of the exception rule let it through
    d = fresh("stale-pin")
    (d / "scripts" / "some_validator.py").write_text(
        f'PROTOCOL = "specs/{proto("1.0")}"\n', encoding="utf-8")
    expect_fail("a validator pinned to a superseded version",
                "superseded protocol version", d)

    # a prompt naming the wrong protocol
    d = fresh("stale-prompt")
    (d / "specs" / "prompts" / "06-example.md").write_text(
        f"Read specs/{proto('1.0')} before reviewing.\n", encoding="utf-8")
    expect_fail("a prompt naming a superseded version",
                "superseded protocol version", d)

    # a stale reference in a nested directory, which the first version of the
    # scan could not see at all
    d = fresh("stale-nested")
    nested = d / "specs" / "gap" / "probe"
    nested.mkdir(parents=True)
    (nested / "SOME_PROBE.md").write_text(
        f"Classified under specs/{proto('1.0')} §38.15.\n", encoding="utf-8")
    expect_fail("a stale reference nested below specs/",
                "superseded protocol version", d)

    # the exception must survive being narrowed: the real declaration still
    # passes, so the fix above did not simply delete the exception
    d = fresh("declaration-still-allowed")
    if check(d, verbose=False):
        out.append("control 'the amendment declaration still passes': "
                   "narrowing the exception broke the legitimate case it exists "
                   "for, which would make verify_amendment.py unmaintainable")
    else:
        print("  [ok] the declared amendment's own old-side line still passes")

    # the record bumped, the code not repinned
    d = fresh("record-ahead")
    s = (d / STATUS).read_text(encoding="utf-8")
    (d / STATUS).write_text(s.replace("v1.1", "v1.2"), encoding="utf-8")
    expect_fail("record bumped to a version nothing else uses",
                "does not exist", d)

    # the record's hash no longer describes the file
    d = fresh("hash-drift")
    s = (d / STATUS).read_text(encoding="utf-8")
    (d / STATUS).write_text(
        re.sub(r"(PROTOCOL_HASH\s+)[0-9a-f]{64}", r"\g<1>" + "0" * 64, s),
        encoding="utf-8")
    expect_fail("PROTOCOL_HASH no longer matches the file",
                "no longer on disk", d)

    # an undeclared protocol file appears in specs/
    d = fresh("undeclared")
    shutil.copy2(d / "specs" / proto("1.1"), d / "specs" / proto("2.0"))
    expect_fail("an undeclared protocol file in specs/",
                "never mentions", d)

    # the record contradicting itself
    d = fresh("self-contradiction")
    s = (d / STATUS).read_text(encoding="utf-8")
    (d / STATUS).write_text(s.replace("VERSION         v1.1",
                                      "VERSION         v1.3"), encoding="utf-8")
    expect_fail("the record document contradicting itself",
                "contradicts itself", d)

    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main() -> int:
    print("=" * 70)
    print("PROTOCOL PIN")
    print("=" * 70)
    print()
    failures = check(REPO)

    print()
    print("negative controls")
    failures += controls()

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("every operational reference names the governing protocol")
    return 0


if __name__ == "__main__":
    sys.exit(main())
