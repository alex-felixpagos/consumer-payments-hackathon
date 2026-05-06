# 06 – Profile Update Unit Tests Prompt

Adds unit tests for the profile update feature. Tests are split between `tests/test_brain.py` (new `update_profile` function) and `tests/test_bot.py` (new `profile_update` intent routing).

**Pre-conditions:**
- `app/services/brain.py` with `update_profile` must exist (from prompt 05)
- `app/bot.py` with `profile_update` routing must exist (from prompt 05)
- `tests/test_brain.py` and `tests/test_bot.py` must exist (from prompts 03 and 04)

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md`, `@app/services/brain.py`, `@app/bot.py`, `@tests/test_brain.py`, and `@tests/test_bot.py`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer adding unit tests for the profile update feature
in BioVibe. Use @docs/00-context-prompt.md as your technical reference.
Read @app/services/brain.py, @app/bot.py, @tests/test_brain.py, and @tests/test_bot.py
before writing any test — append to the existing files, do not recreate them.

YOUR TASK
---------
Add tests to two existing files:
  tests/test_brain.py       — 5 new tests for update_profile
  tests/test_bot.py         — 2 new tests for the profile_update intent routing

Use the same fixtures and helpers already defined in each file (brain_dir, empty_brain, etc.).

--- PART 1: append to tests/test_brain.py ---

1. test_update_profile_sets_name
   - Call update_profile(user_id, name="Rodrigo", traits=[])
   - Load brain and assert profile["name"] == "Rodrigo"

2. test_update_profile_appends_traits
   - Call update_profile(user_id, name=None, traits=["Lactose Intolerant"])
   - Load brain and assert "Lactose Intolerant" in profile["traits"]

3. test_update_profile_deduplicates_traits_case_insensitive
   - Call update_profile twice: traits=["Vegetarian"] then traits=["vegetarian"]
   - Load brain and assert the trait appears exactly once in profile["traits"]

4. test_update_profile_does_not_overwrite_name_with_none
   - Set profile["name"] = "Rodrigo" via a first update_profile call
   - Call update_profile(user_id, name=None, traits=[])
   - Assert profile["name"] is still "Rodrigo"

5. test_update_profile_does_not_affect_log_history
   - Append one log entry via append_log
   - Call update_profile(user_id, name="Rodrigo", traits=["Vegetarian"])
   - Load brain and assert len(log_history) == 1

--- PART 2: append to tests/test_bot.py ---

6. test_handle_inbound_profile_update_saves_profile
   - Mock Gemini to return:
       intent="profile_update"
       profile_update={"name": "Rodrigo", "traits": ["Lactose Intolerant"]}
       reply="Got it, Rodrigo! I'll remember you're lactose intolerant."
   - Assert update_profile was called once with name="Rodrigo"
     and traits=["Lactose Intolerant"]
   - Assert append_log was NOT called
   - Assert send_whatsapp_message was called with the reply string

7. test_handle_inbound_profile_update_does_not_trigger_summary_refresh
   - Mock Gemini to return intent="profile_update"
   - Assert append_log was NOT called
   - Assert should_refresh_summary was NOT called
   - Assert update_summary was NOT called

ACCEPTANCE CHECK
----------------
Run only the new tests first to confirm they pass in isolation:
  pytest tests/test_brain.py -k "profile" -v
  pytest tests/test_bot.py -k "profile" -v

Then run the full suite to confirm nothing was broken:
  pytest -v
```
