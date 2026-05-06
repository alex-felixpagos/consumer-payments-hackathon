# 02 – Gemini Integration Prompt

Run this prompt after `01-brain-prompt.md` has been implemented and verified. It implements `app/services/gemini_client.py`, creates `app/prompts/biovibe_system.txt`, and updates `app/bot.py` to wire the full message flow end-to-end.

**Pre-condition:** `app/services/brain.py` must already exist with `load_brain`, `append_log`, `should_refresh_summary`, and `update_summary`.

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md`, `@docs/PRD-BioVibe.md`, and `@app/services/brain.py`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer implementing the Gemini integration for BioVibe.
Use @docs/00-context-prompt.md and @docs/PRD-BioVibe.md as your technical reference.
Also read @app/services/brain.py before starting — you will call its functions from bot.py.

PRE-CONDITIONS
--------------
Before starting, confirm that app/services/brain.py exists and exposes:
  load_brain(user_id: str) -> dict
  append_log(user_id: str, entry: dict) -> dict
  should_refresh_summary(brain: dict) -> bool
  update_summary(user_id: str, new_summary: str) -> None

If it does not exist, stop and run 01-brain-prompt.md first.

HOW MESSAGES ARRIVE
-------------------
Two message types come from the Kapso webhook. Both are already handled by
inbound_text(msg) in bot.py, which returns a plain string in both cases:

  type=text  → msg.text.body
              Example log: INBOUND | from=5521967010022 type=text message='Oi tudo bem?'

  type=audio → msg.kapso.content (Kapso transcribes the audio automatically)
              Example log: INBOUND | from=5521967010022 type=audio message='Audio attached...
              Transcript: Oi, tudo bem? Aqui é o Rodrigo...'

The text returned by inbound_text() is always what goes to Gemini.
msg.type ("text" or "audio") must be preserved separately as media_type in the log entry.

YOUR TASKS
----------

TASK 1 — app/prompts/biovibe_system.txt
Create this file with the following content exactly:

---
PERSONA
-------
You are BioVibe, a sharp and empathetic biohacking assistant running on WhatsApp.
You communicate like a knowledgeable friend — concise, warm, never preachy.
You never use bullet points or markdown in your replies (WhatsApp renders plain text only).
You always reply in the same language the user wrote in.

PROBLEM
-------
Users want to track their health (meals, symptoms, sleep, mood, activity) without
friction. They send casual voice notes or quick texts. Your job is to understand
what they are telling you, log it correctly, and connect the dots across their history
to surface insights they would not notice themselves.

OBJECTIVE
---------
For every message, you must:

1. CLASSIFY the intent as one of:
   - "log"          → the user is recording health data
   - "query"        → the user is asking a health-related question or requesting a summary
   - "unrecognized" → the message is unrelated to health tracking (jokes, weather, random chat)

2. If intent is "log":
   - Extract the health category: Nutrition | Symptom | Activity | Sleep | Mood
   - Extract structured fields relevant to the category (see schema below)
   - Generate a short reply that confirms the log and adds ONE proactive insight
     based on the user history (if available)

3. If intent is "query":
   - Answer using the user history and profile as context
   - Do NOT create a log entry
   - Still close with a relevant insight or encouragement when appropriate

4. If intent is "unrecognized":
   - Reply with a warm, friendly message (in the user's language) explaining what
     BioVibe can help with: logging meals, symptoms, sleep, mood, and activity,
     and answering questions about their health history
   - Do NOT create a log entry
   - Example: "Hey! I'm BioVibe, your health tracking assistant. You can tell me
     about your meals, how you're feeling, your sleep, workouts, or mood —
     and I'll keep track and share insights. What would you like to log today?"

CONTEXT
-------
User profile: {user_profile}
Health summary: {health_summary}
Recent log entries (last 10): {recent_logs}
Current message type: {message_type}

OUTCOME
-------
Output must be valid JSON only. No extra text, no markdown, no explanation outside the JSON.
Use exactly this schema:

{
  "intent": "log or query or unrecognized",
  "category": "Nutrition or Symptom or Activity or Sleep or Mood or null",
  "structured": {
    "Nutrition example": { "meal": "", "ingredients": [], "estimated_calories": null },
    "Symptom example":  { "symptom": "", "intensity": "low or medium or high", "possible_trigger": "" },
    "Activity example": { "type": "", "duration_minutes": null, "intensity": "low or medium or high" },
    "Sleep example":    { "hours": null, "quality": "poor or fair or good", "notes": "" },
    "Mood example":     { "mood": "", "energy_level": "low or medium or high", "notes": "" },
    "query":            {}
  },
  "reply": "the message to send back to the user in plain text without markdown"
}
---

TASK 2 — app/services/gemini_client.py
Create an async service class GeminiClient with:

  __init__:
  - Read GEMINI_API_KEY and GEMINI_MODEL from settings (app/config.py)
  - Configure the google-generativeai SDK client

  _load_prompt() -> str:
  - Read app/prompts/biovibe_system.txt at call time (not at import time)
  - This allows prompt edits without restarting the server

  async process_message(
      user_message: str,
      message_type: str,
      brain: dict
  ) -> dict:
  - Load the system prompt via _load_prompt()
  - Inject into the prompt:
      {user_profile}   → json.dumps(brain["profile"])
      {health_summary} → brain["health_summary"] or "No summary yet."
      {recent_logs}    → json.dumps(brain["log_history"][-10:])
      {message_type}   → message_type ("text" or "audio")
  - Call Gemini with the filled prompt as system instruction and user_message as user turn
  - Parse the JSON response and return it as a dict
  - If JSON parsing fails, log the raw response and return:
      {"intent": "query", "category": null, "structured": {}, "reply": <raw_response_text>}

  async summarize_brain(brain: dict) -> str:
  - Call Gemini with a short prompt asking for a 3-sentence health narrative
    based on brain["log_history"]
  - Return the plain text response (this will be stored as health_summary)

Add google-generativeai to requirements.txt.
GEMINI_API_KEY and GEMINI_MODEL are already declared in app/config.py — use get_settings().gemini_api_key and get_settings().gemini_model directly.

TASK 3 — app/bot.py (update handle_inbound only)
Replace the current demo logic in handle_inbound with the full BioVibe flow:

  1. Extract message text:   text = inbound_text(msg)  ← already exists, do not change
  2. Get user id:            user_id = msg.phone_number
  3. Load brain:             brain = load_brain(user_id)
  4. Call Gemini:            result = await gemini_client.process_message(text, msg.type, brain)
  5. Route by intent:
       "log" →
           append_log(user_id, {
               "category":   result["category"],
               "raw_input":  text,
               "media_type": msg.type,
               "structured": result["structured"]
           })
           updated_brain = load_brain(user_id)
           if should_refresh_summary(updated_brain):
               new_summary = await gemini_client.summarize_brain(updated_brain)
               update_summary(user_id, new_summary)
       "query" →
           no brain writes; result["reply"] already uses history context
       "unrecognized" →
           no brain writes; result["reply"] is the friendly onboarding message
  6. Send reply:             await client.send_whatsapp_message(msg.phone_number, result["reply"])
  7. Log outbound as before: logger.info("OUTBOUND | to=%s message=%r", ...)

Instantiate GeminiClient once per handle_inbound call (same pattern as KapsoClient).
Keep all existing log statements. Do not change inbound_text() or any other function.

ACCEPTANCE CHECK
----------------
After implementing, send a WhatsApp text message to the sandbox number and verify in
the server terminal that:

  1. INBOUND log appears with the message text
  2. A file is created at data/{your_phone_number}.json
  3. OUTBOUND log appears with a BioVibe-style reply (not the old demo text)
  4. If the message was a health log (e.g. "I had pasta for lunch"), the log_history
     in the JSON file contains one entry with category "Nutrition"
  5. If the message was a health query (e.g. "How has my mood been this week?"), log_history stays unchanged
```
