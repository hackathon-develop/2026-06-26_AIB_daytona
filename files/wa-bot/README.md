# wa-bot

Personal WhatsApp auto-responder. Drafts replies in your voice, flags important
messages for you instead of replying. Friends-only, for-fun. See `DESIGN.md` for the
reasoning and `CLAUDE.md` for the operational summary Claude Code reads.

## Layout

| File | Purpose |
|---|---|
| `wa_bot.py` | The listener + agent (the whole app) |
| `requirements.txt` | Python deps |
| `Dockerfile` | Builds the Daytona snapshot (deps only) |
| `provision.py` | One-time: create the persistent sandbox, print webhook URL + id |
| `deploy.py` | CI step: update the live sandbox in place |
| `.github/workflows/deploy.yml` | Runs `deploy.py` on push to `main` |
| `.env.example` | Required env vars |

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill it in
set -a; source .env; set +a
uvicorn wa_bot:app --host 0.0.0.0 --port 8000
# expose it: cloudflared tunnel --url http://localhost:8000
# then paste the public URL + /webhook into Whapi, and set X-Webhook-Secret there
```

## Deploy on Daytona (one-time)

```bash
daytona login
daytona snapshot create wa-bot --dockerfile ./Dockerfile --context .
python provision.py     # prints SANDBOX_ID and the webhook URL
```

Paste the webhook URL into the Whapi panel and set a custom header
`X-Webhook-Secret: <your WEBHOOK_SECRET>`.

## CI/CD

Add GitHub Actions secrets: `DAYTONA_API_KEY`, `DAYTONA_SANDBOX_ID`. Every push to
`main` then updates the live sandbox in place — the sandbox id (and webhook URL) stay
fixed, so Whapi needs no reconfiguration.

## Before going live

- Keep `DRY_RUN=true` and watch `app.log` for a few days.
- Pair Whapi to a **burner number** — it's an unofficial gateway and the number can be
  banned.
- The `/webhook` endpoint is public; the `X-Webhook-Secret` check is what protects it.
  Don't remove it.
