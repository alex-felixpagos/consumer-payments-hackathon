**Félix conversational hackathon**  
*Consumer payments · WhatsApp starter*

---

# Consumer payments hackathon — WhatsApp starter 🚀

**Build a bot people can actually text.** This repo is a small [FastAPI](https://fastapi.tiangolo.com/) backend wired to [Kapso](https://docs.kapso.ai/docs/introduction) so your team can **send and receive** WhatsApp messages in a sandbox, iterate locally, and focus on the *conversation*—not plumbing.

**Python:** **3.12** (pinned in `[.python-version](.python-version)`; use **3.11+** if you cannot install 3.12). **License:** [MIT](LICENSE).

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


| Approach                  | When it fits                                                                                                                                                                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Branches on this repo** | Each **team** has **one branch** off `main` that they own (see `CONTRIBUTING.md`). Teammates push there; merge to `main` via PR when ready.                                                                                                      |
| **Fork**                  | You want your own copy under your GitHub user/org, or you only have permission to push to your fork. On GitHub: **Fork** → clone **your** fork → add `upstream` pointing at this starter → branch on the fork → open PRs back to `main` here. |


Step-by-step fork commands live in **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

### What you get ✨

- **Inbound 💬:** Kapso hits your machine → you reply from `app/bot.py` (default demo: *“I just received: …Lets start building 🚀”*).
- **Outbound 📲:** One-liner script + REST helper so you can ping your phone and see it in WhatsApp.
- **No database 🧩:** Fewer moving parts; add storage when your idea needs it.

---

## Start here: Cursor + Kapso hackathon setup 🎯

**Use Cursor Agent with this repo’s setup rule—that’s the main path we support for hackathon day.**

The project ships an **always-on Cursor rule**: `[.cursor/rules/kapso-hackathon-setup.mdc](.cursor/rules/kapso-hackathon-setup.mdc)`. It walks people through the full sequence in order: Python + venv, `.env`, Kapso sandbox keys, **Uvicorn and ngrok** (two terminals), registering the Kapso webhook (`/webhooks/whatsapp`), verification token, event selection, and quick checks.

### What to do

1. Clone or open this repository in **Cursor**.
2. Open **Chat** and ask the agent to set you up—start broad or go step by step.

**Example prompts:**


| Goal              | Paste into Cursor chat                                                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Full guided setup | *“Walk me through setup and starting the bot from scratch.”*                                                                        |
| Just environment  | *“Help me create the venv, install dependencies, and copy `.env.example` to `.env`.”*                                               |
| Kapso values      | *“Help me fill `.env` from my Kapso sandbox dashboard.”*                                                                            |
| Run the stack     | *“Help me run uvicorn and ngrok on port 8000 in two terminals.”*                                                                    |
| Webhook           | *“Help me set my Kapso webhook URL and verify token to match `.env`.”*                                                              |
| Kapso feels wrong | *“I’m only using Kapso sandbox—walk me through where API key, phone number ID, and test recipient live so I don’t use production.”* |


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

*This section mirrors what `**[.cursor/rules/kapso-hackathon-setup.mdc](.cursor/rules/kapso-hackathon-setup.mdc)`** covers—use it if you want a printable checklist or you are not using Cursor. Follow the steps in order.*

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

### 2) Kapso: use **sandbox only** (avoid production) 🔐

**This hackathon starter is built for Kapso’s *sandbox / test* WhatsApp path.** Do **not** try to connect a **production** business number or “go live” unless organizers explicitly ask—that flow has different requirements and will confuse your first day.


| ✅ Do (sandbox)                                                                  | ❌ Don’t (for this starter)                                                           |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Work inside Kapso’s **Sandbox** / **test** WhatsApp configuration               | Onboard a **live production** WhatsApp Business number “just to test”                |
| Add **your own mobile** as the dashboard’s **test / sandbox recipient**         | Text the sandbox number from a friend’s phone that was **never** added in Kapso      |
| Copy **API key** + **Phone number ID** from **that same** sandbox config screen | Reuse IDs from another Kapso project, an old browser tab, or a **production** config |


**Two different “numbers” (people mix these up):**


| What                                  | What it is                                                                                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `**KAPSO_PHONE_NUMBER_ID` in `.env`** | The **WhatsApp Phone Number ID** for Kapso’s **sandbox / test sender** (a long numeric id shown next to that test number in the dashboard). **It is not your personal phone.** |
| **Your personal phone**               | The **recipient** you register in Kapso as an allowed **test user** so *your* WhatsApp can chat with the sandbox sender.                                                       |


**Pre-flight checklist (tick mentally before saving `.env`):**

- I’m in Kapso’s **sandbox / test WhatsApp** area (not “production” or a different product).
- My phone appears as an **allowed test recipient** (or I finished Kapso’s “add test number” flow).
- `KAPSO_API_KEY` comes from **this** Kapso project / sandbox config.
- `KAPSO_PHONE_NUMBER_ID` is the **sender’s** WhatsApp Phone Number ID for **that sandbox number**, copied from the same screen as the API key.
- I invented `KAPSO_VERIFY_TOKEN` in `.env` and will paste the **identical** string into Kapso when the webhook asks for the verify token.

**Then:**

1. Go to [kapso.ai](https://kapso.ai/) and create/sign in to your account.
2. Open the WhatsApp **sandbox / test** configuration (wording varies by dashboard version).
3. Complete **add test recipient** (or equivalent) with **your** mobile in international format if the UI asks.
4. Copy into `.env`:
  - `KAPSO_API_KEY`
  - `KAPSO_PHONE_NUMBER_ID` (sender / sandbox number ID — see table above)
5. Add a secret you choose:
  - `KAPSO_VERIFY_TOKEN=your-secret-token`  
   You will reuse this exact value when you create the webhook in Kapso (step 5 later in this doc).

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
- **No WhatsApp delivery / “number not allowed”:** your phone is **not** registered as a **sandbox test recipient**, or you’re texting from a different device than the one you added.
- **Wrong `KAPSO_PHONE_NUMBER_ID`:** you copied the ID from **production**, another project, or the wrong panel—re-copy from the **same sandbox WhatsApp** screen as the API key.
- **Trying to use production:** pause and switch back to **sandbox** for this repo; production onboarding is a different checklist (not covered here).

## Demo outbound message 🎯

```bash
python -m app.send_demo_message --to "+1XXXXXXXXXX"
```

## Routes 🗺️

- `GET /health`
- `GET /webhooks/whatsapp` (verification)
- `POST /webhooks/whatsapp` (inbound events)
- `POST /api/send-text` (manual outbound)
