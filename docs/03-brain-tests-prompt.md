# 03 – Brain Unit Tests Prompt

Implements `tests/test_brain.py`. Run this after `01-brain-prompt.md` is complete and verified. These tests have no external dependencies — no network, no Gemini, no Kapso — and should pass immediately after `brain.py` is implemented.

**Pre-condition:** `app/services/brain.py` must already exist.

---

## How to use this prompt

1. Open a new Cursor Agent session
2. Add to context: `@docs/00-context-prompt.md` and `@app/services/brain.py`
3. Paste the prompt below

---

## Prompt

```
You are a senior software engineer writing unit tests for the BioVibe brain service.
Use @docs/00-context-prompt.md as your technical reference and read @app/services/brain.py
before writing any test.

YOUR TASK
---------
Create tests/test_brain.py with full unit test coverage for app/services/brain.py.

The project uses pytest. Run tests with:
  source .venv/bin/activate && pytest tests/test_brain.py -v

IMPORTANT: all tests must use a temporary directory (tmp_path pytest fixture) for file
operations — never write to the real data/ directory during tests.

To redirect the data/ path to tmp_path, monkeypatch the DATA_DIR constant or path
resolution inside brain.py. Check how brain.py resolves the data directory and
patch accordingly.

TESTS TO IMPLEMENT
------------------

1. test_load_brain_new_user
   - Call load_brain("test_123") with no existing file
   - Assert the returned dict has keys: user_id, profile, health_summary, log_history
   - Assert profile = {"name": null, "traits": []}
   - Assert log_history = []
   - Assert the file was created on disk

2. test_load_brain_existing_user
   - Write a valid brain JSON to tmp_path manually
   - Call load_brain with that user_id
   - Assert the returned values match what was written

3. test_load_brain_corrupted_file
   - Write invalid JSON to the user file
   - Call load_brain — must NOT raise
   - Assert returns the default empty brain structure
   - Assert a warning was logged

4. test_save_brain
   - Call save_brain with a custom brain dict
   - Read the file from disk and assert contents match
   - Assert the file is valid JSON with indent=2

5. test_append_log_adds_entry
   - Call append_log with the four caller-provided fields:
     category, raw_input, media_type, structured
   - Assert log_history has exactly one entry
   - Assert the entry contains all four caller fields plus auto-generated id and timestamp

6. test_append_log_generates_uuid_and_timestamp
   - Call append_log twice
   - Assert each entry has a unique id
   - Assert timestamp is a valid ISO8601 UTC string

7. test_append_log_does_not_require_id_or_timestamp_from_caller
   - Call append_log passing only category, raw_input, media_type, structured
   - Assert no KeyError or TypeError is raised

8. test_should_refresh_summary_false_when_empty
   - Pass a brain with log_history = []
   - Assert returns False

9. test_should_refresh_summary_false_when_not_multiple_of_5
   - Pass a brain with 1, 2, 3, 4, 6, 7 entries
   - Assert returns False for all

10. test_should_refresh_summary_true_at_5
    - Pass a brain with exactly 5 entries
    - Assert returns True

11. test_should_refresh_summary_true_at_10
    - Pass a brain with exactly 10 entries
    - Assert returns True

12. test_update_summary
    - Call update_summary(user_id, "New summary text")
    - Load the brain and assert health_summary == "New summary text"

HELPERS
-------
Create a helper fixture brain_dir(tmp_path, monkeypatch) that patches the data
directory used by brain.py to point to tmp_path. Use this fixture in all tests
that touch the filesystem.

Do not import or mock anything from gemini_client — brain.py must be testable in
complete isolation.

ACCEPTANCE CHECK
----------------
All 12 tests must pass with:
  pytest tests/test_brain.py -v

No test should create files outside of tmp_path.
```
