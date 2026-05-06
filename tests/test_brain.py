"""Unit tests for app/services/brain.py — no network, no Gemini, no Kapso."""

import json
import logging

import pytest

import app.services.brain as brain_module
from app.services.brain import (
    append_log,
    load_brain,
    save_brain,
    should_refresh_summary,
    update_summary,
)


@pytest.fixture()
def brain_dir(tmp_path, monkeypatch):
    """Redirect brain.py's _DATA_DIR to a temporary directory for every test."""
    monkeypatch.setattr(brain_module, "_DATA_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# load_brain
# ---------------------------------------------------------------------------

def test_load_brain_new_user(brain_dir):
    brain = load_brain("test_123")

    assert set(brain.keys()) == {"user_id", "profile", "health_summary", "log_history"}
    assert brain["profile"] == {"name": None, "traits": []}
    assert brain["log_history"] == []
    assert (brain_dir / "test_123.json").exists()


def test_load_brain_existing_user(brain_dir):
    stored = {
        "user_id": "u1",
        "profile": {"name": "Alice", "traits": ["vegan"]},
        "health_summary": "Feeling good.",
        "log_history": [{"id": "abc", "category": "Mood"}],
    }
    (brain_dir / "u1.json").write_text(json.dumps(stored), encoding="utf-8")

    brain = load_brain("u1")

    assert brain["profile"]["name"] == "Alice"
    assert brain["health_summary"] == "Feeling good."
    assert len(brain["log_history"]) == 1


def test_load_brain_corrupted_file(brain_dir, caplog):
    (brain_dir / "bad.json").write_text("not valid json {{", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="app.services.brain"):
        brain = load_brain("bad")

    assert brain["log_history"] == []
    assert brain["profile"] == {"name": None, "traits": []}
    assert any("Corrupted" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# save_brain
# ---------------------------------------------------------------------------

def test_save_brain(brain_dir):
    custom = {
        "user_id": "u2",
        "profile": {"name": "Bob", "traits": []},
        "health_summary": "",
        "log_history": [],
    }
    save_brain("u2", custom)

    raw = (brain_dir / "u2.json").read_text(encoding="utf-8")
    loaded = json.loads(raw)
    assert loaded == custom
    assert "  " in raw  # indent=2 check


# ---------------------------------------------------------------------------
# append_log
# ---------------------------------------------------------------------------

def test_append_log_adds_entry(brain_dir):
    brain = append_log("u3", {
        "category": "Nutrition",
        "raw_input": "Had oatmeal",
        "media_type": "text",
        "structured": {"meal": "oatmeal"},
    })

    assert len(brain["log_history"]) == 1
    entry = brain["log_history"][0]
    assert entry["category"] == "Nutrition"
    assert entry["raw_input"] == "Had oatmeal"
    assert entry["media_type"] == "text"
    assert entry["structured"] == {"meal": "oatmeal"}
    assert "id" in entry
    assert "timestamp" in entry


def test_append_log_generates_uuid_and_timestamp(brain_dir):
    append_log("u4", {"category": "Sleep", "raw_input": "8h", "media_type": "text", "structured": {}})
    brain = append_log("u4", {"category": "Mood", "raw_input": "Happy", "media_type": "text", "structured": {}})

    ids = [e["id"] for e in brain["log_history"]]
    assert len(set(ids)) == 2

    for entry in brain["log_history"]:
        ts = entry["timestamp"]
        assert "T" in ts
        assert ts.endswith("+00:00") or ts.endswith("Z")


def test_append_log_does_not_require_id_or_timestamp_from_caller(brain_dir):
    brain = append_log("u5", {
        "category": "Activity",
        "raw_input": "Ran 5km",
        "media_type": "text",
        "structured": {},
    })
    assert len(brain["log_history"]) == 1


# ---------------------------------------------------------------------------
# should_refresh_summary
# ---------------------------------------------------------------------------

def _brain_with_n_entries(n: int) -> dict:
    return {
        "user_id": "x",
        "profile": {"name": None, "traits": []},
        "health_summary": "",
        "log_history": [{"id": str(i)} for i in range(n)],
    }


def test_should_refresh_summary_false_when_empty():
    assert should_refresh_summary(_brain_with_n_entries(0)) is False


@pytest.mark.parametrize("n", [1, 2, 3, 4, 6, 7])
def test_should_refresh_summary_false_when_not_multiple_of_5(n):
    assert should_refresh_summary(_brain_with_n_entries(n)) is False


def test_should_refresh_summary_true_at_5():
    assert should_refresh_summary(_brain_with_n_entries(5)) is True


def test_should_refresh_summary_true_at_10():
    assert should_refresh_summary(_brain_with_n_entries(10)) is True


# ---------------------------------------------------------------------------
# update_summary
# ---------------------------------------------------------------------------

def test_update_summary(brain_dir):
    load_brain("u6")  # create the file
    update_summary("u6", "New summary text")

    brain = load_brain("u6")
    assert brain["health_summary"] == "New summary text"
