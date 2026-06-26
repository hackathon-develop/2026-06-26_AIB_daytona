"""
ONE-TIME provisioning. Run locally once to create the long-lived sandbox.
After this, CI (deploy.py) only updates code in place — the sandbox, and therefore
the webhook URL, stay fixed.

    pip install daytona
    DAYTONA_API_KEY=...  WHAPI_TOKEN=...  ANTHROPIC_API_KEY=...  \
    MY_NUMBER=4915...    WEBHOOK_SECRET=$(openssl rand -hex 16)   \
    python provision.py

Prints SANDBOX_ID (save as a GitHub secret) and the WEBHOOK URL (paste into Whapi).

NOTE ON SDK SYMBOLS: the Daytona Python SDK renames classes/params between versions.
The *concepts* below are stable (snapshot, public, auto_stop_interval=0,
get_preview_link, git clone, process exec); if an import or kwarg name is off, check
the current Python SDK reference — don't assume these spellings are frozen.
"""

import os

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams

REPO = os.environ.get("REPO_URL", "https://github.com/hackathon-develop/2026-06-26_AIB_daytona")
APP_DIR = "/home/daytona/repo/files/wa-bot"
PORT = 8000

daytona = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))

sandbox = daytona.create(CreateSandboxFromSnapshotParams(
    snapshot="daytona-small",   # pre-built Daytona base image (custom snapshots need paid plan)
    public=True,                # webhook reachable without a per-request token...
    auto_stop_interval=0,       # ...and NEVER auto-stops (mandatory for a listener)
    domain_allow_list="gate.whapi.cloud,github.com,api.featherless.ai,pypi.org,files.pythonhosted.org",
    env_vars={
        "WHAPI_TOKEN":         os.environ.get("WHAPI_TOKEN", ""),
        "FEATHERLESS_API_KEY": os.environ.get("FEATHERLESS_API_KEY", ""),
        "MY_NUMBER":           os.environ.get("MY_NUMBER", ""),
        "WEBHOOK_SECRET":      os.environ["WEBHOOK_SECRET"],
        "DRY_RUN":             "true",
    },
))

# Clone the repo, install deps, and start the listener from the app subdirectory.
sandbox.git.clone(REPO, "/home/daytona/repo")
sandbox.process.exec(f"pip install --no-cache-dir -r {APP_DIR}/requirements.txt")
sandbox.process.exec(
    f"cd {APP_DIR} && nohup uvicorn wa_bot:app "
    f"--host 0.0.0.0 --port 8000 > /home/daytona/app.log 2>&1 &"
)
# For a more robust daemon than nohup, use Daytona "Sessions" (process.create_session)
# — see the Process Execution docs. nohup is fine for a for-fun build.

preview = sandbox.get_preview_link(PORT)
print("SANDBOX_ID :", sandbox.id)
print("WEBHOOK URL:", preview.url.rstrip("/") + "/webhook")
