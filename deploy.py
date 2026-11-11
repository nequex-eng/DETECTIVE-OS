"""Deploy detective-os to Cloudflare Pages via wrangler.
Credential handling: fetch an hsurr surrogate at runtime via
dynamic_credentials and pass it to wrangler only through the child
process environment. Never print it, never write it to disk or logs.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import dynamic_credential_entry

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNT_ID = "3c76b79d615b6bc886fe564307682767"


def main():
    build = subprocess.run([sys.executable, str(
        os.path.join(PROJECT_DIR, "scripts", "build_site.py"))],
        cwd=PROJECT_DIR)
    if build.returncode:
        print("deploy: static site build failed")
        return build.returncode
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
