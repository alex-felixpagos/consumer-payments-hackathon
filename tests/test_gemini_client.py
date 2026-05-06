"""Unit tests for GeminiClient — no real Gemini calls."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gemini_client import GeminiClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def empty_brain() -> dict:
    return {
        "user_id": "test",
        "profile": {"name": None, "traits": []},
        "health_summary": "",
        "log_history": [],
    }


def brain_with_logs() -> dict:
    entries = [
        {
            "id": str(i),
            "timestamp": "2026-01-01T00:00:00+00:00",
            "category": "Nutrition",
            "raw_input": f"meal {i}",
            "media_type": "text",
            "structured": {},
        }
        for i in range(5)
    ]
    return {
        "user_id": "test",
        "profile": {"name": None, "traits": []},
        "health_summary": "",
        "log_history": entries,
    }


def _make_client_with_mock(response_text: str):
    """Return a GeminiClient whose internal SDK client is fully mocked."""
    mock_response = MagicMock()
    mock_response.text = response_text

    mock_aio = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)

    mock_sdk_client = MagicMock()
    mock_sdk_client.aio = mock_aio

    with patch("app.services.gemini_client.genai.Client", return_value=mock_sdk_client):
        client = GeminiClient()

    # Keep the mock accessible for assertions
    client._mock_aio = mock_aio
    return client


SYSTEM_PROMPT_TEMPLATE = (
    "User profile: {user_profile}\n"
    "Health summary: {health_summary}\n"
    "Recent log entries (last 10): {recent_logs}\n"
    "Current message type: {message_type}"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_process_message_log_intent():
    payload = json.dumps({
        "intent": "log",
        "category": "Nutrition",
        "structured": {"meal": "pasta"},
        "reply": "Logged your lunch!",
    })
    client = _make_client_with_mock(payload)

    with patch.object(client, "_load_prompt", return_value=SYSTEM_PROMPT_TEMPLATE):
        result = await client.process_message("I had pasta for lunch", "text", empty_brain())

    assert result["intent"] == "log"
    assert result["category"] == "Nutrition"
    assert result["reply"]


@pytest.mark.anyio
async def test_process_message_query_intent():
    payload = json.dumps({
        "intent": "query",
        "category": None,
        "structured": {},
        "reply": "You slept well this week.",
    })
    client = _make_client_with_mock(payload)

    with patch.object(client, "_load_prompt", return_value=SYSTEM_PROMPT_TEMPLATE):
        result = await client.process_message("How was my sleep?", "text", empty_brain())

    assert result["intent"] == "query"
    assert result["category"] is None


@pytest.mark.anyio
async def test_process_message_unrecognized_intent():
    payload = json.dumps({
        "intent": "unrecognized",
        "category": None,
        "structured": {},
        "reply": "Hey! I can help you track your health.",
    })
    client = _make_client_with_mock(payload)

    with patch.object(client, "_load_prompt", return_value=SYSTEM_PROMPT_TEMPLATE):
        result = await client.process_message("What's the weather?", "text", empty_brain())

    assert result["intent"] == "unrecognized"


@pytest.mark.anyio
async def test_process_message_json_parse_failure():
    client = _make_client_with_mock("Sorry, I can't help with that.")

    with patch.object(client, "_load_prompt", return_value=SYSTEM_PROMPT_TEMPLATE):
        result = await client.process_message("random text", "text", empty_brain())

    assert result["intent"] == "query"
    assert "Sorry" in result["reply"]


@pytest.mark.anyio
async def test_prompt_is_injected_with_brain_context():
    payload = json.dumps({"intent": "query", "category": None, "structured": {}, "reply": "ok"})
    brain = {
        "user_id": "u1",
        "profile": {"name": "Alice", "traits": ["vegan"]},
        "health_summary": "Feeling energetic.",
        "log_history": [],
    }

    mock_response = MagicMock()
    mock_response.text = payload
    mock_aio = MagicMock()
    mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
    mock_sdk_client = MagicMock()
    mock_sdk_client.aio = mock_aio

    captured_config = {}

    async def capture_call(**kwargs):
        captured_config.update(kwargs)
        return mock_response

    mock_aio.models.generate_content = capture_call

    with patch("app.services.gemini_client.genai.Client", return_value=mock_sdk_client):
        client = GeminiClient()

    template = (
        "profile:{user_profile} summary:{health_summary} "
        "logs:{recent_logs} type:{message_type}"
    )
    with patch.object(client, "_load_prompt", return_value=template):
        await client.process_message("hello", "text", brain)

    config = captured_config.get("config")
    system_instruction = config.system_instruction
    assert "Alice" in system_instruction
    assert "Feeling energetic." in system_instruction
    assert "text" in system_instruction


@pytest.mark.anyio
async def test_summarize_brain_returns_string():
    client = _make_client_with_mock("User has been logging well.")

    result = await client.summarize_brain(brain_with_logs())

    assert isinstance(result, str)
    assert len(result) > 0
