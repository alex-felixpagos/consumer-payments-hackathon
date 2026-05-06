# BioVibe – AI-Driven Biohacking Assistant

**Status:** Hackathon MVP — Shipped  
**Stack:** Gemini 1.5 Flash · FastAPI · WhatsApp (Kapso) · Ngrok · Multilingual Landing Page (Netlify)

---

## Solution Overview

```mermaid
sequenceDiagram
    actor User as User
    participant Site as Landing Page
    participant Kapso as Kapso API
    participant API as FastAPI bot.py
    participant Gemini as Gemini 1.5 Flash
    participant Brain as JSON Brain

    User->>Site: Visits site in EN / ES / PT
    Site->>Kapso: WhatsApp deep-link with pre-filled trigger
    Kapso->>API: POST /webhooks/whatsapp
    API->>Brain: load_brain + save detected lang
    API->>Kapso: send hero image + welcome interactive message
    Kapso->>User: Hero image + welcome in user language + profile button

    opt User taps profile button
        Kapso->>API: button_reply = setup_profile
        API->>Brain: load_brain - read profile
        API->>Kapso: profile summary or setup prompt
        Kapso->>User: Profile info or guided questions
    end

    User->>Kapso: Text, voice note, or image
    Kapso->>API: POST /webhooks/whatsapp
    API->>Brain: load_brain(user_id)
    Brain-->>API: profile + health_summary + log_history
    API->>Gemini: message + brain context
    Note over Gemini: Classify intent and extract structured data

    alt intent = log
        Gemini-->>API: category + structured data + reply
        API->>Brain: append_log entry
        API->>Brain: refresh summary every 5 logs
    else intent = query
        Gemini-->>API: answer based on history
    else intent = profile_update
        Gemini-->>API: name + traits + reply
        API->>Brain: update_profile
    else intent = unrecognized
        Gemini-->>API: friendly redirect reply
    end

    API->>Kapso: send reply text
    API->>Kapso: send 3 contextual quick-log buttons
    Kapso->>User: Reply + insight + quick-log buttons
```

---

## How We Built It

Rather than jumping straight into code, we applied a structured engineering methodology from the first minute of the hackathon.

### 1. Product First — PRD Before Code

We started by writing this PRD: executive summary, problem statement, functional requirements, data model, and a sequence diagram. This forced alignment on what we were building before anyone opened a code editor.

### 2. Structured Prompt Engineering

Each implementation task was designed as a **self-contained prompt** following a professional prompt engineering structure:

| Section | Purpose |
|---|---|
| **Persona** | Defines who the AI is acting as (senior software engineer) |
| **Context** | Full technical reference — codebase structure, schemas, conventions |
| **Pre-conditions** | What must exist before this prompt can run |
| **Objective** | Numbered, unambiguous tasks with no room for interpretation |
| **Outcome** | Exact function signatures, file paths, and JSON schemas expected |
| **Acceptance Check** | A concrete test the engineer runs to verify before moving on |

This eliminated the most common AI coding failure: the agent having to guess what was already built.

### 3. Decoupled Parallel Execution

Prompts were designed so different team members could work independently:

```
01-brain          (no deps)
    ├──► 02-gemini + bot  ──► 04-gemini tests
    └──► 03-brain tests
              └──► 05-profile update ──► 06-profile tests
```

No verbal handoff needed — every prompt includes enough context to be picked up cold by any team member on any machine.

### 4. Docs as the Single Source of Truth

`docs/00-context-prompt.md` acts as the living technical reference — intent model, data schemas, message flow, coding conventions — kept in sync with every decision made during the hackathon.

---

## 1. Executive Summary

BioVibe is a conversational AI agent for WhatsApp that eliminates the friction of health tracking. Instead of manual data entry in complex apps, users send quick voice notes or text messages about meals, symptoms, and habits. BioVibe acts as the "Brain" — storing a longitudinal history in JSON format to identify correlations and surface proactive biohacking insights.

---

## 2. Problem Statement

Health enthusiasts and high-performers consistently fail to track their data because traditional apps require too many clicks and context switches. This creates **data silos** where symptoms (e.g., a headache) are never linked to root causes (e.g., poor sleep or specific foods), making pattern discovery impossible.

---

## 3. The "AI as the Brain" Concept

Unlike a standard chatbot, BioVibe:

| Capability | Description |
|---|---|
| **Multimodal Input** | Accepts voice notes, text, and images; Kapso transcribes audio automatically; Gemini Vision analyzes image content directly |
| **State Management** | Maintains an evolving user profile, not just a message log |
| **Insight Synthesis** | Cross-references today's log with full history to surface patterns |

---

## 4. Functional Requirements

### FR1 – Onboarding & Landing Page

- A static multilingual landing page (`web/index.html`) serves as the public entry point to BioVibe.
- Available in **English, Spanish, and Portuguese** with auto-detection of the browser language and a manual switcher.
- A WhatsApp CTA button pre-fills a language-specific trigger message (e.g. *"Oi BioVibe, estou pronto para começar a monitorar minha saúde!"*) that deeplinks directly to the bot.
- When the bot receives the trigger message it:
  1. Detects the language and persists it to the user's brain (`lang` field).
  2. Sends the **BioVibe hero image** as a visual brand touchpoint.
  3. Sends a **multilingual interactive message** with a "Set up my profile" button.
- Tapping **"Set up my profile"**:
  - If a profile already exists → displays name and traits saved so far.
  - If no profile exists → sends a conversational prompt asking for name, dietary restrictions, allergies, and health goals.

### FR2 – Multimodal Ingestion

- Accept voice notes (`.ogg` / `.mp3`), plain text, and images via WhatsApp.
- Kapso transcribes audio automatically and delivers the transcript alongside the message — no separate transcription step needed.
- Gemini receives the transcript as plain text and extracts structured data in a single pass.
- For images: Kapso delivers the image URL in the webhook payload; the bot downloads the image bytes and passes them to Gemini as a multimodal input alongside any user caption.
- Gemini Vision identifies health-relevant content in images: food, meals, workout screens, body metrics, nutrition labels, etc.
- `media_type` is recorded as `"image"` in the log entry.

### FR3 – Intent Recognition

Before any logging or response, the system must classify the user's input into one of three intents:

| Intent | Description | Examples |
|---|---|---|
| **Log** | User is recording health data | "Lunch was pasta", "I have a headache", "Ran 5km", [photo of a meal], [photo of a treadmill screen] |
| **Query** | User is asking a health-related question or summary | "How was my mood this week?", "What is gluten?", "Am I sleeping enough?" |
| **Unrecognized** | Message is unrelated to the service scope | "Send me a joke", "What's the weather?", "Hello" |
| **Profile Update** | User shares persistent personal information | "I'm lactose intolerant", "My name is Rodrigo", "I'm vegetarian" |

- **Log intent** → proceed to FR4 (extract structured data, save to Brain, reply with insight)
- **Query intent** → answer using the user's history as context; do **not** create a new log entry
- **Unrecognized intent** → reply with a friendly message explaining what the user can send; do **not** create a log entry
- **Profile Update intent** → update `profile.name` and/or `profile.traits`; do **not** create a log entry

This prevents polluting the JSON Brain with irrelevant data and ensures the history stays meaningful.

### FR4 – Structured Health Logging

- Only triggered after a **Log** intent is confirmed (see FR2).
- Categorize the log into one of: **Nutrition · Symptom · Activity · Sleep · Mood**.
- Extract data into a consistent JSON schema with fields such as `ingredients`, `duration`, and `intensity`.
- For image-based logs, `raw_input` stores the image URL and any user caption.

**Calorie estimation (Nutrition logs):**
- Gemini must always attempt to estimate calories for every Nutrition log entry, whether the input is text, audio, or an image of food.
- The estimate is based on typical portion sizes and the model's food knowledge. It is surfaced to the user in the reply (e.g. "around 550 kcal").
- `estimated_calories` is set to `null` only when the food is completely unidentifiable.

**Example log entry:**

```json
{
  "timestamp": "2026-05-05T14:30:00Z",
  "category": "Nutrition",
  "raw_input": "Had a bowl of pasta with cheese for lunch",
  "media_type": "text",
  "structured": {
    "meal": "pasta with cheese",
    "ingredients": ["pasta", "cheese"],
    "estimated_calories": 650
  }
}
```

### FR5 – Persistent Memory (The JSON Brain)

- Maintain one local JSON file per `user_id` (phone number).
- File structure:

```json
{
  "user_id": "5511999999999",
  "lang": "pt",
  "profile": {
    "name": "Rodrigo",
    "traits": ["Lactose Intolerant", "intermittent faster"]
  },
  "health_summary": "AI-generated narrative, updated every 5 logs.",
  "log_history": []
}
```

- `lang` is set from the landing page trigger and drives all bot-initiated copy (welcome, profile prompt, quick-log buttons).
- The `health_summary` field is regenerated by Gemini every **5 new log entries**.

### FR6 – Quick-Log Contextual Buttons

After every **log** or **query** response, the bot sends a secondary interactive message with 3 quick-log buttons tailored to what the user just logged:

| Last logged | Buttons shown |
|---|---|
| Nutrition | 🏃 Just exercised · 😴 Log my sleep · 💧 Drank water |
| Activity  | 🍽️ Log a meal · 😴 Log my sleep · 😊 Log my mood |
| Sleep     | 😊 Log my mood · 🍽️ Log a meal · 🏃 Just exercised |
| Symptom   | 🍽️ Log a meal · 😊 Log my mood · 🏃 Just exercised |
| Mood      | 🍽️ Log a meal · 🏃 Just exercised · 😴 Log my sleep |

- Button labels are fully localised (EN / ES / PT) using the `lang` stored in the brain.
- Tapping a button sends the button title as a WhatsApp message → Gemini processes it naturally and starts a conversational flow to capture the details.

### FR7 – Proactive Insights (The Biohacker Persona)

- Every response must close with a personalised **Insight** derived from the user's history.
- Insight must reference at least one past log entry when available.

> **Example:** *"You've reported low energy 30 minutes after eating pasta twice this week. Consider testing a lower-carb lunch tomorrow."*

### FR8 – Image Response Requirements

Every reply to an image message must contain three parts, in order:

1. **Acknowledgement** — describe what was detected in the image in warm, natural language.
   > *"Oh nice, I can see a plate of rice, beans, and grilled chicken!"*

2. **Positive recognition** — celebrate good behaviour when present before any suggestion. If the choice is not ideal, frame it warmly, never judgmentally.
   > *"That's a solid balanced meal — good protein, complex carbs, and reasonable portions."*
   > *"That looks like a treat meal — totally fine, everyone needs those!"*
   > If the user is on a streak: *"Three solid meals in a row — that's real consistency."*

3. **One personalised recommendation** — a single actionable tip framed as encouragement, grounded in the image and the user's history.
   > *"Adding a handful of greens tomorrow would make this streak even stronger."*

**Tone rules (hard constraints for all image replies):**
- Always lead with what the user did well before suggesting improvements.
- Never use "avoid", "you should", "you must" — use "you might try", "one option is", "have you considered".
- Acknowledge streaks explicitly when the user has been consistent.
- If the image is not health-relevant (meme, landscape, selfie with no health signal), classify as `unrecognized` and reply with the standard onboarding message.

---

## 5. Technical Requirements

| Concern | Decision |
|---|---|
| **API framework** | FastAPI (webhook listener) |
| **LLM** | `gemini-1.5-flash` — speed + native audio |
| **Storage** | Local JSON filesystem, one file per user |
| **Tunneling** | Ngrok (dev only) |
| **WhatsApp integration** | Kapso API (hackathon sandbox) |

### Codebase Structure

```
app/
├── main.py                  # FastAPI entrypoint, router registration
├── bot.py                   # handle_inbound() + inbound_text() — orchestrates message flow
├── config.py                # Settings via pydantic-settings / .env
├── prompts/
│   └── biovibe_system.txt   # Gemini system prompt (loaded at runtime)
├── routers/
│   ├── webhooks.py          # GET (verification) · POST (inbound) · POST /debug
│   ├── api.py               # POST /api/send-text · GET /api/kapso/account
│   └── health.py            # GET /health
├── schemas/
│   ├── kapso/               # KapsoWebhook, KapsoMessage, etc.
│   └── messages.py          # SendTextRequest, MessageResponse, HealthResponse
└── services/
    ├── kapso_client.py      # Async HTTP wrapper for Kapso REST API
    ├── gemini_client.py     # Gemini SDK wrapper — intent, extraction, reply
    └── brain.py             # JSON Brain read/write (synchronous)

web/
├── index.html               # Multilingual landing page (EN / ES / PT) — deployed on Netlify
└── biovibe-hero.png         # Brand hero image served via GitHub raw URL

data/                        # Created at runtime — one JSON file per user
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/` | Service info / links |
| `GET` | `/webhooks/whatsapp` | Kapso webhook verification (hub challenge) |
| `POST` | `/webhooks/whatsapp` | Inbound message handler → calls `bot.handle_inbound` |
| `POST` | `/webhooks/whatsapp/debug` | Echo raw payload — use while wiring Kapso locally |
| `POST` | `/api/send-text` | Manual outbound text (curl / Postman tests) |
| `GET` | `/api/kapso/account` | Confirms API key against Kapso platform |

### Message Processing Flow

```
WhatsApp User
    │
    ▼
Kapso Webhook ──► POST /webhooks/whatsapp   (routers/webhooks.py)
    │
    │  signature check + KapsoWebhook schema validation
    │
    ▼
bot.handle_inbound(msg, client)             (bot.py)
    │
    ├── bot.inbound_text(msg)
    │       ├── msg.type == "text"      → msg.text.body
    │       ├── msg.interactive         → button_reply / list_reply title
    │       ├── msg.button              → button text / payload
    │       └── msg.kapso.content       → fallback
    │
    ▼  [TO IMPLEMENT for BioVibe]
    │
    │  inbound_text(msg) returns plain text in both cases:
    ├── msg.type == "text"  → msg.text.body
    └── msg.type == "audio" → msg.kapso.content (Kapso transcribes automatically)
                                                        │
                                                        ▼
                                          Gemini (text + brain context)
                                                        │
                                                        ▼
                          ┌────────── Intent Recognition ──────────┐
                          │            │               │           │
                         LOG         QUERY       UNRECOGNIZED  PROFILE_UPDATE
                          │            │               │           │
                          ▼            ▼               ▼           ▼
                 Extract structured  Answer using   Friendly   Update profile
                   log entry        Brain history   reply only  (name + traits)
                          │            │                           │
                          ▼            │                           │
                 Update JSON Brain     │                           │
                 (data/{user_id}.json) │                           │
                          │            │                           │
                          ▼            │                           │
                 Generate insight ◄────┴───────────────────────────┘
                                        │
                                        ▼
                           client.send_whatsapp_message()
                           (services/kapso_client.py)
```

---

## 6. Data Model

### User Brain File (`data/{user_id}.json`)

```json
{
  "user_id": "string",
  "profile": {
    "name": "string | null",
    "traits": ["string"]
  },
  "health_summary": "string",
  "log_history": [
    {
      "id": "uuid",
      "timestamp": "ISO8601",
      "category": "Nutrition | Symptom | Activity | Sleep | Mood",
      "raw_input": "string",
      "media_type": "text | audio | image",
      "structured": {}
    }
  ]
}
```

---

## 7. User Stories

| ID | Story |
|---|---|
| US-01 | As a user, I want to send a voice note of my lunch so I don't have to type ingredients. |
| US-02 | As a user, I want the assistant to remember my allergies so it can warn me proactively. |
| US-03 | As a user, I want to ask "How has my mood been this week?" and get a summary based on my logs. |
| US-04 | As a user, I want to receive a health insight after every message without asking for it. |
| US-05 | As a user, I want to send a photo of my meal so BioVibe can log the nutritional content without me describing it. |
| US-06 | As a user, I want to send a photo of my workout screen so BioVibe can log my activity metrics automatically. |
| US-07 | As a user, I want BioVibe to tell me when I'm doing well so I feel motivated to keep going. |
| US-08 | As a user, I want BioVibe to estimate the calories of my meal automatically so I don't have to look them up myself. |
| US-09 | As a user, I want to discover BioVibe through a website in my language and start chatting in one tap. |
| US-10 | As a user, I want to set up my profile (name, diet, goals) once and have BioVibe remember it forever. |
| US-11 | As a user, I want to see my saved profile at any time by tapping a button — without having to ask. |
| US-12 | As a user, I want quick-reply buttons after every interaction so I can log my next habit without typing. |

---

## 8. Demo Script (Success Metrics)

1. **Landing Page → WhatsApp in one tap** — Open the site in PT/ES/EN, tap the button, show the hero image and welcome message arriving in the correct language with the profile setup button.
2. **Profile Setup** — Tap "Set up my profile", tell BioVibe your name and a dietary restriction. Tap the button again and see the saved profile displayed back.
3. **Zero-UI Magic** — Record a messy voice note about lunch → show the structured JSON in the terminal log + calorie estimate in the WhatsApp reply.
4. **Quick-log buttons** — After the voice note reply, tap "🏃 Just exercised" and show how the bot opens a conversational flow for the workout details.
5. **Memory Demonstration** — Mention a symptom → bot recalls a relevant meal from the history as a potential cause.
6. **Speed** — End-to-end response time under **3 seconds** using Gemini Flash.

---

## 9. Out of Scope (Future Iterations)

- Apple Health / Google Fit integration
- Subscription / payment gateways
- Production WhatsApp Business account onboarding
- Daily/weekly proactive digest (scheduled push messages)
- Health Score (0–100 numeric index based on recent logs)
- PDF/report export ("send me my weekly report")

---

## 10. Open Questions

- [ ] Should the JSON Brain file be encrypted at rest for the demo?
- [ ] What is the maximum audio file size Kapso forwards via webhook?
- [x] Should the `health_summary` regeneration be triggered by message count or a time window? → **Decided: every 5 log entries** (`len(log_history) % 5 == 0`)
