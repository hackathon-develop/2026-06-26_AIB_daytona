# CLAUDE.md

Context for Claude Code working in this repo. Read DESIGN.md for the full rationale
behind every decision below; this file is the operational summary.

## What this is

A personal WhatsApp auto-responder. Inbound WhatsApp messages arrive via webhook,
an LLM drafts a reply in the owner's voice and scores the message's importance, then
the bot either auto-replies (low stakes) or pings the owner instead (important / needs
info it doesn't have). Personal use, friends only — NOT a product, NOT for client or
work communications.

## Architecture (two tiers — keep them distinct)

1. **Listener** — always-on FastAPI server (`wa_bot.py`) that receives the Whapi
   webhook. Must never sleep.
2. **Agent** — the per-message logic: one Anthropic API call that returns
   `{important, needs_user, reason, reply}`. Today it only generates text. The reason
   this project is hosted on Daytona (rather than a cheap VPS) is the *future* of this
   tier: running code / tools / data work in an isolated sandbox per message. If that
   never happens, Daytona is the wrong host — see DESIGN.md.

## Hard constraints — do not violate

- **`auto_stop_interval=0` is mandatory.** Daytona's auto-stop idle timer is NOT reset
  by traffic arriving through a preview URL. Any non-zero value will let the sandbox
  shut down between webhooks and silently drop messages.
- **The webhook endpoint is public** (`public=true` so Whapi can POST without a token),
  therefore the app MUST verify `X-Webhook-Secret` against `WEBHOOK_SECRET`. Never
  remove that check.
- **Never auto-send to anyone outside the intended scope.** Default behavior is
  draft-and-flag for anything important or anything requiring facts the model lacks.
  Do not "improve" this into unconditional autonomous replying.
- **Keep `DRY_RUN=true`** as the default until the owner has reviewed logs. In DRY_RUN
  the bot logs what it would send instead of sending.
- **Whapi is an unofficial WhatsApp gateway** — it pairs as a linked device and using
  it risks a WhatsApp ban on the paired number. Assume a burner number, not the
  owner's primary line.

## Version-sensitive — verify, don't assume

The Daytona Python SDK renames classes/kwargs between versions. Symbols used here
(`CreateSandboxParams`, `daytona.get(id)`, `sandbox.git.clone`, `sandbox.process.exec`,
`get_preview_link`, `auto_stop_interval`) are written to the *concepts*, which are
stable, but exact spellings may have moved. Check the current SDK reference before
trusting an import — don't fabricate method names to make code compile.

## File map

- `wa_bot.py` — the listener + agent. The whole app.
- `Dockerfile` — builds the Daytona snapshot (deps only; app code is git-cloned at
  runtime so deploys are a `git pull`, not a rebuild).
- `provision.py` — run ONCE to create the persistent sandbox and print the stable
  webhook URL + sandbox id.
- `deploy.py` + `.github/workflows/deploy.yml` — CI: on push to `main`, update the
  live sandbox in place (stable URL, no Whapi reconfig).
- `.env.example` — required environment variables.

## Common commands

- Run locally:  `uvicorn wa_bot:app --host 0.0.0.0 --port 8000`
- Build snapshot:  `daytona snapshot create wa-bot --dockerfile ./Dockerfile --context .`
- First deploy:  `python provision.py`  (prints SANDBOX_ID + webhook URL)
- Tail logs:  `daytona sandbox exec <id> -- tail -f /home/daytona/app.log`

## Quality lever

Reply quality is dominated by `STYLE_EXAMPLES` in `wa_bot.py` — real `them -> you`
exchanges. More examples beats prompt tuning. Do not fine-tune; it isn't warranted.
The next real upgrade is feeding the last N messages of each thread into the Anthropic
call (currently it sees only the single incoming message).
