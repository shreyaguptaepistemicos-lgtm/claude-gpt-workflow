#!/usr/bin/env python3
"""Controls for the credential check.

    python scripts/test_credential_check.py

Exit 0 = every control fired.

The check itself talks to GitHub, so these drive its classifier with a
responder of their own. That is the whole reason `classify` takes `get` as an
argument: a check whose failure paths have never run is an argument from
reading the source, and the register entry this file exists because of,
SELF-F28, is three instances of exactly that.

The distinctions these pin, in order of how easily they collapse:

  present is not working      a variable that exists and a credential that
                              answers are different questions
  visible is not permitted    seeing a repository and reading its Actions are
                              different permissions, and the second is the
                              one everything here is held for
  unreachable is not invalid  a network that is down must not be reported as
                              a bad token, or the fix is a new credential for
                              a problem a new credential cannot solve
  soon is not later           a token with days left is reported now, not on
                              the morning it stops working
"""

from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

import check_credential as cc  # noqa: E402

HERE = "owner/repo"


def responder(repo_code=200, actions_code=200, headers=None, raises=None):
    """A fake GitHub, counting what it was asked.

    The count is not decoration. A classifier that returned a verdict without
    calling anything would satisfy every assertion below about the verdict,
    and the fixture would be testing a constant.
    """
    calls = []

    def get(url: str):
        calls.append(url)
        if raises:
            raise urllib.error.URLError(raises)
        if "/actions/runs" in url:
            return actions_code, dict(headers or {}), {}
        return repo_code, {}, {}

    get.calls = calls
    return get


def main() -> int:
    failures: list[str] = []
    seen: set[str] = set()

    def ok(msg: str) -> None:
        print(f"  [ok] {msg}")

    def expect(cid, label, state, want_verdict, needle, get, where=HERE,
               want_calls=None):
        if cid in seen:
            failures.append(f"[CRED-DUP] {cid} is used twice, so one of the "
                            f"two controls is not the one being read")
            return
        seen.add(cid)
        verdict, headline, detail = cc.classify(state, where, get)
        body = f"{headline}\n{detail}"
        if verdict != want_verdict:
            failures.append(f"[{cid}] {label}: expected {want_verdict}, got "
                            f"{verdict} ({headline})")
            return
        if needle and needle.lower() not in body.lower():
            failures.append(f"[{cid}] {label}: {want_verdict} is right and "
                            f"the reason is not. Expected {needle!r} in:\n"
                            f"      {body}")
            return
        if want_calls is not None and len(get.calls) != want_calls:
            failures.append(f"[{cid}] {label}: expected {want_calls} call(s) "
                            f"to GitHub, made {len(get.calls)}. A verdict "
                            f"reached without asking is a constant")
            return
        ok(f"{label}: {want_verdict}")

    print("credential check controls")

    # ---- the value itself, before anything is asked of GitHub ----
    expect("CRED-ABSENT", "no GITHUB_TOKEN line at all",
           "absent", cc.FAIL, "no GITHUB_TOKEN", responder(), want_calls=0)

    # SELF-F28 verbatim. The line was there, the value was not, and the two
    # checks performed in those eight days both asked about the line.
    expect("CRED-EMPTY", "the line is present and the value is empty",
           "empty", cc.FAIL, "present and empty", responder(), want_calls=0)

    # ---- what it is being asked about ----
    expect("CRED-NOWHERE", "no origin remote, so there is nothing to ask about",
           "present", cc.UNKNOWN, "not established", responder(), where="",
           want_calls=0)

    # ---- GitHub's answers about the repository ----
    expect("CRED-401", "a token GitHub rejects",
           "present", cc.FAIL, "rejected", responder(repo_code=401))

    expect("CRED-403", "a token forbidden from the repository",
           "present", cc.FAIL, "forbidden", responder(repo_code=403))

    # 404 must name the transfer case. It is the reading a person needs on
    # the one day it happens, and GitHub's own answer does not distinguish
    # "no such repository" from "not yours to know about". SELF-F30.
    expect("CRED-404", "a token that cannot see the repository",
           "present", cc.FAIL, "transferred", responder(repo_code=404))

    # ---- visible is not permitted, which is the case that started this ----
    #
    # The token can see the repository and cannot read its Actions. Every
    # check performed before 23 October would have passed on this, because
    # each of them asked a question this state answers correctly.
    expect("CRED-ACTIONS-404", "it can see the repository but not its Actions",
           "present", cc.FAIL, "not its Actions",
           responder(actions_code=404), want_calls=2)

    expect("CRED-ACTIONS-403", "Actions forbidden rather than invisible",
           "present", cc.FAIL, "not its Actions",
           responder(actions_code=403), want_calls=2)

    # ---- unreachable is not invalid ----
    #
    # Kept apart deliberately. Reporting a dropped connection as a bad
    # credential sends somebody to make a new token, which cannot fix it, and
    # the real cause goes unlooked at.
    expect("CRED-OFFLINE", "GitHub unreachable is not a failed credential",
           "present", cc.UNKNOWN, "could not be reached",
           responder(raises="connection refused"))

    expect("CRED-5XX", "a server error is not a verdict about the token",
           "present", cc.UNKNOWN, "not a verdict", responder(repo_code=500))

    # ---- expiry ----
    expect("CRED-EXPIRY-SOON", "a token with days left is reported now",
           "present", cc.FAIL, "expires in",
           responder(headers={"github-authentication-token-expiration":
                              _in_days(3)}))

    expect("CRED-EXPIRY-PAST", "a token GitHub calls expired",
           "present", cc.FAIL, "already expired",
           responder(headers={"github-authentication-token-expiration":
                              _in_days(-2)}))

    expect("CRED-OK-FAR", "a healthy token with plenty of life",
           "present", cc.PASS, "can read Actions",
           responder(headers={"github-authentication-token-expiration":
                              _in_days(60)}), want_calls=2)

    # And the positive with no expiry header at all, because a classifier
    # that refused whenever it could not read an expiry would pass every
    # refusal above while never accepting anything.
    expect("CRED-OK-NOHEADER", "a healthy token whose expiry GitHub omits",
           "present", cc.PASS, "can read Actions", responder(), want_calls=2)

    # ---- the header parser, which the two expiry controls depend on ----
    print("\n  the expiry header")
    for label, raw, want in (
            ("GitHub's own format", _in_days(10), True),
            ("ISO with a Z", _iso_z(10), True),
            ("a bare date", _date(10), True),
            ("a format nobody here knows", "next Tuesday", False),
            ("no header at all", None, False)):
        h = {} if raw is None else {
            "github-authentication-token-expiration": raw}
        got = cc.expiry_days(h)
        if (got is not None) != want:
            failures.append(f"[CRED-HEADER] {label}: expected "
                            f"{'a number' if want else 'None'}, got {got!r}")
        else:
            ok(f"{label}: {'read' if want else 'not read, and not guessed'}")

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        print(f"\n{len(failures)} failure(s)")
        return 1
    print(f"all {len(seen)} classifier control(s) fired, and the header "
          f"parser refuses what it cannot read")
    return 0


def _in_days(n: int) -> str:
    from datetime import datetime, timedelta, timezone
    when = datetime.now(timezone.utc) + timedelta(days=n, hours=1)
    return when.strftime("%Y-%m-%d %H:%M:%S %z")


def _iso_z(n: int) -> str:
    from datetime import datetime, timedelta, timezone
    when = datetime.now(timezone.utc) + timedelta(days=n, hours=1)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _date(n: int) -> str:
    from datetime import datetime, timedelta, timezone
    when = datetime.now(timezone.utc) + timedelta(days=n, hours=1)
    return when.strftime("%Y-%m-%d")


if __name__ == "__main__":
    sys.exit(main())
