**Félix conversational hackathon**  
*Consumer payments · WhatsApp starter*

---

# Consumer payments hackathon — WhatsApp starter 🚀

**Build a bot people can actually text.** This repo is a small [FastAPI](https://fastapi.tiangolo.com/) backend wired to [Kapso](https://docs.kapso.ai/docs/introduction) so your team can **send and receive** WhatsApp messages in a sandbox, iterate locally, and focus on the *conversation*—not plumbing.

**Python:** **3.12** (pinned in [`.python-version`](.python-version); use **3.11+** if you cannot install 3.12). **License:** [MIT](LICENSE).

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

**How to collaborate (optional):** **[CONTRIBUTING.md](CONTRIBUTING.md)** is a **suggested** guide (branches, small PRs, secrets)—teams can ignore it or follow it loosely.

**Two common Git approaches:**

| Approach | When it fits |
|----------|----------------|
| **Branches on this repo** | Everyone has write access; fastest for small teams. Create a branch, open a PR to `main`, merge often. |
| **Fork** | You want your own copy under your GitHub user/org, or you only have permission to push to your fork. On GitHub: **Fork** → clone **your** fork → add `upstream` pointing at this starter → branch on the fork → open PRs back to `main` here. |

Step-by-step fork commands live in **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

### What you get ✨

- **Inbound 💬:** Kapso hits your machine → you reply from `app/bot.py` (default demo: *“I just received: …Lets start building 🚀”*).
- **Outbound 📲:** One-liner script + REST helper so you can ping your phone and see it in WhatsApp.
- **No database 🧩:** Fewer moving parts; add storage when your idea needs it.

---

## Start here: Cursor + Kapso hackathon setup 🎯

**Use Cursor Agent with this repo’s setup rule—that’s the main path we support for hackathon day.**

The project ships an **always-on Cursor rule**: [`.cursor/rules/kapso-hackathon-setup.mdc`](.cursor/rules/kapso-hackathon-setup.mdc). It walks people through the full sequence in order: Python + venv, `.env`, Kapso sandbox keys, **Uvicorn and ngrok** (two terminals), registering the Kapso webhook (`/webhooks/whatsapp`), verification token, event selection, and quick checks.

### What to do

1. Clone or open this repository in **Cursor**.
2. Open **Chat** and ask the agent to set you up—start broad or go step by step.

**Example prompts:**

| Goal | Paste into Cursor chat |
|------|-------------------------|
| Full guided setup | *“Walk me through setup and starting the bot from scratch.”* |
| Just environment | *“Help me create the venv, install dependencies, and copy `.env.example` to `.env`.”* |
| Kapso values | *“Help me fill `.env` from my Kapso sandbox dashboard.”* |
| Run the stack | *“Help me run uvicorn and ngrok on port 8000 in two terminals.”* |
| Webhook | *“Help me set my Kapso webhook URL and verify token to match `.env`.”* |

You **do not** need to open or paste the `.mdc` file manually—the rule applies automatically in this workspace.

### Not using Cursor?

Use the **[Detailed setup reference](#detailed-setup-reference-manual-checklist)** at the end of this README (same flow, written out as a checklist). You can also pair with a teammate who is using Cursor.

---

## Demo outbound message 🎯

No ngrok required for a one-off send—only a filled `.env` and a sandbox-approved phone:

```bash
python -m app.send_demo_message --to "+1XXXXXXXXXX"
```

---

## API routes (quick ref) 🗺️

- `GET /health` — liveness
- `GET /webhooks/whatsapp` — Kapso/Meta webhook verification
- `POST /webhooks/whatsapp` — inbound events → `app/bot.py`
- `POST /api/send-text` — manual outbound (Swagger: `/docs`)

---

## Run tests 🧪

Light **integration** tests hit the FastAPI app in-process (`TestClient`)—no Kapso credentials or network calls required.

```bash
pip install -r requirements.txt
pytest
```

---

**Go build something people can text. Have fun and ship fast ⚡**

---

## Detailed setup reference (manual checklist) 🧭

*This section mirrors what **[`.cursor/rules/kapso-hackathon-setup.mdc`](.cursor/rules/kapso-hackathon-setup.mdc)** covers—use it if you want a printable checklist or you are not using Cursor. Follow the steps in order.*

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
