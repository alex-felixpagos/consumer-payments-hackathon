# 01 – Brain Service Implementation Prompt

Implements `app/services/brain.py`, the persistent memory layer for BioVibe. This step has no external dependencies — it is pure file I/O and can be implemented and tested in isolation before any Gemini integration.

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md` and `@docs/PRD-BioVibe.md`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer implementing the persistent memory layer for BioVibe.
Use @docs/00-context-prompt.md and @docs/PRD-BioVibe.md as your technical reference.

YOUR TASK
---------
Create app/services/brain.py.

This module is the only place in the codebase that reads and writes user data.
It manages one JSON file per user at data/{user_id}.json, where user_id is the
user's phone number exactly as it arrives in msg.phone_number from the Kapso webhook
(e.g. "5521967010022" — no "+" prefix, no formatting).

FILE SCHEMA
-----------
Every user file must follow this exact structure:

{
  "user_id": "5521967010022",
  "profile": {
    "name": null,
    "traits": []
  },
  "health_summary": "",
  "log_history": []
}

Each entry in log_history follows this schema:

{
  "id": "<uuid4>",
  "timestamp": "<ISO8601 UTC>",
  "category": "Nutrition | Symptom | Activity | Sleep | Mood",
  "raw_input": "<original message text>",
  "media_type": "text | audio",
  "structured": {}
}

INTENT MODEL
------------
The Gemini integration (implemented in step 02) classifies every message into one of
three intents. brain.py must only be written to for "log" intent:

  "log"          → append to log_history (Nutrition, Symptom, Activity, Sleep, or Mood)
  "query"        → health-related question; read brain for context but do NOT append
  "unrecognized" → message is unrelated to health tracking; do NOT append anything

The bot.py orchestrator (step 02) is responsible for routing. brain.py does not decide
intent — it only receives explicit instructions to read or write.

FUNCTIONS TO IMPLEMENT
----------------------
Implement the following functions (all synchronous — file I/O is fast enough for the
hackathon scope and keeps the code simple):

1. load_brain(user_id: str) -> dict
   - If data/{user_id}.json does not exist, create data/ if needed, write and return
     the default empty brain structure shown above.
   - If the file exists, read and return its contents as a dict.

2. save_brain(user_id: str, brain: dict) -> None
   - Write brain to data/{user_id}.json with indent=2 and ensure_ascii=False.

3. append_log(user_id: str, entry: dict) -> dict
   - Load the brain, append entry to log_history, save, and return the updated brain.
   - The caller passes only: category, raw_input, media_type, structured.
   - This function generates id (uuid4) and timestamp (UTC ISO8601) internally before saving.

4. should_refresh_summary(brain: dict) -> bool
   - Return True if len(log_history) > 0 and len(log_history) % 5 == 0.
   - This is used by the caller to decide when to regenerate health_summary.

5. update_summary(user_id: str, new_summary: str) -> None
   - Load the brain, set health_summary = new_summary, save.

IMPORTANT DETAILS
-----------------
- The data/ directory is at the project root (same level as app/), not inside app/.
- Use pathlib.Path throughout — no os.path.
- Use json from the standard library — no third-party dependencies.
- If the JSON file is corrupted (json.JSONDecodeError), log a warning and return
  the default empty brain structure (do not raise — the bot must stay alive).
- Add a module-level logger: logger = logging.getLogger(__name__)

WHAT NOT TO DO
--------------
- Do not call Gemini from this module. brain.py is pure data — no LLM calls.
- Do not import anything from app.services.gemini_client.
- Do not implement async functions — keep everything synchronous.

ACCEPTANCE CHECK
----------------
After implementing, verify with:

  python -c "
  from app.services.brain import load_brain, append_log, should_refresh_summary
  brain = load_brain('test_user')
  print('New user brain:', brain)
  brain = append_log('test_user', {
      'category': 'Nutrition',
      'raw_input': 'Had pasta for lunch',
      'media_type': 'text',
      'structured': {'meal': 'pasta', 'ingredients': ['pasta']}
  })
  print('After append:', brain['log_history'])
  print('Should refresh:', should_refresh_summary(brain))
  "

Expected: a new file data/test_user.json is created, the log entry appears with an
auto-generated id and timestamp, and should_refresh_summary returns False (only 1 entry).
Delete data/test_user.json after verifying.
```
