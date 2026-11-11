#!/usr/bin/env python3
"""Runner helpers for DETECTIVE OS auto-run jobs (KV-backed).

The API (Pages Functions) only creates jobs and serves status. The
runner (agent, woken by a cron) drives the pipeline and writes stage
updates back to KV through this script.

Usage:
  python3 scripts/job.py poll              # list queued jobs
  python3 scripts/job.py get <job_id>      # print one job as JSON
  python3 scripts/job.py update <job_id> --status collecting --stage collecting \
      --note "正在搜索来源" --event "开始收集：12条查询"
  python3 scripts/job.py update <job_id> --status done --stage done \
      --note "草稿报告已生成" --result reports/DRAFT-xxx-report.json
  python3 scripts/job.py update <job_id> --status failed --stage failed \
      --error "原因"
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

API = "https://detective-os.pages.dev/api/jobs"
ROOT = Path(__file__).resolve().parent.parent


def api_get(job_id=None, retries=5):
    """GET a job (or the list) with retries.

    KV reads are eventually consistent across colos: a just-created
    job can 404 from one colo while visible from another. Retry with
    backoff before concluding the job does not exist.
    A random cache-buster is appended: the sandbox egress caches
    repeated GETs of the same URL, which once masqueraded as KV
    staleness (see AGENTS.md 2026-11-11).
    """
    import random
    import time
    cb = f"cb={random.randint(100000, 999999)}"
    url = API + (f"?id={job_id}&{cb}" if job_id else f"?{cb}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "detective-os-runner/1.0"})
    last = {"error": "no response"}
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                last = json.loads(exc.read().decode("utf-8"))
            except Exception:
                last = {"error": f"HTTP {exc.code}"}
            if exc.code != 404:
                break
        except Exception as exc:  # noqa: BLE001 - network flakes
            last = {"error": str(exc)}
        if attempt < retries - 1:
            time.sleep(5)
    return last


def kv_put(key, value: dict):
    """Write a job doc to KV via the Cloudflare REST API directly.

    Do NOT use `wrangler kv key put` for this: verified 2026-11-11
    that the wrangler CLI's KV writes do not land in the namespace it
    prints (CLI PUT invisible to REST GET and vice versa), while REST
    PUT -> REST GET and REST PUT -> Function GET both round-trip
    immediately. Pages deploys via wrangler still work; only its KV
    commands are untrustworthy here.
    """
    import urllib.error
    sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
    from dynamic_credentials import dynamic_credential_entry
    tok = str(dynamic_credential_entry(
        "custom.cloudflare", "access_token").get("surrogate", "")).strip()
    if not tok.startswith("hsurr:"):
        raise RuntimeError("cloudflare surrogate unavailable")
    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"3c76b79d615b6bc886fe564307682767/storage/kv/namespaces/"
           f"ae900386f76f465896f5e307baf12917/values/{key}")
    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="PUT",
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"kv REST put failed: HTTP {exc.code} "
            f"{exc.read().decode('utf-8', 'replace')[:300]}")
    if not data.get("success"):
        raise RuntimeError(f"kv REST put failed: {json.dumps(data)[:300]}")
    return "ok"


def cmd_poll(_args):
    data = api_get()
    queued = [j for j in data.get("jobs", []) if j["status"] == "queued"]
    print(json.dumps({"queued": queued}, ensure_ascii=False, indent=2))
    return 0 if queued else 0


def cmd_get(args):
    print(json.dumps(api_get(args.job_id), ensure_ascii=False, indent=2))
    return 0


def cmd_update(args):
    job = api_get(args.job_id)
    # NOTE: the job doc itself carries an "error" key (null when fine,
    # a failure message when failed), so "missing" is ONLY the exact
    # not-found marker api_get returns on 404 — a failed job's error
    # string must NOT be mistaken for "no such job".
    if job.get("error") == "没有这个任务":
        print(f"no such job: {args.job_id}")
        return 1
    # Read-your-writes: KV reads lag writes across colos. A blind
    # read-modify-write can resurrect a stale status (e.g. write
    # "extracting" over a doc whose read still said "queued"). When
    # --expect-status is given, wait until the read shows that status
    # before applying this update.
    if args.expect_status:
        import time
        deadline = time.time() + 30
        while job.get("status") != args.expect_status and time.time() < deadline:
            time.sleep(5)
            job = api_get(args.job_id)
            if job.get("error") == "没有这个任务":
                print(f"no such job: {args.job_id}")
                return 1
        if job.get("status") != args.expect_status:
            print(f"stale read: status is {job.get('status')}, "
                  f"expected {args.expect_status}; refusing to overwrite")
            return 1
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    if args.status:
        job["status"] = args.status
        if args.status != "failed":
            job["error"] = None  # a retry clears the old failure message
    if args.stage:
        job["stage"] = args.stage
    if args.note is not None:
        job["stage_note"] = args.note
    if args.event:
        job.setdefault("events", []).append(
            {"t": now, "stage": job["stage"], "message": args.event})
    if args.error is not None:
        job["error"] = args.error
    if args.result:
        job["result"] = json.loads(Path(args.result).read_text(encoding="utf-8"))
    job["updated_at"] = now
    kv_put(f"job:{args.job_id}", job)
    print(f"updated {args.job_id}: {job['status']}/{job['stage']}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="job.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("poll")
    p_get = sub.add_parser("get")
    p_get.add_argument("job_id")
    p_up = sub.add_parser("update")
    p_up.add_argument("job_id")
    p_up.add_argument("--status")
    p_up.add_argument("--stage")
    p_up.add_argument("--note")
    p_up.add_argument("--event")
    p_up.add_argument("--result")
    p_up.add_argument("--error")
    p_up.add_argument("--expect-status")
    args = ap.parse_args()
    if args.cmd == "poll":
        return cmd_poll(args)
    if args.cmd == "get":
        return cmd_get(args)
    return cmd_update(args)


if __name__ == "__main__":
    raise SystemExit(main())
