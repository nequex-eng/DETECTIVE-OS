"""Build and deploy DETECTIVE OS to Cloudflare Pages production.
Use the GitHub Actions CLOUDFLARE_API_TOKEN secret in CI; Muse dynamic
credentials are a local-runtime fallback only. Never print credentials.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACCOUNT_ID = "3c76b79d615b6bc886fe564307682767"


def resolve_cloudflare_token(env=None, credential_loader=None):
    """Resolve the standard CI token first, then the Muse surrogate fallback."""
    values = os.environ if env is None else env
    token = str(values.get("CLOUDFLARE_API_TOKEN", "")).strip()
    if token:
        return token
    loader = credential_loader
    if loader is None:
        try:
            sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
            from dynamic_credentials import dynamic_credential_entry
            loader = dynamic_credential_entry
        except Exception:
            return ""
    try:
        entry = loader("custom.cloudflare", "access_token")
    except Exception:
        return ""
    surrogate = str(entry.get("surrogate", "")).strip()
    return surrogate if surrogate.startswith("hsurr:") else ""


def resolve_token():
    return resolve_cloudflare_token(os.environ)


def run(command, label, env=None):
    print("build:", label)
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        print("failed:", label, "exit", result.returncode)
    return result.returncode


def main():
    for command, label in [
        (["npm", "install", "--no-audit", "--no-fund"], "install frontend dependencies"),
        (["npm", "run", "typecheck"], "typecheck React workbench"),
        (["npm", "run", "build"], "build React workbench"),
        ([sys.executable, "scripts/build_site.py"], "build homepage and case pages"),
    ]:
        code = run(command, label)
        if code:
            return code

    token = resolve_token()
    if not token:
        print("deploy: CLOUDFLARE_API_TOKEN unavailable")
        return 1
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = str(env.get("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID))
    command = [
        "npx", "-y", "wrangler@4", "pages", "deploy", "public",
        "--project-name=detective-os", "--branch=main", "--commit-dirty=true"
    ]
    return run(command, "deploy Cloudflare Pages production", env=env)


if __name__ == "__main__":
    raise SystemExit(main())
