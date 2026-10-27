#!/usr/bin/env python3
"""Ask the credential whether it can still do the thing it is held for.

    python scripts/check_credential.py

Exit 0 = it answered, for this repository, with the permission it needs.
Exit 1 = it could not, and the reason is named rather than guessed at.

Why this exists
---------------
SELF-F28, 23 October 2026: the GitHub token EC-4's recorder depends on was
created with no repository access and no permissions of any kind, and nobody
found out for eight days. It was checked twice in that time by listing the
variable names in .env without their values. Both times it was reported
present, which it was.

Its residual said the obvious thing and nothing was written: a check that
asks whether a secret is PRESENT answers a different question from whether it
WORKS, and the gap between those two was eight days wide.

On 26 October the same gap cost two more rounds. The repository moved to an
organisation, a fine-grained token's access is scoped under its resource
owner, and the old token was owned by a personal account. So it could see
nothing, and GitHub reports that as 404, which reads as "no such run".

Three failures, one shape. The token was present every time.

What it asks, and why two calls rather than one
-----------------------------------------------
Being able to SEE the repository and being allowed to read its Actions are
different permissions, and the failure that started all this was the second
without the first being wrong. A token with Metadata only answers the first
call and fails the second, which is exactly the state the 15 October token
would have been in had it been given anything at all.

So this asks both, in the order a reader would want them, and it asks about
the repository the origin remote names rather than a constant, because the
constant is the thing that silently keeps working after a transfer.

What it does not establish
--------------------------
That the token is the right token, or that nobody else holds a copy. It
establishes that the credential in .env can read this repository's Actions
right now, which is the one claim everything downstream assumes and nothing
checked.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# SELF-F25. This prints an arrow and a dash the Windows code page cannot
# encode, and a run that dies mid-print reads as a run that found less.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "CANNOT_ESTABLISH"

# Days of remaining life below which this reports rather than waits. A token
# that expires on a Friday takes the evidence pipeline with it, and the first
# sign is a 401 in the middle of something else.
EXPIRY_WARN_DAYS = 14


def token_line() -> tuple[str, str]:
    """(state, value). State is one of absent, empty, present.

    .env rather than the environment, for the reason the recorder gives: an
    environment variable has to be typed somewhere, and a shell history is
    the one place a credential must not be.
    """
    f = REPO / ".env"
    if not f.is_file():
        return "absent", ""
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        if k.strip() == "GITHUB_TOKEN":
            v = v.strip().strip('"').strip("'")
            # SELF-F28 verbatim: the line was there and the value was not.
            # "Present" was what every earlier check asked about.
            return ("present", v) if v else ("empty", "")
    return "absent", ""


def origin() -> str:
    """owner/name from the origin remote, or "".

    Not a constant. A hardcoded owner goes on working after a transfer,
    because GitHub redirects the old path, so the first sign of trouble is
    evidence recorded under a name nobody uses. SELF-F30.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "remote", "get-url", "origin"],
            capture_output=True, text=True, encoding="utf-8").stdout.strip()
    except OSError:
        return ""
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?$", out)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def live_get(url: str, tok: str) -> tuple[int, dict, dict]:
    """(status, headers, payload). Network errors raise URLError."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "epistemicos-credential-check",
        "Authorization": f"Bearer {tok}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), {}


def expiry_days(headers: dict) -> int | None:
    """Days until the token expires, from GitHub's own header, or None.

    A fine-grained token's expiry comes back on every response. Reading it
    here rather than from a calendar reminder: a reminder is a thing somebody
    has to have set, and SELF-F28 is a register entry about exactly that kind
    of assumption.
    """
    raw = ""
    for k, v in headers.items():
        if k.lower() == "github-authentication-token-expiration":
            raw = str(v).strip()
            break
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            when = datetime.strptime(raw, fmt)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return (when - datetime.now(timezone.utc)).days
        except ValueError:
            continue
    return None


def classify(state: str, where: str, get) -> tuple[str, str, str]:
    """(verdict, headline, detail), given a responder.

    `get` is injected so the controls can drive every branch without a
    network or a real credential. A check whose failure paths have never run
    is an argument from reading the source, which is what this whole file is
    a consequence of.
    """
    if state == "absent":
        return (FAIL, "no GITHUB_TOKEN in .env",
                "Nothing downstream can reach GitHub. The recorder refuses "
                "rather than\n  recording without verification, so this is "
                "the thing to fix first.")
    if state == "empty":
        return (FAIL, "GITHUB_TOKEN is present and empty",
                "This is SELF-F28 exactly. A check that asks whether the "
                "variable exists\n  answers yes, and every call it is used "
                "for returns 404.")
    if not where:
        return (UNKNOWN, "the origin remote could not be read",
                "Which repository the credential should be able to see is "
                "not established,\n  so this cannot ask.")

    try:
        code, headers, _ = get(f"https://api.github.com/repos/{where}")
    except urllib.error.URLError as e:
        return (UNKNOWN, f"GitHub could not be reached: {e.reason}",
                "An unreachable service is not a failed credential.")

    if code == 401:
        return (FAIL, "the token was rejected",
                "GitHub answered 401, which means expired, revoked or "
                "mistyped. The value\n  in .env is not a credential GitHub "
                "accepts.")
    if code == 403:
        return (FAIL, "the token is forbidden from this repository",
                "GitHub answered 403.")
    if code == 404:
        return (FAIL, f"the token cannot see {where}",
                "GitHub answers 404 both for a repository that does not "
                "exist and for one\n  the credential is not allowed to "
                "know about, so this does not say which.\n\n"
                "  A fine-grained token is scoped under a resource owner. "
                "If this repository\n  was transferred, a token owned by "
                "the previous owner stops covering it and\n  this is "
                "exactly what that looks like. SELF-F30.")
    if code != 200:
        return (UNKNOWN, f"GitHub answered {code} for the repository",
                "Not a verdict about the credential.")

    # It can see the repository. Whether it may read Actions is a separate
    # permission, and the one everything here is held for.
    try:
        code2, headers2, _ = get(
            f"https://api.github.com/repos/{where}/actions/runs?per_page=1")
    except urllib.error.URLError as e:
        return (UNKNOWN, f"GitHub could not be reached: {e.reason}", "")

    if code2 in (403, 404):
        return (FAIL, "the token can see the repository but not its Actions",
                "This is the state SELF-F28 found: a credential that is "
                "present, valid and\n  unable to do the one thing it is "
                "held for. Grant Actions: Read-only.")
    if code2 != 200:
        return (UNKNOWN, f"GitHub answered {code2} for the Actions runs", "")

    days = expiry_days(headers2) or expiry_days(headers)
    if days is not None and days < 0:
        return (FAIL, "GitHub reports this token as already expired",
                "It answered anyway, which is GitHub's business. Replace it.")
    if days is not None and days <= EXPIRY_WARN_DAYS:
        return (FAIL, f"the token expires in {days} day(s)",
                "Reported as a failure rather than a note, deliberately. The "
                "day it lapses\n  the evidence pipeline stops, and the first "
                "sign would be a 401 in the\n  middle of something else.")

    when = f", {days} days of life left" if days is not None else ""
    return (PASS, f"the credential can read Actions on {where}{when}", "")


def main() -> int:
    state, tok = token_line()
    where = origin()
    verdict, headline, detail = classify(
        state, where, lambda u: live_get(u, tok))

    print("credential check")
    print(f"  [{verdict}] {headline}")
    if detail:
        print(f"  {detail}")
    if verdict == PASS:
        return 0
    print("\n  Nothing here printed the credential, and nothing here wrote "
          "it anywhere.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
