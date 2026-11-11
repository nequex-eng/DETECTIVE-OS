"""Build and deploy detective-os to Cloudflare Pages via wrangler.

Credential handling: fetch an hsurr surrogate at runtime via dynamic_credentials
and pass it to wrangler only through the child process environment. Never print
it, never write it to disk or logs.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import dynamic_credential_entry

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNT_ID = "3c76b79d615b6bc886fe564307682767"


def run_step(command, label):
    print("build:", label)
    proc = subprocess.run(command, cwd=PROJECT_DIR)
    if proc.returncode:
        print("build failed:", label, "exit code=" + str(proc.returncode))
        return proc.returncode
    return 0


def main():
    # Build the React/TypeScript workbench and the read-only case/report dataset.
    for command, label in [
        (["npm", "install", "--no-audit", "--no-fund"], "install frontend dependencies"),
        (["npm", "run", "typecheck"], "typecheck workbench"),
        (["npm", "run", "build"], "build workbench"),
        ([sys.executable, "scripts/build_site.py"], "build case data and reports"),
    ]:
        code = run_step(command, label)
        if code:
            return code

    entry = dynamic_credential_entry("custom.cloudflare", "access_token")
    surrogate = str(entry.get("surrogate", "")).strip()
    if not surrogate.startswith("hsurr:"):
        print("deploy: surrogate unavailable")
        return 1
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = surrogate
    env["CLOUDFLARE_ACCOUNT_ID"] = ACCOUNT_ID
    cmd = ["npx", "-y", "wrangler@4", "pages", "deploy", "public",
           "--project-name=detective-os", "--commit-dirty=true"]
    proc = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    print("deploy: wrangler exit code=" + str(proc.returncode))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
