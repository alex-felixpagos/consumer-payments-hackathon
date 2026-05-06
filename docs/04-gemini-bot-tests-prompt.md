# 04 – Gemini & Bot Unit Tests Prompt

Implements `tests/test_gemini_client.py` and `tests/test_bot.py`. Run this after `02-gemini-integration-prompt.md` is complete. These tests mock all external dependencies (Gemini SDK, Kapso API, file system) so no real network calls are made.

**Pre-conditions:**
- `app/services/brain.py` must exist (from prompt 01)
- `app/services/gemini_client.py` must exist (from prompt 02)
- `app/bot.py` must be updated with the full BioVibe flow (from prompt 02)

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md`, `@app/services/gemini_client.py`, `@app/bot.py`, and `@app/services/brain.py`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer writing unit tests for the BioVibe Gemini integration
and bot orchestration logic. Use @docs/00-context-prompt.md as your technical reference.
Read @app/services/gemini_client.py, @app/bot.py, and @app/services/brain.py before writing
any test.

YOUR TASK
---------
Create two test files:
  tests/test_gemini_client.py   — unit tests for GeminiClient
  tests/test_bot.py             — unit tests for handle_inbound in bot.py

Use unittest.mock (built-in) for all mocking. Do not make real calls to Gemini or Kapso.

Run tests with:
  source .venv/bin/activate && pytest tests/test_gemini_client.py tests/test_bot.py -v

--- PART 1: tests/test_gemini_client.py ---

Mock target: the google-generativeai SDK client used inside GeminiClient.
Also mock the file read in _load_prompt() to avoid depending on the actual
app/prompts/biovibe_system.txt file being present.

TESTS TO IMPLEMENT

1. test_process_message_log_intent
   - Mock Gemini to return valid JSON with intent="log", category="Nutrition",
     structured={"meal": "pasta"}, reply="Logged your lunch!"
   - Call process_message("I had pasta for lunch", "text", empty_brain())
   - Assert the returned dict has intent="log", category="Nutrition"
   - Assert reply is a non-empty string

2. test_process_message_query_intent
   - Mock Gemini to return JSON with intent="query", category=null,
     structured={}, reply="You slept well this week."
   - Assert returned dict has intent="query" and category is None

3. test_process_message_unrecognized_intent
   - Mock Gemini to return JSON with intent="unrecognized", category=null,
     structured={}, reply="Hey! I can help you track..."
   - Assert returned dict has intent="unrecognized"

4. test_process_message_json_parse_failure
   - Mock Gemini to return a non-JSON string (e.g. "Sorry, I can't help with that.")
   - Assert process_message does NOT raise
   - Assert returned dict has intent="query" and reply contains the raw response text

5. test_prompt_is_injected_with_brain_context
   - Capture the prompt string passed to Gemini
   - Assert it contains the user_profile, health_summary, and recent_logs values
     from the brain dict passed to process_message

6. test_summarize_brain_returns_string
   - Mock Gemini to return "User has been logging well."
   - Call summarize_brain(brain_with_logs())
   - Assert the return value is a non-empty string

Helper: empty_brain() returns the default brain dict structure (same as load_brain for a new user).
Helper: brain_with_logs() returns a brain with 5 Nutrition log entries.

--- PART 2: tests/test_bot.py ---

Mock targets: GeminiClient, brain functions (load_brain, append_log,
should_refresh_summary, update_summary), and KapsoClient.send_whatsapp_message.

Build a minimal fake KapsoMessage with the fields handle_inbound uses:
  phone_number, type, text, interactive, button, kapso

TESTS TO IMPLEMENT

7. test_handle_inbound_log_intent_saves_to_brain
   - Mock Gemini to return intent="log", category="Nutrition", structured={}, reply="Logged!"
   - Mock should_refresh_summary to return False
   - Call handle_inbound with a text message
   - Assert append_log was called once with the correct category and media_type="text"
   - Assert send_whatsapp_message was called with reply="Logged!"

8. test_handle_inbound_query_intent_does_not_write_brain
   - Mock Gemini to return intent="query", reply="You slept 7h on average."
   - Call handle_inbound with a text message
   - Assert append_log was NOT called
   - Assert send_whatsapp_message was called

9. test_handle_inbound_unrecognized_does_not_write_brain
   - Mock Gemini to return intent="unrecognized", reply="Hey! I can help you track..."
   - Assert append_log was NOT called
   - Assert send_whatsapp_message was called with the friendly reply

10. test_handle_inbound_triggers_summary_refresh
    - Mock Gemini to return intent="log"
    - Mock should_refresh_summary to return True
    - Mock summarize_brain to return "New summary."
    - Assert update_summary was called with "New summary."

11. test_handle_inbound_audio_message_preserves_media_type
    - Build a fake message with type="audio" and kapso.content="I ran 5km today"
    - Mock Gemini to return intent="log", category="Activity"
    - Assert append_log was called with media_type="audio"

12. test_handle_inbound_gemini_failure_does_not_crash
    - Mock GeminiClient.process_message to raise an Exception
    - Call handle_inbound — must NOT raise (webhooks.py already wraps in try/except,
      but verify handle_inbound itself is robust or that the exception propagates cleanly
      to the caller without crashing the process)

ACCEPTANCE CHECK
----------------
All tests must pass with:
  pytest tests/test_gemini_client.py tests/test_bot.py -v

No test should make real HTTP calls or write to the real data/ directory.
Run the full test suite at the end to confirm existing tests still pass:
  pytest -v
```
