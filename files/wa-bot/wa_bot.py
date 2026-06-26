"""
Minimal WhatsApp auto-responder.

Flow:  Whapi webhook  ->  LLM (draft reply + importance score)  ->  reply, or alert you.

Run locally:
    pip install fastapi uvicorn httpx
    WHAPI_TOKEN=... FEATHERLESS_API_KEY=... MY_NUMBER=4915... WEBHOOK_SECRET=... DRY_RUN=true \
        uvicorn wa_bot:app --host 0.0.0.0 --port 8000

Keep DRY_RUN=true until you've watched the logs for a few days. It logs what it WOULD
send instead of sending, so you can judge the voice + the flagging before it goes live.
"""

import os
import json
import logging

import httpx
from fastapi import FastAPI, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("wa-bot")

WHAPI_TOKEN = os.environ["WHAPI_TOKEN"]
FEATHERLESS_API_KEY = os.environ["FEATHERLESS_API_KEY"]
MY_NUMBER = os.environ["MY_NUMBER"]          # where flags/alerts go, e.g. "4915123456789"
WHAPI_BASE = "https://gate.whapi.cloud"
FEATHERLESS_BASE = "https://api.featherless.ai/v1"
MODEL = "Qwen/Qwen2.5-72B-Instruct"
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# Optional: only auto-handle these chat ids. Empty = everyone who messages you.
ALLOWLIST = set(filter(None, os.environ.get("ALLOWLIST", "").split(",")))

# YOUR VOICE. Paste 10-20 real (them -> you) exchanges. This is the single biggest
# lever on quality — more real examples beats any prompt cleverness.
STYLE_EXAMPLES = """
Them: yo you coming friday
You: yeah for sure what time we starting
Them: can you send me that doc
You: on it gimme 10
Them: how was the run
You: brutal. legs are gone lol
"""

SYSTEM = f"""You reply to WhatsApp messages AS the user, in their exact voice.
Match tone, length, punctuation, capitalisation and slang from the examples below.
Default to SHORT.

Hard rule: never invent facts about the user's plans, schedule, location, money, or
commitments. If a good reply would require info you don't have, set "needs_user": true
and keep "reply" short and non-committal (you'll hand it to the user instead).

Also decide if this message needs the user's PERSONAL attention: anything time-sensitive,
emotionally significant, a real decision, money, conflict, or where a generic reply could
do damage. When unsure, flag it — a false flag is cheap, a missed important message is not.

The user's voice:
{STYLE_EXAMPLES}

Respond with JSON ONLY, no prose, no code fences:
{{"important": bool, "needs_user": bool, "reason": "few words", "reply": "message to send"}}"""

app = FastAPI()

log.info("startup: DRY_RUN=%s MODEL=%s MY_NUMBER=%s ALLOWLIST=%s",
         DRY_RUN, MODEL, MY_NUMBER, ALLOWLIST or "none")


async def llm(message_text: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{FEATHERLESS_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 400,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message_text},
                ],
            },
        )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def send_whatsapp(to: str, body: str):
    if DRY_RUN:
        log.info("[DRY_RUN] would send -> %s: %s", to, body)
        return
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{WHAPI_BASE}/messages/text",
            headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
            json={"to": to, "body": body},
        )
    r.raise_for_status()


@app.post("/webhook")
async def webhook(req: Request):
    log.info("webhook hit")

    payload = await req.json()
    log.info("RAW payload: %s", json.dumps(payload)[:3000])

    messages = payload.get("messages", [])
    log.info("messages in payload: %d", len(messages))

    actions = []

    for msg in messages:
        if msg.get("from_me"):
            log.info("skipping own outgoing message")
            continue

        sender = msg.get("from") or msg.get("chat_id")
        body = msg.get("text", {}).get("body") if isinstance(msg.get("text"), dict) else msg.get("body")
        log.info("message from=%s body=%r", sender, body)

        if not sender or not body:
            log.info("skipping: missing sender or body")
            continue
        if ALLOWLIST and sender not in ALLOWLIST:
            log.info("skipping: sender %s not in allowlist", sender)
            continue

        try:
            out = await llm(body)
            log.info("llm output: %s", out)
        except Exception as e:
            log.exception("llm call failed: %s", e)
            actions.append({"sender": sender, "error": str(e)})
            continue

        if out.get("important"):
            alert = f"\u26a0\ufe0f flagged ({sender}): {out.get('reason','')}\n\n> {body}"
            log.info("flagging as important \u2014 reason: %s", out.get("reason"))
            await send_whatsapp(MY_NUMBER, alert)
            actions.append({"sender": sender, "action": "flagged_important", "reason": out.get("reason"), "alert_sent_to_owner": alert, "dry_run": DRY_RUN})
            continue

        if out.get("needs_user"):
            alert = f"\u2753 needs you ({sender}): {body}\ndraft: {out.get('reply','')}"
            log.info("flagging as needs_user")
            await send_whatsapp(MY_NUMBER, alert)
            actions.append({"sender": sender, "action": "needs_user", "alert_sent_to_owner": alert, "dry_run": DRY_RUN})
            continue

        reply = out["reply"]
        log.info("auto-replying to %s: %r", sender, reply)
        await send_whatsapp(sender, reply)
        actions.append({"sender": sender, "action": "auto_reply", "reply": reply, "dry_run": DRY_RUN})

    return {"ok": True, "processed": len(actions), "actions": actions}
