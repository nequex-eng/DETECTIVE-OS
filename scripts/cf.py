#!/usr/bin/env python3
"""Cloudflare wrangler helper for detective-os.

Same credential pattern as deploy.py: fetch an hsurr surrogate at
runtime via dynamic_credentials and pass it to wrangler only through
the child process environment. Never print it, never write it to disk.

Usage:
  python3 scripts/cf.py d1 list
  python3 scripts/cf.py d1 create detective-os-jobs
  python3 scripts/cf.py d1 execute detective-os-jobs --file schema.sql
  python3 scripts/cf.py pages deploy
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import dynamic_credential_entry

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNT_ID = "3c76b79d615b6bc886fe564307682767"


def main():
    if len(sys.argv) < 2:
        print("usage: cf.py <wrangler args...>")
        return 1
    entry = dynamic_credential_entry("custom.cloudflare", "access_token")
    surrogate = str(entry.get("surrogate", "")).strip()
    if not surrogate.startswith("hsurr:"):
        print("cf: surrogate unavailable")
        return 1
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = surrogate
    env["CLOUDFLARE_ACCOUNT_ID"] = ACCOUNT_ID
    # wrangler prints a proxy warning when proxy env vars are set; the
    # sandbox needs the proxy, so keep it and ignore the warning.
    cmd = ["npx", "-y", "wrangler@4"] + sys.argv[1:]
    proc = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
