# PRD — Conversational debt payment coach (WhatsApp, hackathon scope)

**Version:** 0.2 (3-hour hackathon build)  
**Date:** 2026-05-06  
**Channel:** WhatsApp via Kapso (sandbox for demo)  
**Stack:** FastAPI starter in this repo; bot logic lives in `app/bot.py` (today: echo reply — replace with a **small state machine + scripted coach flow**)

---

## 1. Executive summary (winning move for ~3 hours)

**Do not build the bank product.** Build a **believable conversation** around payment planning: fake all financial infrastructure, make the chat feel real, and demo **one complete journey** end-to-end.

The product story: help someone **name a debt payment goal**, **set a tiny budget** (three buckets), **see a simulated “payment envelope”** with illustrative yield, **trigger a D-1-style reminder on demand** (no real scheduler), and **handle the emotionally useful shortfall case** with safe, non-advisory language.

Long-term vision can still include real yield accounts and bank APIs — that language belongs **only under Roadmap**, not in the hackathon MVP copy shown to judges.

---

## 2. Demo assumptions (read this first)

| Assumption | What it means for the demo |
|------------|----------------------------|
| **No real money movement** | All balances and transfers are fictional. |
| **No real account creation** | “Envelope” is a **simulated payment envelope**, not an actual bank account. |
| **No financial advice** | Use: *“Here are general options to consider”* and *“Check your lender terms before changing payments.”* |
| **Yield is simulated** | Show an **estimated** illustrative yield for the envelope; never imply a guarantee. |
| **Reminders are manually triggered** | For demo, user texts `reminder` (or `simulate tomorrow`) — **no cron**, no real D-1 scheduling. Judges care that the **story** works, not that a job runner is wired. |

---

## 3. Problem, hypothesis, and emotional hook

- People juggle due dates and cash timing; a **simple WhatsApp coach** can reduce panic.  
- **Hypothesis (demo):** A guided flow makes the plan **legible** in under three minutes.  
- **Emotional hook:** The **shortfall flow** (“I can’t cover principal”) must feel helpful, not like a robot saying “denied.” It should **quantify the gap** and offer **three general options** with **guardrails** (see §8).

---

## 4. Terminology: hackathon vs roadmap

| Hackathon MVP (use in UI/copy) | Roadmap (product / regulated context) |
|--------------------------------|--------------------------------------|
| **Simulated payment envelope** | Yield-bearing savings or cash-management account |
| **Estimated / simulated yield** | Actual APY, partner bank terms, disclosures |
| **`reminder` command** = “pretend it’s the day before” | Real D-1 scheduling, time zones, bank holidays, cutoffs |
| **General options to consider** | Deeper advisory or licensed guidance |

---

## 5. Out of scope for the 3-hour MVP (explicit cut list)

Do **not** implement in the hackathon window:

- Multi-debt portfolios  
- Biweekly / complex cadence  
- Bank holidays, settlement windows, time-zone logic  
- KYC, bank APIs, or any real account opening  
- Durable storage (database) — **in-memory state keyed by phone number** is enough  
- Real scheduled jobs / cron for reminders  

These remain **roadmap** items for a post-hackathon PRD.

---

## 6. Target user (one sentence)

Someone with a **known monthly payment** who wants a **quick plan** and a **calm nudge** before the due date — demo’d through one scripted persona.

---

## 7. Locked demo persona (do not improvise live)

Use this **fixed script** for the pitch so the conversation is not generic or fragile.

| Field | Value |
|-------|--------|
| Debt label | Credit card |
| Payment goal | **$450** |
| Due date | **May 15** (adjust display year to match demo date if needed) |
| Monthly income | **$3,000** |
| Essentials | **$1,800** |
| Flexible spending | **$500** |
| Implied “available” before debt line | $3,000 − $1,800 − $500 = **$700** (debt goal $450 → **feasible** in happy path) |
| Shortfall scenario (optional second beat) | Same income/buckets but payment goal **$450** with only **$330** left for the payment after tweaks — **short $120** (use a variant script or user says they can only allocate $330) |

**Shortfall example copy (guardrails built in):**  
*“Your payment goal is **$450**, but your budget leaves **$330** available. You’re short **$120**. Here are **three general options to consider**: reduce flexible spending by **$60**, see whether **splitting extra principal** is allowed under **your lender terms**, or **prioritize the minimum payment** to reduce **late-fee risk**. **Check your lender terms before changing payments** — this isn’t financial advice.”*

---

## 8. Shortfall flow — product requirements

- **Trigger:** Phrase such as `help principal`, `I can't cover principal`, or detected gap after `budget` / `goal`.  
- **Must do:** State goal amount, stated available amount, **gap dollar amount**, then **exactly three** bullet options.  
- **Must not:** Promise lender approval, imply guaranteed outcomes, or sound like personalized investment advice.  
- **Required phrases (use verbatim tone):** *“General options to consider”* · *“Check your lender terms before changing payments.”*

---

## 9. Budget scope (3 buckets max)

For WhatsApp turn count and build time: **only three categories**

1. **Essentials**  
2. **Flexible spending**  
3. **Debt payment** (or amount available toward the goal after the first two)

Do **not** use six-line item categories (housing, transport, food, etc.) in the MVP — too many turns.

---

## 10. Bot commands and behavior (MVP contract)

Implement a **command router + light state machine** in `app/handle_inbound` path (replacing echo demo). **State:** in-memory dict keyed by **phone number** (no DB).

| Command / intent | Behavior |
|------------------|----------|
| `start` | Begin guided onboarding; first question: *“What debt are we planning for?”* |
| `goal` | Capture **debt label**, **amount**, **due date** (can be same session as `start` or explicit command reset) |
| `budget` | Capture **monthly income** + **essentials** + **flexible** (third bucket implied or named “debt / remainder”) |
| `envelope` | Show **simulated saved amount** toward goal + **estimated simulated yield** (clearly labeled simulated) |
| `reminder` | **Simulate** the day-before message: e.g. *“Your credit card payment is due tomorrow. Move $450 from your envelope today.”* |
| `help principal` (or natural phrase) | Run **shortfall flow** (§8) |

Optional: `menu` lists commands. Unknown text → gentle nudge toward `start` or next expected step in the state machine.

---

## 11. Recommended live demo script (judge-friendly, ~3 minutes)

1. User: `start`  
2. Bot: *“I can help you plan a debt payment. What debt are we planning for?”*  
3. User: *Credit card*  
4. Bot asks **amount** and **due date**  
5. User: *$450 due May 15*  
6. Bot asks **income** and **simple budget** (essentials + flexible)  
7. User: *Income 3000, essentials 1800, flexible 500*  
8. Bot: computes remainder, states whether **$450** goal fits, summarizes plan  
9. Bot: confirms **simulated payment envelope** created (copy only)  
10. User: `reminder`  
11. Bot: D-1 style message (simulated)  
12. User: *I can't cover principal* (or shortfall variant)  
13. Bot: gap + three options + guardrail line  

That is a **complete story**: plan → envelope story → reminder → empathy under constraint.

---

## 12. Technical approach (aligned to repo)

- **Current state:** `_reply_body_for_demo` / `handle_inbound` echo — fastest path is **replace** with scripted steps + parser for commands.  
- **Hour 1:** State object per phone + command router in `app/bot.py` (or tiny helper module if needed, keep diff small).  
- **Hour 2:** Implement `goal`, `budget`, `envelope`, `reminder`, shortfall responses with locked numbers for persona.  
- **Hour 3:** Polish copy, run WhatsApp + ngrok smoke test, **freeze demo script**, add **2–3 unit tests** for parsing / gap math (pure functions).  

**QA bar:** If a judge sends random text, the bot should **recover** to `start` / `menu` without crashing.

---

## 13. Non-functional (unchanged essentials)

- No CVV, passwords, or account numbers in chat.  
- Webhook verification and secrets only in `.env` — not in git.  
- Sandbox WhatsApp only unless organizers require otherwise.

---

## 14. Success criteria (this hackathon)

- **One** polished journey (§11) with no dead ends in the happy path.  
- Shortfall beat uses **safe copy** (§8).  
- Team can explain in one sentence: **“We simulated the bank; we shipped the coach.”**

---

## 15. Roadmap (post-hackathon — do not build now)

Real yield product, lender integrations, persisted users, true D-1 scheduling, multi-debt, compliance review, and advisory disclaimers reviewed by counsel.

---

## 16. Glossary

- **Simulated payment envelope:** In-app fiction for “money set aside for this payment” — not a real account.  
- **Principal (in copy):** User-facing word for “extra beyond minimum” only if the script uses it; always pair with lender-term disclaimer.  
- **D-1 (demo):** Whatever `reminder` says — not calendar-accurate in MVP.

---

## 17. Team checklist

- [ ] Replace echo bot with state machine + commands (§10).  
- [ ] Memorize demo script (§11); print one-page cheat sheet for presenter.  
- [ ] Add minimal tests for gap math and command routing.  
- [ ] Rehearse with **one** ngrok URL and Kapso webhook path `/webhooks/whatsapp`.

---

*PRD v0.2 narrows scope to a 3-hour, judge-ready demo. Vision lives in §4 and §15 only.*
