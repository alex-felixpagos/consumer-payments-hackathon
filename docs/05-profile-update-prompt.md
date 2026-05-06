# 05 – Profile Update Prompt

Implements the profile update feature: when a user shares persistent information about themselves ("I'm lactose intolerant", "My name is Rodrigo", "I'm vegetarian"), BioVibe saves it to their profile instead of logging it as a health entry.

**Pre-conditions:**
- `app/services/brain.py` must exist (from prompt 01)
- `app/services/gemini_client.py` must exist (from prompt 02)
- `app/bot.py` must have the full BioVibe flow (from prompt 02)

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md`, `@app/services/brain.py`, `@app/services/gemini_client.py`, and `@app/bot.py`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer adding the profile update feature to BioVibe.
Use @docs/00-context-prompt.md as your technical reference.
Read @app/services/brain.py, @app/services/gemini_client.py, and @app/bot.py
before making any changes.

CONTEXT
-------
The current intent model has three intents: log, query, unrecognized.
We are adding a fourth: profile_update.

A profile_update occurs when the user shares persistent personal information that
should be remembered across all future conversations — not logged as a health event.

Examples:
  "I'm lactose intolerant"        → add "Lactose Intolerant" to profile.traits
  "My name is Rodrigo"            → set profile.name = "Rodrigo"
  "I'm vegetarian"                → add "Vegetarian" to profile.traits
  "I do intermittent fasting"     → add "Intermittent Faster" to profile.traits
  "I had a headache this morning" → this is a LOG, not a profile update

The user's profile is stored in data/{user_id}.json under the "profile" key:
  {
    "name": null,
    "traits": []
  }

YOUR TASKS
----------

TASK 1 — app/services/brain.py (add one function)
Add the following function without changing any existing function:

  update_profile(user_id: str, name: str | None, traits: list[str]) -> dict:
  - Load the brain
  - If name is not None and not empty, set profile["name"] = name
  - For each trait in traits: if it is not already in profile["traits"], append it
    (case-insensitive deduplication — "Vegetarian" and "vegetarian" are the same)
  - Save the brain and return the updated brain

TASK 2 — app/prompts/biovibe_system.txt (add the new intent)
In the OBJECTIVE section, add a fourth classification option and its handling rule.
Insert after the "unrecognized" rule:

  5. If intent is "profile_update":
     - The user is sharing persistent personal information (name, dietary restrictions,
       health conditions, lifestyle traits)
     - Do NOT create a log entry
     - Extract: name (string or null) and traits (list of strings, normalized to title case)
     - Reply warmly confirming what was saved, and mention it will be remembered
       Example: "Got it, Rodrigo! I'll remember you're lactose intolerant and factor
       that into my insights from now on."

Update the OUTCOME JSON schema to include the profile_update case:

  {
    "intent": "log or query or unrecognized or profile_update",
    "category": "Nutrition or Symptom or Activity or Sleep or Mood or null",
    "structured": { ... same as before ... },
    "profile_update": {
      "name": "string or null",
      "traits": ["string"]
    },
    "reply": "..."
  }

For intents other than profile_update, profile_update must be:
  "profile_update": {"name": null, "traits": []}

TASK 3 — app/bot.py (add one routing branch)
In handle_inbound, add the profile_update branch after the unrecognized branch:

  "profile_update" →
      update_profile(
          user_id,
          name=result.get("profile_update", {}).get("name"),
          traits=result.get("profile_update", {}).get("traits", [])
      )
      # then send reply as usual

Do not change any existing branch. Do not change inbound_text() or any other function.

WHAT NOT TO DO
--------------
- Do not change the existing log, query, or unrecognized behavior
- Do not add profile_update entries to log_history
- Do not change the brain file schema — profile already exists in the schema

ACCEPTANCE CHECK
----------------
After implementing, test manually via WhatsApp:

  1. Send: "My name is [your name] and I'm lactose intolerant"
     → Bot replies confirming name and trait
     → data/{user_id}.json shows profile.name and "Lactose Intolerant" in traits

  2. Send: "I had pasta for lunch"
     → Bot logs it as Nutrition (profile_update branch was NOT triggered)
     → log_history has one entry, profile.traits unchanged

  3. Send: "I'm lactose intolerant" again
     → Trait is NOT duplicated in profile.traits (deduplication works)
```
