# DESIGN.md — decisions and rationale

This is the distilled record of the design discussion. It exists so a future session
(human or Claude Code) inherits the reasoning, not just the result.

## Goal

Auto-respond to personal WhatsApp messages in the owner's voice; flag important ones
for personal attention instead of replying. Friends-only, for-fun build.

## Starting proposal (and what was wrong with it)

The original three-step plan was: Whapi webhook → dispatch a Daytona agent to process
and reply → flag serious messages. Problems:

1. **Autonomous send was the dangerous default.** An LLM replying *as* the owner makes
   commitments, invents facts, and agrees to things, with the owner's authority. For
   anything beyond friends this also has legal weight (messages can form agreements /
   be representations). Decision: **draft-and-flag by default**; auto-send only for
   low-stakes messages, and only after review. Importance/needs-info → route to the
   owner with a draft, don't send.

2. **"Deemed serious" hid the hard part.** The importance classifier *is* the product.
   Errors are asymmetric — a missed-important is far costlier than a false flag — so it
   is calibrated to over-flag. Importance lives in the relationship/context, not the
   message body, so future work should add sender identity, thread history, and calendar
   context as features.

3. **Daytona was the wrong tool for the stated reason.** "Run permanently" argues
   *against* an ephemeral-sandbox platform, not for it. What justifies Daytona is the
   *other* reason — the agent eventually executing code/tools in isolation per message.
   These are two tiers: an always-on listener (not a Daytona job on its own) and a
   per-message worker (a genuine Daytona fit).

## Platform findings (Daytona, verified against docs)

- Persistence is supported: sandboxes have no hard session limit; set
  `auto_stop_interval=0` to keep one alive.
- **Gotcha:** preview-URL traffic does NOT reset the auto-stop idle timer, so a non-zero
  interval kills a webhook listener between messages. `0` is mandatory here.
- Inbound webhooks work via preview URLs (ports 3000–9999):
  `https://{port}-{sandboxId}.{proxyDomain}`. `public=true` removes the per-request
  token; the app then enforces its own shared secret.
- There is no git-push PaaS. "CI/CD to Daytona" = a GitHub Action that calls the
  Daytona API/SDK/CLI.
- Reference: Daytona's own **OpenClaw** guide runs a WhatsApp/Telegram assistant in a
  sandbox with `--auto-stop 0` and a phone allow-list — closest existing pattern.

## Deployment decision

Two CI shapes considered:

- **Pattern A (immutable redeploy):** build image → push to GHCR → new snapshot →
  recreate sandbox. Clean, but a recreate changes the `sandboxId`, hence the preview
  URL, hence requires re-pointing Whapi every deploy (unless fronted by a Custom Preview
  Proxy / own domain).
- **Pattern B (in-place update):** one long-lived sandbox; CI does `git pull` + restart.
  Same id → **stable webhook URL**. Chosen as the default for an always-on listener.
  A is the upgrade path once immutability matters.

## Legal/privacy posture

Friends-only collapses the legal layer: GDPR's household/personal-activity exemption
applies and confidentiality is moot. This changes **the moment** any work/client comms
flow through — at which point Whapi (an unofficial third party touching plaintext) plus
a US LLM API becomes a confidentiality and GDPR problem, and the build must stop and be
reassessed. Keep work comms out entirely.

## Rejected / not-now

- **Official WhatsApp Cloud API** — doesn't fit a personal number (template + 24h-window
  model; migrating a number removes it from the consumer app). The unofficial lane is
  effectively forced, with its ban risk.
- **Fine-tuning for voice** — unwarranted; few-shot from real messages is enough.
- **VPS/PaaS for the listener** — cheaper than always-on Daytona for a listener alone.
  Only revisit if the agent tier never grows into real per-message compute.

## Open questions / next steps

- Add thread context (last N messages) to the Anthropic call — biggest quality win.
- Route flags to a Telegram bot instead of self-WhatsApp to declutter.
- Build out the agent tier (code/tool execution in-sandbox) — the actual justification
  for being on Daytona.
- Decide on a robust daemon (Daytona Sessions) vs the current `nohup` for the server
  process.
