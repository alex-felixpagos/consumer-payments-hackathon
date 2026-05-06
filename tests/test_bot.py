"""Unit tests for handle_inbound in bot.py — no real Gemini or Kapso calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import handle_inbound
from app.schemas.kapso.message import KapsoMessage, KapsoMessageMeta, KapsoTextContent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_text_message(phone: str = "5521999999999", body: str = "I had pasta for lunch") -> KapsoMessage:
    return KapsoMessage(
        id="msg1",
        type="text",
        timestamp="2026-01-01T00:00:00Z",
        **{"from": phone},
        kapso=KapsoMessageMeta(direction="inbound", status="received", processing_status="processed"),
        text=KapsoTextContent(body=body),
    )


def make_audio_message(phone: str = "5521999999999", transcript: str = "I ran 5km today") -> KapsoMessage:
    return KapsoMessage(
        id="msg2",
        type="audio",
        timestamp="2026-01-01T00:00:00Z",
        **{"from": phone},
        kapso=KapsoMessageMeta(
            direction="inbound",
            status="received",
            processing_status="processed",
            content=transcript,
        ),
    )


def _gemini_result(intent: str, category: str | None = None, reply: str = "ok", structured: dict | None = None):
    return {
        "intent": intent,
        "category": category,
        "structured": structured or {},
        "reply": reply,
    }


def _mock_kapso_client() -> MagicMock:
    client = MagicMock()
    client.send_whatsapp_message = AsyncMock()
    return client


EMPTY_BRAIN = {
    "user_id": "5521999999999",
    "profile": {"name": None, "traits": []},
    "health_summary": "",
    "log_history": [],
}

LOG_BRAIN = {**EMPTY_BRAIN, "log_history": [{"id": "x"}]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_handle_inbound_log_intent_saves_to_brain():
    msg = make_text_message()
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log", return_value=LOG_BRAIN) as mock_append,
        patch("app.bot.should_refresh_summary", return_value=False),
        patch("app.bot.update_summary"),
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(
            return_value=_gemini_result("log", category="Nutrition", reply="Logged!")
        )
        await handle_inbound(msg, kapso)

    mock_append.assert_called_once()
    call_kwargs = mock_append.call_args[0][1]
    assert call_kwargs["category"] == "Nutrition"
    assert call_kwargs["media_type"] == "text"
    kapso.send_whatsapp_message.assert_called_once_with(msg.phone_number, "Logged!")


@pytest.mark.anyio
async def test_handle_inbound_query_intent_does_not_write_brain():
    msg = make_text_message(body="How has my mood been?")
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log") as mock_append,
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(
            return_value=_gemini_result("query", reply="You slept 7h on average.")
        )
        await handle_inbound(msg, kapso)

    mock_append.assert_not_called()
    kapso.send_whatsapp_message.assert_called_once()


@pytest.mark.anyio
async def test_handle_inbound_unrecognized_does_not_write_brain():
    msg = make_text_message(body="What's the weather?")
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log") as mock_append,
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(
            return_value=_gemini_result("unrecognized", reply="Hey! I can help you track...")
        )
        await handle_inbound(msg, kapso)

    mock_append.assert_not_called()
    kapso.send_whatsapp_message.assert_called_once_with(
        msg.phone_number, "Hey! I can help you track..."
    )


@pytest.mark.anyio
async def test_handle_inbound_triggers_summary_refresh():
    msg = make_text_message()
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log", return_value=LOG_BRAIN),
        patch("app.bot.should_refresh_summary", return_value=True),
        patch("app.bot.update_summary") as mock_update,
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        mock_instance = MockGemini.return_value
        mock_instance.process_message = AsyncMock(
            return_value=_gemini_result("log", category="Sleep", reply="Logged!")
        )
        mock_instance.summarize_brain = AsyncMock(return_value="New summary.")
        await handle_inbound(msg, kapso)

    mock_update.assert_called_once_with(msg.phone_number, "New summary.")


@pytest.mark.anyio
async def test_handle_inbound_audio_message_preserves_media_type():
    msg = make_audio_message()
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log", return_value=LOG_BRAIN) as mock_append,
        patch("app.bot.should_refresh_summary", return_value=False),
        patch("app.bot.update_summary"),
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(
            return_value=_gemini_result("log", category="Activity", reply="Logged your run!")
        )
        await handle_inbound(msg, kapso)

    call_kwargs = mock_append.call_args[0][1]
    assert call_kwargs["media_type"] == "audio"


@pytest.mark.anyio
async def test_handle_inbound_gemini_failure_does_not_crash():
    msg = make_text_message()
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(
            side_effect=Exception("Gemini unavailable")
        )
        with pytest.raises(Exception, match="Gemini unavailable"):
            await handle_inbound(msg, kapso)


@pytest.mark.anyio
async def test_handle_inbound_profile_update_saves_profile():
    msg = make_text_message(body="My name is Rodrigo and I'm lactose intolerant")
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log") as mock_append,
        patch("app.bot.update_profile") as mock_update_profile,
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(return_value={
            "intent": "profile_update",
            "category": None,
            "structured": {},
            "profile_update": {"name": "Rodrigo", "traits": ["Lactose Intolerant"]},
            "reply": "Got it, Rodrigo! I'll remember you're lactose intolerant.",
        })
        await handle_inbound(msg, kapso)

    mock_update_profile.assert_called_once_with(
        msg.phone_number,
        name="Rodrigo",
        traits=["Lactose Intolerant"],
    )
    mock_append.assert_not_called()
    kapso.send_whatsapp_message.assert_called_once_with(
        msg.phone_number,
        "Got it, Rodrigo! I'll remember you're lactose intolerant.",
    )


@pytest.mark.anyio
async def test_handle_inbound_profile_update_does_not_trigger_summary_refresh():
    msg = make_text_message(body="I'm vegetarian")
    kapso = _mock_kapso_client()

    with (
        patch("app.bot.load_brain", return_value=EMPTY_BRAIN),
        patch("app.bot.append_log") as mock_append,
        patch("app.bot.should_refresh_summary") as mock_refresh,
        patch("app.bot.update_summary") as mock_update_summary,
        patch("app.bot.update_profile"),
        patch("app.bot.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value.process_message = AsyncMock(return_value={
            "intent": "profile_update",
            "category": None,
            "structured": {},
            "profile_update": {"name": None, "traits": ["Vegetarian"]},
            "reply": "Got it! I'll keep in mind you're vegetarian.",
        })
        await handle_inbound(msg, kapso)

    mock_append.assert_not_called()
    mock_refresh.assert_not_called()
    mock_update_summary.assert_not_called()
