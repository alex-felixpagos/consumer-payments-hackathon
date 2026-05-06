# AGENTS.md — Team Bachata, Felix Pago Hackathon

Project context for AI coding agents (Cursor, Claude Code, Codex, etc.) working on this repo. **Read this first** before touching code. For the full human setup walkthrough see `README.md` and the always-on Cursor rule `.cursor/rules/kapso-hackathon-setup.mdc`.

---

## TL;DR

- **What we're building:** A WhatsApp + AI conversational product on top of [Kapso](https://docs.kapso.ai/docs/introduction) (Meta Tech Provider) + FastAPI. Pick an idea inside the constraints in `KICKOFF.md`.
- **Stack:** Python **3.12** (pinned in `.python-version`), FastAPI, Uvicorn, httpx, pydantic-settings, pytest. No DB.
- **Deadline:** Wed May 6, **3 PM code freeze**, demos 3:30 PM, awards 4:30 PM (see `KICKOFF.md`).
- **Where we coordinate:** Bachata team Slack group DM → [felix-pago.slack.com/archives/C0B1XAGP0RK](https://felix-pago.slack.com/archives/C0B1XAGP0RK). Cross-team hackathon channel is `#cp-hackathon`.
- **Team branch:** `team-bachata`. Members:
  - Sam Cohen — `@sam`
  - Luccas Monteiro — `@luccasmonteiro`
  - Diego Kamiha — `@diegokamiha`
  - Axel Diaz — `@axeldiaz`
  - Hernan Aracena — `@hernanaracena`
  - **Never push directly to `main`** during the hackathon.

---

## Dependency management — `venv` + `pip` (canonical) or `uv` (faster)

We deliberately stay on the documented `venv + requirements.txt` flow because:

- The `README.md`, the always-on Cursor rule, and `.github/workflows/ci.yml` all assume it.
- Teammates ranging from PMs to senior engineers will follow the README literally.
- Switching to Poetry would force doc + CI + rule updates with zero hackathon value.

**Do NOT add `pyproject.toml` / Poetry / PDM / Hatch.** Add new runtime deps to `requirements.txt` (pin a `>=` lower bound, no upper unless needed).

### One-time setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # OR (much faster, same result):
# uv pip install -r requirements.txt
cp .env.example .env                 # then fill Kapso sandbox values
```

`uv` is a drop-in replacement for `pip` that produces a normal `.venv` — anyone using plain `pip` afterwards will not notice. Prefer it locally for speed; CI keeps `pip`.

---

## Repo map (the 6 files you actually edit)

```
app/
├── main.py                  # FastAPI app, CORS, router wiring. Rarely touched.
├── config.py                # pydantic-settings .env loader. Add new env vars here.
├── bot.py                   # ⭐ inbound conversation logic. THIS is where most LLM/feature work goes.
├── send_demo_message.py     # one-off outbound CLI (`python -m app.send_demo_message --to +1...`).
├── routers/
│   ├── health.py            # GET /health
│   ├── webhooks.py          # GET/POST /webhooks/whatsapp + signature verification
│   └── api.py               # POST /api/send-text, GET /api/kapso/account (smoke-tests API key)
├── services/
│   └── kapso_client.py      # ⭐ HTTP client; helpers for text / template / media / interactive buttons / cta_url / location_request
└── schemas/
    ├── messages.py          # SendTextRequest / MessageResponse
    ├── health.py
    └── kapso/               # KapsoMessage / KapsoConversation / KapsoWebhook (extra="allow" — Kapso may add fields)
tests/test_app.py            # in-process TestClient, no network, no Kapso credentials needed
.cursor/rules/               # always-on setup rule for non-technical teammates
```

When in doubt: **edit `app/bot.py`** for behavior, **`app/services/kapso_client.py`** for new send capabilities, **`app/config.py`** for new secrets/env vars.

---

## Run commands

| Goal | Command |
|---|---|
| Activate venv | `source .venv/bin/activate` |
| Run API (terminal 1) | `uvicorn app.main:app --reload --port 8000` |
| Expose to Kapso (terminal 2) | `ngrok http 8000` → copy `https://...` host, set webhook to `https://<host>/webhooks/whatsapp` |
| Health check | `curl -s http://127.0.0.1:8000/health` |
| API key smoke test | `curl -s http://127.0.0.1:8000/api/kapso/account` |
| One-off outbound (no ngrok) | `python -m app.send_demo_message --to "+1XXXXXXXXXX"` |
| Run tests | `pytest -q` (or `.venv/bin/python -m pytest -q`) |
| Swagger UI | http://127.0.0.1:8000/docs |

**Inbound messages require BOTH Uvicorn AND ngrok running simultaneously.** Outbound (`send_demo_message`, `/api/send-text`) only needs Uvicorn.

---

## Conventions

- **Python 3.12 syntax.** Use built-in generics (`list[str]`, `dict[str, Any]`, `str | None`) — no `from typing import List, Optional`.
- **Async everywhere on the request path.** All Kapso calls go through `httpx.AsyncClient`. Don't introduce sync HTTP calls inside FastAPI handlers or `bot.py`.
- **Pydantic v2.** Models use `ConfigDict(extra="allow")` for Kapso payloads (the upstream schema evolves).
- **Logging, not print.** Use `logging.getLogger(__name__)` (already wired in `app/main.py`).
- **No secrets in code or commits.** `.env` is gitignored; new keys go in both `.env.example` (empty) and `app/config.py` (`Field(default="", alias="...")`).
- **Tests:** prefer `pytest.mark.parametrize` over duplicated test functions, and group tests in classes (`class TestSomething: def test_...`). Light integration via `TestClient` is the existing style — keep it credential-free.

When you need to add a runtime dependency: append to `requirements.txt`, then `uv pip install -r requirements.txt` (or `pip install -r requirements.txt`).

---

## Inbound message flow (so you know where to hook in)

```
WhatsApp user → Kapso → POST https://<ngrok>/webhooks/whatsapp
  → app/routers/webhooks.py: receive_webhook()
      ├── (optional) HMAC signature check via KAPSO_WEBHOOK_SECRET
      ├── parse into KapsoWebhook (app/schemas/kapso/webhook.py)
      ├── ignore if msg.direction != "inbound"
      └── await handle_inbound(msg, KapsoClient())   ← app/bot.py
              └── inbound_text(msg)                  # extracts text / button / list / kapso.content
              └── client.send_whatsapp_message(...)  # current demo: echoes back
```

To plug in an LLM, replace `_reply_body_for_demo(...)` in `app/bot.py` with your prompt/tool-calling logic. Keep the function `async`. Don't block the webhook — Kapso retries on timeout.

---

## Kapso quick reference

- **Sandbox only.** Don't touch a production WhatsApp Business number for this hackathon.
- **`KAPSO_PHONE_NUMBER_ID`** is the **sender's** WhatsApp Phone Number ID from the Kapso sandbox config — **not** any teammate's personal phone.
- **Each teammate** must add **their own personal mobile** as a sandbox test recipient in the Kapso dashboard, otherwise messages from that phone will silently fail.
- **`KAPSO_VERIFY_TOKEN`** is a string you invent in `.env`; paste the **exact same string** into the Kapso webhook config when registering the URL.
- **Webhook URL must be exact:** `https://<ngrok-host>/webhooks/whatsapp` — no truncation, no trailing slash.
- **ngrok free URLs change on restart** → re-paste in Kapso whenever ngrok restarts.
- `KapsoClient` already supports: text, template, media (image/audio/video/document), interactive buttons, CTA URL button, location request. Use those before reinventing.

---

## Git workflow for team-bachata

- **Always work on the `team-bachata` branch.** Never push to `main`.
- Hackathon rule (`KICKOFF.md`): **every teammate must push at least one commit** — including non-engineers. AI tools are how non-engineers ship; pair, don't ghostwrite.
- Small commits > one giant pre-deadline merge. Open PRs `team-bachata` → `main` only when something is stable enough to land.
- Before pushing: `pytest -q` should still pass and `.env` must not be staged.
- Optional Graphite (`gt`) is fine if individual users prefer it, but the canonical line of work is the single `team-bachata` branch (see `CONTRIBUTING.md`).

---

## What "good" at 3 PM looks like (from `KICKOFF.md`)

- Whole Bachata team on stage.
- A real WhatsApp conversation works end-to-end on screen.
- The bot does **something we're genuinely proud of**, even if narrow.
- Every member can point at one commit: *"that's mine."*

**Working > polished > clever. Done > perfect.** Build the conversation; don't yak-shave the platform.
