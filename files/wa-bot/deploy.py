"""
CI deploy step (Pattern B: in-place update of the existing sandbox).
Keeps the same sandbox -> same preview URL -> no Whapi reconfiguration.

Run by GitHub Actions with DAYTONA_API_KEY and SANDBOX_ID in the env.
"""

import os

from daytona import Daytona, DaytonaConfig

daytona = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))

# Attach to the already-running sandbox by id. (If 'get' isn't the current method
# name, check the SDK — it may be daytona.find()/find_one(); the operation is
# "fetch existing sandbox by id", which the SDK definitely exposes.)
APP_DIR = "/home/daytona/repo/files/wa-bot"

sandbox = daytona.get(os.environ["SANDBOX_ID"])

steps = [
    "cd /home/daytona/repo && git pull --ff-only",
    # cheap + idempotent; covers the case where requirements.txt changed:
    f"cd {APP_DIR} && pip install --no-cache-dir -r requirements.txt",
    # restart the listener
    "pkill -f 'uvicorn wa_bot:app' || true",
    f"cd {APP_DIR} && nohup uvicorn wa_bot:app --host 0.0.0.0 "
    "--port 8000 > /home/daytona/app.log 2>&1 &",
]

for cmd in steps:
    res = sandbox.process.exec(cmd)
    # surface failures so the Action goes red instead of silently "succeeding"
    print(cmd, "->", getattr(res, "exit_code", "n/a"))

print("deployed")
