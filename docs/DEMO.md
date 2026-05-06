# Felix Pay (Colombia) — 60-second demo script

Use this script when presenting **Track D: Felix Pay** on WhatsApp with Kapso sandbox numbers.

## The line about QR decoding

If the demo uses a mocked QR decode step, say this aloud when you show the photo step:

> **In production we read the Bre-B llave from this QR.**

That sets expectations: the hackathon build may stub parsing, but the real product reads the merchant key from the Bre-B QR.

---

## 60-second run-through (Colombia Felix Pay)

| Sec | You do / say | On WhatsApp |
| --- | --- | --- |
| 0–10 | “This is **Felix Pay** for Colombia—pay a merchant over WhatsApp using **Bre-B**.” | Open the bot thread on your **Kapso sandbox** phone. |
| 10–25 | “The shopper sends a **photo of the merchant’s Bre-B QR**.” | Send a clear photo of a sample / printed Bre-B QR (or your team’s test asset). |
| 25–40 | “We resolve the merchant, show **FX** if needed, and they **tap preset amounts** or type COP.” | Walk through amount chips or typed amount; call out **COP** and vendor name. |
| 40–50 | “They **confirm**—still sandbox, no rails.” | Tap confirm; narrate that this is **mock** settlement. |
| 50–60 | “Here’s the **mock receipt** and we’d notify the vendor in production.” | Show receipt message; optionally mention Spanish vendor ping in the product copy. |

**Closer:** “Same flow on a real phone in production—here we’re on **Kapso sandbox** and mock backend.”

---

## Kapso sandbox phones — pre-demo checklist

- [ ] **Kapso dashboard:** Sandbox **API key**, **phone number ID**, and **test recipient** numbers match `.env` (not production).
- [ ] **Webhook:** `https://<your-ngrok>/webhooks/whatsapp` registered; verify token matches app config.
- [ ] **Two devices ready:** **Inbound** phone (receives bot replies) and optional **second** sandbox number if your flow tests merchant vs payer.
- [ ] **ngrok + uvicorn** running; health check passes (`/health` or organizer’s check).
- [ ] **Test assets:** Bre-B QR image on camera roll; printed QR avoids glare during live demo.
- [ ] **Wi‑Fi / data** stable on the demo phone; **Do Not Disturb** off for WhatsApp notifications.

---

## Related

- Repo setup: root `README.md` and `.cursor/rules/kapso-hackathon-setup.mdc`
- Bot behavior: `app/bot.py` (do not change for this doc-only track unless your team owns that integration)
