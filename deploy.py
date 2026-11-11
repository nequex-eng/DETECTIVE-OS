"""Build and deploy detective-os to Cloudflare Pages via wrangler.

Prefer a standard CLOUDFLARE_API_TOKEN environment variable (for example a
GitHub Actions secret). In the Muse runtime only, fall back to its one-shot
dynamic credential provider. Never print or persist a credential.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_ACCOUNT_ID = "3c76b79d615b6bc886fe564307682767"


def resolve_cloudflare_token(env=None, credential_loader=None):
    env = os.environ if env is None else env
    token = str(env.get("CLOUDFLARE_API_TOKEN", "")).strip()
    if token:
        return token
    if credential_loader is None:
        try:
            sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
            from dynamic_credentials import dynamic_credential_entry
            credential_loader = dynamic_credential_entry
        except ImportError:
            return ""
    try:
        entry = credential_loader("custom.cloudflare", "access_token")
    except Exception:
        return ""
    surrogate = str(entry.get("surrogate", "")).strip()
    return surrogate if surrogate.startswith("hsurr:") else ""


def run_step(command, label):
    print("build:", label)
    proc = subprocess.run(command, cwd=ROOT)
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

    token = resolve_cloudflare_token()
    if not token:
        print("deploy: CLOUDFLARE_API_TOKEN unavailable; configure the GitHub secret or run in the authorized Muse runtime")
        return 1
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = str(env.get("CLOUDFLARE_ACCOUNT_ID", DEFAULT_ACCOUNT_ID))
    cmd = ["npx", "-y", "wrangler@4", "pages", "deploy", "public",
           "--project-name=detective-os", "--commit-dirty=true"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    print("deploy: wrangler exit code=" + str(proc.returncode))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
