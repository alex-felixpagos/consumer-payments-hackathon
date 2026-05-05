**Félix conversational hackathon**  
*Consumer payments · WhatsApp starter*

---

# Consumer payments hackathon — WhatsApp starter 🚀

**Build a bot people can actually text.** This repo is a small [FastAPI](https://fastapi.tiangolo.com/) backend wired to [Kapso](https://docs.kapso.ai/docs/introduction) so your team can **send and receive** WhatsApp messages in a sandbox, iterate locally, and focus on the *conversation*—not plumbing.

---

## Hackathon objective 🏆

Build a **conversational product** that solves a real problem.

- **Your mission:** Pick a problem, design a WhatsApp conversation flow, and ship a working demo.
- **Team goal:** Create the most useful, creative, and polished conversational experience you can in hackathon time.
- **Deadline:** Final push to `main` by **Wednesday at 5pm** (clarify timezone with organizers if unsure).
- **How we pick a winner:** Everyone votes for their favorite project, and the team with the coolest project wins. 🎉

Think of this starter as your launchpad: focus your energy on the conversation, user value, and demo story.

---

## IMPORTANT - Project requirements ✅

To be considered a successful hackathon submission, teams should follow these rules:

1. **Vibe-code it with Cursor Agent:** Core implementation should be built through Cursor Agent workflows.
2. **Everyone contributes code:** Every teammate must push at least one change to the repository.
3. **Make it fun:** Build something that excites your team and is genuinely enjoyable to demo.

---

### What you get ✨

- **Inbound 💬:** Kapso hits your machine → you reply from `app/bot.py` (default demo: *“I just received: …Lets start building 🚀”*).
- **Outbound 📲:** One-liner script + REST helper so you can ping your phone and see it in WhatsApp.
- **No database 🧩:** Fewer moving parts; add storage when your idea needs it.

---

# Initial Setup (Start here ⬇️)

Ask the agent: *“Help me set up `.env`, Kapso, ngrok, and start the server.”*  
The project loads **`.cursor/rules/kapso-hackathon-setup.mdc`** so everyone gets the same step-by-step path—including teammates who rarely touch the terminal.

#### How to use the rule directly

1. Open Cursor chat in this repo.
2. Ask for one step at a time (recommended for non-technical teammates).
3. Use prompts like:
  - `Walk me through setup and starting the bot`
  - `Help me fill .env for Kapso sandbox`
  - `Help me run uvicorn and ngrok`
  - `Help me configure the Kapso webhook URL and events`

The rule is auto-applied in this project, so you do **not** need to manually load it each time.

---

## First-time setup (detailed) 🧭

If you have never used Kapso or ngrok before, follow these steps in order.

### 1) Local Python setup 🐍

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

If `python3` is missing, install Python 3.11+ from [python.org](https://www.python.org/downloads/).

### 2) Create your Kapso account + sandbox 🔐

1. Go to [kapso.ai](https://kapso.ai/) and create/sign in to your account.
2. Open the WhatsApp **sandbox** setup area.
3. Add your personal phone number as an allowed test recipient (if prompted).
4. Copy these values from Kapso into your local `.env`:
  - `KAPSO_API_KEY`
  - `KAPSO_PHONE_NUMBER_ID`
5. Pick your own secret verify token and add it to `.env`:
  - `KAPSO_VERIFY_TOKEN=your-secret-token`

### 3) Install and configure ngrok (required) 🌍

Kapso needs a public HTTPS URL to send webhooks to your laptop.

1. Create a free account at [ngrok.com](https://ngrok.com/).
2. Install ngrok:
  - macOS (Homebrew): `brew install ngrok/ngrok/ngrok`
  - Other OS: use [ngrok download](https://ngrok.com/download)
3. In the ngrok dashboard, copy your authtoken and run:

```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### 4) Start the app + tunnel (2 terminals) 🖥️

**Terminal 1 (API):**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (ngrok):**

```bash
ngrok http 8000
```

Copy the HTTPS ngrok host (example: `https://abcd-123.ngrok-free.app`).

### 5) Register webhook in Kapso 📬

In Kapso “Add Webhook Endpoint” (or similar):

- **Endpoint URL:** `https://<your-ngrok-host>/webhooks/whatsapp`
  - Must include the full `/webhooks/whatsapp` path (no truncation).
- **Verify token:** must exactly match `KAPSO_VERIFY_TOKEN` in `.env`.
- **Webhook type:** use what sandbox allows (usually **Kapso (events)**).
- **Events:** enable **Message received**.
- **Message debouncing:** keep it **off** for easier debugging.

### 6) Quick checks ✅

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- API key smoke test:

```bash
curl -s http://127.0.0.1:8000/api/kapso/account
```

If you see JSON (including `{"data":[]}`), your key is valid.

### 7) Common first-time issues 🧯

- **No inbound messages:** check both terminals are running, and Kapso URL is exactly `https://<ngrok-host>/webhooks/whatsapp`.
- **ngrok restarted:** free ngrok URL changed; update webhook URL in Kapso.
- **Verify token failed:** Kapso verify token and `.env` `KAPSO_VERIFY_TOKEN` do not match exactly.
- **No WhatsApp delivery:** confirm your phone was added as a sandbox recipient in Kapso.

## Demo outbound message 🎯

```bash
python -m app.send_demo_message --to "+1XXXXXXXXXX"
```

## Routes 🗺️

- `GET /health`
- `GET /webhooks/whatsapp` (verification)
- `POST /webhooks/whatsapp` (inbound events)
- `POST /api/send-text` (manual outbound)

---

**Go build something people can text. Have fun and ship fast ⚡**