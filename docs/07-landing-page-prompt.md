# 07 – Landing Page Prompt

Implements a static landing page for BioVibe: a single HTML file with embedded CSS and JavaScript that presents the product and drives users directly into a WhatsApp conversation with a pre-loaded first message.

**Pre-conditions:**
- The Kapso sandbox WhatsApp number is `+56920403095`
- `app/bot.py` must handle a welcome trigger message (see TASK 2 below)
- No framework, no build step — one self-contained `index.html` file

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md` and `@docs/PRD-BioVibe.md`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer and product designer building the BioVibe landing page.
Use @docs/00-context-prompt.md and @docs/PRD-BioVibe.md as your reference.

BioVibe is a WhatsApp-based AI health tracking assistant. The landing page is the
entry point for the hackathon demo — it must make a strong first impression and
get the user into a WhatsApp conversation in one click.

TASK 1 — Create web/index.html
-------------------------------
Create a single self-contained HTML file at web/index.html.
All CSS and JavaScript must be inline (no external files, no npm, no build step).
The page must work by simply opening the file in a browser.

DESIGN REQUIREMENTS
- Dark background (#0a0a0a or similar), clean and modern
- BioVibe logo/name as large hero text with a short tagline
- One primary CTA button: "Start on WhatsApp"
- Below the button: 3 short feature highlights (icons + one-line descriptions)
- Footer with "Hackathon MVP" note
- Fully responsive (mobile-first — most users will scan the QR on their phone)

WHATSAPP DEEP LINK
The CTA button must open WhatsApp with the sandbox number and a pre-loaded message.
Use this exact URL:

  https://wa.me/56920403095?text=Hey%20BioVibe%2C%20I%27m%20ready%20to%20start%20tracking%20my%20health%21

This opens WhatsApp with the number pre-filled and the message:
  "Hey BioVibe, I'm ready to start tracking my health!"

On mobile: opens the WhatsApp app directly.
On desktop: opens web.whatsapp.com.

The button must open the link in a new tab: target="_blank".

COPY (use this text exactly)
- Hero headline: "Your Health, Tracked by AI"
- Subheadline: "Send a voice note or a quick text. BioVibe logs your meals, symptoms, sleep, and mood — and tells you what it all means."
- CTA button: "Start on WhatsApp →"
- Feature 1: "🎙 Voice or Text — just talk naturally, no forms"
- Feature 2: "🧠 AI Memory — BioVibe remembers everything you share"
- Feature 3: "💡 Proactive Insights — patterns you'd never notice yourself"

TASK 2 — Update app/bot.py to handle the welcome trigger
---------------------------------------------------------
When the bot receives exactly the trigger message from the landing page:
  "Hey BioVibe, I'm ready to start tracking my health!"

It must skip the normal Gemini flow and reply with a hardcoded welcome message:

  "Welcome to BioVibe! 🌱

  I'm your personal health tracking assistant. Here's what you can do:

  • Tell me what you ate: "Had oatmeal and coffee for breakfast"
  • Log how you feel: "I have a mild headache since noon"
  • Track your workout: "Ran 5km this morning"
  • Check in on your mood: "Feeling anxious today"

  I'll remember everything and share insights to help you feel your best.

  What would you like to track first?"

Implementation:
- In handle_inbound, before calling Gemini, check if the extracted text matches
  the trigger message (strip and case-insensitive comparison)
- If it matches: send the welcome message and return early (do not call Gemini,
  do not write to brain)
- If it does not match: proceed with the normal flow

ACCEPTANCE CHECK
----------------
1. Open web/index.html in a browser — the page must render correctly on both
   desktop and mobile viewport (use browser DevTools to simulate mobile)
2. Click "Start on WhatsApp →" — WhatsApp must open with the number and
   pre-loaded message
3. Send the trigger message from WhatsApp — the bot must reply with the welcome
   message (not the demo reply or a Gemini response)
4. Send a follow-up message like "I had eggs for breakfast" — the bot must
   proceed normally through the Gemini flow
```
