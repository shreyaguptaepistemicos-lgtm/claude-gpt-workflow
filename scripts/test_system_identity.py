#!/usr/bin/env python3
"""The status record, the manifest and the code describe one system.

    python scripts/test_system_identity.py

Exit 0 = what PROTOCOL_STATUS.md declares about scope agrees with
specs/covered-components.json and with what the covered files actually
import.

Why this file exists
--------------------
Alex Zamurko, issue 6 on the public repository:

    "PROTOCOL_STATUS.md still describes stages of a programme wider than this
     repository, and nothing checks that the covered-component manifest, the
     status record and the suites' dependencies name the same system.
     Rewriting the status document to match today would make it agree and
     would not make anything check that it still agrees next week. The check
     is the work."

He was describing a real disagreement. On 22 October 2026 the status document
described a bootstrap scope of five components and stated that their
dependency closure was empty. The manifest declared eleven, four of which were
exactly the dependencies the status document said did not exist. Both
documents were accurate when written. One of them stopped being accurate and
nothing said so.

His general ruling, 19 October 2026: "Update the README and explicitly
distinguish historical protocol status, current public-repository status and
original private-repository status... Historical statements should not be
silently rewritten as current facts."

What it checks
--------------
The status document carries one machine-readable block of current claims.
Everything outside that block is prose, some of it historical, and this file
does not read it. Inside it, four claims are checked against the system:

  COVERED_MANIFEST   the manifest exists where it says
  COVERED_VERSION    equals the manifest's own version
  COVERED_COUNT      equals the number of components in it
  COVERED_SHA256     equals the manifest's digest on disk
  STATUS_AS_OF       is not older than the manifest's last scope change

The last of those is the one that answers "will it still agree next week". A
scope change raises the manifest version and dates a history entry; if the
status record is not updated with it, STATUS_AS_OF falls behind and this
fails. Comparing contents alone would not catch a change made on both sides
inconsistently, and comparing dates alone would not catch a wrong copy, so
both are here.

Then the closure, which is the "suites' dependencies" half: every
`scripts/*.py` that a covered Python file imports, transitively, must itself
be covered. A manifest that pins a file whose dependencies are unpinned is
describing a smaller system than the one that actually runs.

What it does NOT check
----------------------
Whether the prose outside the block is true. Most of that document is a
record of what was decided and when, which is history and should not be
rewritten to match today. Nothing here can tell a stale current-state claim
from a correctly preserved historical one, and pretending otherwise would be
the same defect from the other side.

It also does not check that the covered set is the right set. That is Alex
Zamurko's decision, recorded in the manifest's own history.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

STATUS_REL = "specs/PROTOCOL_STATUS.md"
BEGIN = "<!-- SYSTEM-IDENTITY-BEGIN -->"
END = "<!-- SYSTEM-IDENTITY-END -->"

IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)",
                    re.M)


def declared(text: str) -> tuple[dict, str]:
    """The key/value claims inside the marked block, or why there are none."""
    if BEGIN not in text or END not in text:
        return {}, (f"PROTOCOL_STATUS.md carries no {BEGIN} block, so it "
                    f"makes no checkable claim about scope at all")
    body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    out = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip()
    return out, ""


def imports_of(p: Path) -> set[str]:  # noqa: D401
    """Module names this file imports, by name only.

    Names rather than resolved paths, because the question is which
    `scripts/*.py` siblings it reaches, and every one of those is imported by
    bare module name after the sys.path insert these programs share.
    """
    try:
        return set(IMPORT.findall(p.read_text(encoding="utf-8")))
    except OSError:
        return set()


def closure(root: Path, roots: list[str]) -> tuple[set[str], list[str]]:
    """Every scripts/*.py reachable from the covered Python files."""
    seen: set[str] = set()
    missing: list[str] = []
    stack = [r for r in roots if r.endswith(".py")]
    while stack:
        rel = stack.pop()
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        for name in imports_of(p):
            sib = f"scripts/{name}.py"
            if (root / sib).is_file() and sib not in seen:
                stack.append(sib)
    return seen, missing


def check(root: Path, verbose: bool = True) -> list[str]:
    """Every check against `root`. Returns the list of failures."""
    failures: list[str] = []

    def ok(m: str) -> None:
        if verbose:
            print(f"  [ok] {m}")

    status = root / STATUS_REL
    if not status.is_file():
        return [f"{STATUS_REL} does not exist"]
    text = status.read_text(encoding="utf-8")

    claims, why = declared(text)
    if why:
        return [why]
    ok(f"PROTOCOL_STATUS.md declares {len(claims)} current claim(s) in one "
       f"block")

    need = ("STATUS_AS_OF", "COVERED_MANIFEST", "COVERED_VERSION",
            "COVERED_COUNT", "COVERED_SHA256")
    absent = [k for k in need if k not in claims]
    if absent:
        return [f"the block omits {', '.join(absent)}. A claim that is not "
                f"made cannot be checked,\n    and a block allowed to omit "
                f"fields is a block that can shrink until it\n    checks "
                f"nothing."]

    mpath = root / claims["COVERED_MANIFEST"]
    if not mpath.is_file():
        return [f"the declared manifest {claims['COVERED_MANIFEST']} does "
                f"not exist"]
    raw = mpath.read_bytes()
    try:
        man = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return [f"the declared manifest could not be read: {e}"]
    ok(f"the declared manifest exists and parses: "
       f"{claims['COVERED_MANIFEST']}")

    # ---- the three contents claims ----
    if str(man.get("version")) != claims["COVERED_VERSION"]:
        failures.append(f"the status record declares COVERED_VERSION "
                        f"{claims['COVERED_VERSION']} and the manifest says "
                        f"{man.get('version')}")
    else:
        ok(f"version agrees: {claims['COVERED_VERSION']}")

    comps = man.get("components") or []
    if str(len(comps)) != claims["COVERED_COUNT"]:
        failures.append(f"the status record declares COVERED_COUNT "
                        f"{claims['COVERED_COUNT']} and the manifest lists "
                        f"{len(comps)}. This is the disagreement issue 6 was "
                        f"opened for: on 22 October 2026 the document "
                        f"described five covered components and the manifest "
                        f"declared eleven.")
    else:
        ok(f"count agrees: {len(comps)} component(s)")

    digest = hashlib.sha256(raw).hexdigest()
    if digest != claims["COVERED_SHA256"]:
        failures.append(f"COVERED_SHA256 is {claims['COVERED_SHA256'][:16]}… "
                        f"and the manifest hashes to {digest[:16]}…. The "
                        f"version and count can both agree while the contents "
                        f"differ, which is why the digest is here as well.")
    else:
        ok(f"digest agrees: {digest[:16]}…")

    # ---- the date, which is what makes it still true next week ----
    hist = man.get("history") or []
    last = max((str(h.get("at", "")) for h in hist), default="")
    if last and claims["STATUS_AS_OF"] < last[:10]:
        failures.append(f"STATUS_AS_OF is {claims['STATUS_AS_OF']} and the "
                        f"manifest's last scope change is dated {last[:10]}. "
                        f"The scope moved and the record describing it did "
                        f"not.")
    else:
        ok(f"the record is not older than the last scope change "
           f"({claims['STATUS_AS_OF']} vs {last[:10] or 'none recorded'})")

    # ---- the closure: dependencies are part of the system ----
    reach, missing = closure(root, [c for c in comps])
    if missing:
        failures.append(f"covered file(s) that do not exist: "
                        f"{', '.join(sorted(missing))}")
    uncovered = sorted(reach - set(comps))
    if uncovered:
        failures.append(
            "covered files import scripts/ modules the manifest does not "
            "cover:\n      " + "\n      ".join(uncovered) +
            "\n    A manifest that pins a file whose dependencies are "
            "unpinned describes a\n    smaller system than the one that runs. "
            "Either cover them, or record why\n    the gate may ignore them.")
    else:
        ok(f"the covered set is closed under its own imports "
           f"({len(reach)} file(s) reachable, all covered)")

    return failures


# ------------------------------------------------------------------ controls

def controls() -> list[str]:
    """Each check shown failing on a tree built to break it.

    The suite was written and passed on its first run, which proves nothing
    on its own: a check that cannot come back false passes identically. Each
    fixture below changes exactly one thing.
    """
    out: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="sysid-"))

    def fresh(name: str) -> Path:
        d = tmp / name
        (d / "specs").mkdir(parents=True)
        (d / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / STATUS_REL, d / STATUS_REL)
        shutil.copy2(REPO / "specs/covered-components.json",
                     d / "specs/covered-components.json")
        man = json.loads((REPO / "specs/covered-components.json")
                         .read_text(encoding="utf-8"))
        for rel in man["components"]:
            if rel.endswith(".py"):
                shutil.copy2(REPO / rel, d / rel)
            elif not (d / rel).exists():
                (d / rel).write_text("placeholder\n", encoding="utf-8")
        return d

    def rewrite(d: Path, old: str, new: str) -> None:
        p = d / STATUS_REL
        p.write_text(p.read_text(encoding="utf-8").replace(old, new, 1),
                     encoding="utf-8")

    # Alex Zamurko, 16 October 2026: "use a stable, identifiable failure
    # signal from its named test, preferably a specific test or assertion
    # identifier rather than fragile prose."
    #
    # SELF-F15b applied that to test_run_review.py on 21 October and this file
    # was written on 22 October matching on prose anyway. Both of its
    # mutations came back WRONG CONTROL in the sweep, and he found it rather
    # than I did. The reason is worth stating because it is not obvious: a
    # mutation here disables a check, so the control does not fail with the
    # check's own message, it fails with "expected a failure, got none". The
    # words of the original failure never appear in the red output, so a
    # mutation matching on them can never be caught by the control it names.
    #
    # The identifier is in every line this emits, so it appears whichever way
    # the control fails.
    seen: dict[str, str] = {}

    def expect_fail(cid: str, label: str, needle: str, d: Path) -> None:
        if cid in seen:
            out.append(f"control id {cid} is used twice: {seen[cid]!r} and "
                       f"{label!r}. A signal naming two controls names "
                       f"neither.")
            return
        seen[cid] = label
        fails = check(d, verbose=False)
        if not fails:
            out.append(f"[{cid}] control {label!r}: expected a failure, got "
                       f"none")
            return
        blob = "\n".join(fails).lower()
        if needle.lower() not in blob:
            out.append(f"[{cid}] control {label!r}: failed for the wrong "
                       f"reason\n  wanted {needle!r}\n  got {blob[:200]}")
            return
        print(f"  [ok] [{cid}] caught: {label}")

    d = fresh("clean")
    if check(d, verbose=False):
        out.append("control 'clean copy': a tree built from the real record "
                   "already fails, so no control below means anything")
        return out
    print("  [ok] a tree built from the real record passes")

    d = fresh("no-block")
    rewrite(d, BEGIN, "<!-- removed -->")
    expect_fail("SYSID-NO-BLOCK",
                "the declared block removed entirely", "no", d)

    d = fresh("no-digest")
    rewrite(d, "COVERED_SHA256", "WAS_COVERED_SHA256")
    expect_fail("SYSID-FIELD-MISSING",
                "a field dropped from the block", "omits", d)

    d = fresh("wrong-version")
    rewrite(d, "COVERED_VERSION     1", "COVERED_VERSION     2")
    expect_fail("SYSID-VERSION",
                "the declared version disagreeing with the manifest",
                "covered_version", d)

    d = fresh("wrong-count")
    rewrite(d, "COVERED_COUNT       11", "COVERED_COUNT       5")
    expect_fail("SYSID-COUNT",
                "the declared count disagreeing with the manifest, which is "
                "the disagreement issue 6 was opened for", "covered_count", d)

    # Version and count both right, contents changed. Only the digest sees it.
    d = fresh("silent-edit")
    m = d / "specs/covered-components.json"
    doc = json.loads(m.read_text(encoding="utf-8"))
    doc["note"] = doc.get("note", "") + " "
    m.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    expect_fail("SYSID-DIGEST",
                "the manifest edited without its version or count changing",
                "covered_sha256", d)

    d = fresh("stale-record")
    rewrite(d, "STATUS_AS_OF        2026-10-22",
            "STATUS_AS_OF        2026-09-09")
    expect_fail("SYSID-STALE",
                "the record dated before the manifest's last scope change, "
                "which is the 'still agrees next week' case",
                "scope moved", d)

    # A covered file importing a scripts/ module nobody pinned.
    d = fresh("open-closure")
    (d / "scripts" / "unpinned_helper.py").write_text(
        "VALUE = 1\n", encoding="utf-8")
    led = d / "scripts/ledger.py"
    led.write_text("import unpinned_helper  # noqa\n"
                   + led.read_text(encoding="utf-8"), encoding="utf-8")
    expect_fail("SYSID-CLOSURE",
                "a covered file importing an uncovered module",
                "unpinned_helper", d)

    return out


def main() -> int:
    print("system identity")
    failures = check(REPO)

    print("\nnegative controls")
    failures += controls()

    if failures:
        print()
        for f in failures:
            print(f"  FAIL: {f}")
        print(f"\n  {len(failures)} problem(s).")
        return 1

    print("\n  the status record, the manifest and the covered files' own "
          "imports describe\n  one system, and every way of noticing they do "
          "not has been shown working")
    print("\n  Note: this reads only the declared block. The prose around it "
          "is a record of\n  what was decided and when, and nothing here can "
          "tell a stale current claim\n  from a correctly preserved "
          "historical one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
