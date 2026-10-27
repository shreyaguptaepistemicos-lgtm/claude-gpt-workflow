#!/usr/bin/env python3
"""Record that a repair was exercised by a machine nobody here controls.

    python scripts/record_execution_evidence.py \
        --url  https://github.com/<owner>/<repo>/actions/runs/<id> \
        --job  "every repair goes red when removed" \
        --log  evidence/github/<id>-sweep.txt \
        --covers D02-F01 SELF-F02 SELF-F04

Writes evidence/execution-evidence.json, which EC-4 reads.

Why this exists
---------------
Alex Zamurko, 13 October 2026, on EC-4:

    "The inspected implementation still adds CANNOT_ESTABLISH for independent
     execution unconditionally. Replace this with validation of actual GitHub
     execution evidence, linked to the exact commit and reviewed finding."

And on the first attempt at it, 15 October:

    "The checker verifies the locally recorded commit SHA, log-file existence,
     log digest and declared finding IDs. It does not independently verify
     that the claimed GitHub run, job, conclusion and coverage are genuine...
     A locally authored evidence record with a matching log digest can
     therefore satisfy the mechanical check without demonstrating that GitHub
     independently executed the named repair."

He was right both times. The first version let somebody type a conclusion into
a JSON file and have EC-4 believe it. So nothing here is typed any more that
GitHub can be asked about instead.

What this now does
------------------
Fetches the run and its jobs from the GitHub API, and derives the commit, the
job's conclusion, the workflow name and the timestamps from that response
rather than from arguments. The raw responses are preserved beside the log
with their digests, so a reviewer can re-fetch the same URLs and compare bytes
rather than take this file's word for anything.

The only things still supplied by hand are which run, which job, where the log
is, which findings it is claimed to cover, and what kind of evidence it is.
Of those, the coverage claim is reconciled by EC-4 against what the preserved
log actually says, and a claim the output does not support is reported.

What it still cannot do, stated rather than implied
---------------------------------------------------
This runs on the implementing agent's machine. Somebody with write access to
the repository could write these files by hand, and no check inside the
repository can tell the difference, because under MC1_ENFORCEMENT:
CONVENTION_ONLY the same writable code performs the checks on itself. What
this removes is the easy path: a record is now either consistent with a live
GitHub response or it is not, and the URL is preserved so a reviewer can do in
thirty seconds the one thing no script here can do for them.

The token
---------
Read from .env, never from an argument or an environment variable set by hand,
so it never passes through a command line or a shell history. A fine-grained
token with Actions: Read-only on this repository is enough. Nothing in this
file prints it, and a failure message that would contain it is redacted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# SELF-F16/F20/F25. The Windows console encodes at the locale code page,
# cp1252, and this program holds characters it has no room for. Without
# this the work completes and the print raises UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "evidence" / "execution-evidence.json"
RAW = REPO / "evidence" / "github"

RUN_URL = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+)/actions/runs/(\d+)(?:/|$)")

PURPOSE = (
    "Independent execution evidence, read by EC-4. Each entry records a "
    "GitHub run whose commit, job conclusion and timestamps were fetched from "
    "the GitHub API rather than typed, with the raw API responses preserved "
    "beside the job log so a reviewer can re-fetch and compare. None of it "
    "asserts that a repair is correct or that the evidence is adequate for a "
    "blocking item. Written by scripts/record_execution_evidence.py, never by "
    "hand."
)


def fail(msg: str) -> int:
    print(f"  [REFUSED] {msg}")
    return 2


def token() -> str:
    """GITHUB_TOKEN from .env, and nowhere else.

    Not os.environ: an environment variable has to be set by typing it
    somewhere, and the one place a credential should not appear is a shell
    history. .env is gitignored and is where this repository's other key
    already lives.
    """
    f = REPO / ".env"
    if not f.is_file():
        return ""
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        if k.strip() == "GITHUB_TOKEN":
            return v.strip().strip('"').strip("'")
    return ""


def api(path: str, tok: str) -> tuple[dict | None, str]:
    """GET from the GitHub API. Returns (payload, error).

    The error string is built from the status and reason only. A URL or a
    header could carry the token into a message somebody later pastes.
    """
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "epistemicos-execution-evidence",
            "Authorization": f"Bearer {tok}",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), ""
    except urllib.error.HTTPError as e:
        hint = {
            401: "the token was rejected. It may be expired, or mistyped in "
                 ".env.",
            403: "forbidden. The token most likely lacks Actions: Read-only "
                 "on this repository.",
            404: "not found. Either the run id is wrong, or the token cannot "
                 "see this repository at all, which GitHub reports as 404 "
                 "rather than 403.",
        }.get(e.code, "")
        return None, f"GitHub returned {e.code} {e.reason}. {hint}".strip()
    except urllib.error.URLError as e:
        return None, f"could not reach GitHub: {e.reason}"
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"GitHub's reply could not be read: {e}"


def load() -> dict:
    if not EVIDENCE.is_file():
        return {"schema": "execution-evidence/2", "purpose": PURPOSE,
                "runs": []}
    try:
        d = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{EVIDENCE} is not valid JSON: {e}\n"
                 f"It is written by this script and should not be edited by "
                 f"hand. Fix or remove it.")
    d["schema"] = "execution-evidence/2"
    d["purpose"] = PURPOSE
    d.setdefault("runs", [])
    return d


def write_raw(run_id: str, name: str, payload: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f"{run_id}-{name}.json"
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    p.write_text(body, encoding="utf-8", newline="\n")
    return {
        "path": p.relative_to(REPO).as_posix(),
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="the GitHub run page")
    p.add_argument("--job", required=True,
                   help="the job name within that run, exactly as GitHub "
                        "shows it")
    p.add_argument("--log", required=True,
                   help="the preserved output, repo-relative")
    p.add_argument("--covers", nargs="+", required=True,
                   help="the finding IDs this run is claimed to exercise. "
                        "Reconciled by EC-4 against what the preserved log "
                        "actually names: a claim the output does not support "
                        "is reported rather than believed.")
    p.add_argument("--purpose", default="repair_verification",
                   choices=["repair_verification", "failure_demonstration"],
                   help="what this run is evidence OF. A deliberately red run "
                        "shows the pipeline reports failure; it is not "
                        "evidence that a repair holds, and EC-4 counts the "
                        "two separately.")
    p.add_argument("--note", default="",
                   help="anything a reader needs that the fields cannot say")
    a = p.parse_args()

    m = RUN_URL.match(a.url.strip())
    if not m:
        return fail("--url is not a GitHub Actions run page.\n"
                    "  Expected https://github.com/<owner>/<repo>/actions/"
                    f"runs/<id>\n  Got      {a.url}")
    owner, repo, run_id = m.group(1), m.group(2), m.group(3)

    log = (REPO / a.log).resolve()
    if not log.is_file():
        return fail(f"the preserved log is not there: {a.log}\n"
                    "  A run page is not forever. Download the job log or the "
                    "sweep artifact and\n  commit it beside the repository "
                    "before recording the run.")
    if log.stat().st_size == 0:
        return fail(f"the preserved log is empty: {a.log}\n"
                    "  An empty file is not a record of anything.")
    try:
        log.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return fail(f"the preserved log is not valid UTF-8: {e}\n"
                    "  SELF-F11: a reader that cannot decode its evidence has "
                    "not found an empty\n  result, it has found one it cannot "
                    "read. Save it as UTF-8.")

    tok = token()

    # Ask the credential whether it can do this before doing it. SELF-F28's
    # residual, written 26 October.
    #
    # Until now the first sign of a credential problem was whatever GitHub
    # said about the specific call that failed, and GitHub says 404 for a
    # repository that does not exist, for one the token may not know about,
    # and for a run id that is wrong. Three causes, one answer, and the hint
    # below used to list all three and leave the reader to guess. It cost
    # eight days in October and two rounds on the day the repository moved.
    #
    # check_credential asks the two questions that separate them: can this
    # token see the repository the origin remote names, and may it read that
    # repository's Actions. A failure here names which.
    import check_credential as _cred  # local import: this is the only caller
    _state = "present" if tok else _cred.token_line()[0]
    _verdict, _headline, _detail = _cred.classify(
        _state, _cred.origin(), lambda u: _cred.live_get(u, tok))
    if _verdict == _cred.FAIL:
        return fail(f"{_headline}\n  {_detail}\n\n"
                    "  Recording without verification is not offered. That "
                    "is the defect Alex\n  Zamurko named on 15 October.")
    if _verdict == _cred.UNKNOWN:
        print(f"  [note] the credential could not be checked first: "
              f"{_headline}")
        print("         Continuing, because that is not a statement that it "
              "is broken.")

    run, err = api(f"/repos/{owner}/{repo}/actions/runs/{run_id}", tok)
    if err:
        return fail(f"the run could not be fetched.\n  {err}")
    jobs, err = api(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", tok)
    if err:
        return fail(f"the run's jobs could not be fetched.\n  {err}")

    names = [j.get("name", "") for j in jobs.get("jobs", [])]
    job = next((j for j in jobs.get("jobs", []) if j.get("name") == a.job),
               None)
    if job is None:
        return fail(f"run {run_id} has no job named {a.job!r}.\n"
                    f"  It has: " + ", ".join(repr(n) for n in names))

    if run.get("status") != "completed":
        return fail(f"run {run_id} is {run.get('status')!r}, not completed. "
                    f"A run still in progress\n  is not evidence of anything "
                    f"yet.")
    if job.get("conclusion") == "skipped":
        return fail(f"the job {a.job!r} was skipped in run {run_id}. A job "
                    f"that did not run\n  establishes nothing, and recording "
                    f"it would make the run page look like\n  evidence it is "
                    f"not.")

    sha = str(run.get("head_sha", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return fail(f"GitHub did not report a commit for run {run_id}")
    have = subprocess.run(["git", "-C", str(REPO), "cat-file", "-t", sha],
                          capture_output=True, text=True, encoding="utf-8")
    if have.returncode != 0 or have.stdout.strip() != "commit":
        return fail(f"GitHub says run {run_id} examined {sha[:12]}, and this "
                    f"repository has no\n  such commit. Fetch it, or the "
                    f"evidence is bound to something nobody here\n  can look "
                    f"at.")

    raw_run = write_raw(run_id, "run", run)
    raw_jobs = write_raw(run_id, "jobs", jobs)

    entry = {
        "run_id": run_id,
        "url": run.get("html_url") or a.url.strip(),
        "repository": f"{owner}/{repo}",
        "workflow": run.get("name") or "",
        "job": a.job,
        "commit": sha,
        "conclusion": job.get("conclusion"),
        "run_conclusion": run.get("conclusion"),
        "run_attempt": run.get("run_attempt"),
        "job_started_at": job.get("started_at"),
        "job_completed_at": job.get("completed_at"),
        "log": a.log.replace("\\", "/"),
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "log_bytes": log.stat().st_size,
        "covers": sorted(set(a.covers)),
        "purpose": a.purpose,
        "api_run": raw_run,
        "api_jobs": raw_jobs,
        "recorded_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
    }
    if a.note:
        entry["note"] = a.note

    d = load()
    d["runs"] = [r for r in d["runs"]
                 if not (r.get("run_id") == run_id and r.get("job") == a.job)]
    d["runs"].append(entry)
    d["runs"].sort(key=lambda r: (r.get("run_id", ""), r.get("job", "")))

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8",
                        newline="\n")

    print(f"recorded run {run_id}, job {a.job!r}")
    print(f"  workflow    {entry['workflow']}")
    print(f"  commit      {sha}      (from GitHub, not from you)")
    print(f"  conclusion  {entry['conclusion']}   (job)   "
          f"{entry['run_conclusion']}   (run)")
    print(f"  log         {entry['log']}  {entry['log_bytes']} bytes  "
          f"{entry['log_sha256'][:16]}…")
    print(f"  api         {raw_run['path']}, {raw_jobs['path']}")
    print(f"  covers      {', '.join(entry['covers'])}   "
          f"(claimed; EC-4 reconciles this against the log)")
    print(f"  purpose     {a.purpose}")
    print(f"\n  {EVIDENCE.relative_to(REPO).as_posix()} now holds "
          f"{len(d['runs'])} run(s).")
    print("\n  The commit, conclusion and timestamps came from GitHub's API "
          "and the raw\n  replies are preserved. Whether any of it is "
          "adequate for a blocking item is\n  not recorded here, because it "
          "is not this script's to decide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
