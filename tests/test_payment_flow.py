"""Tests for the champeta payment flow bot logic."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import handle_inbound
from app.schemas.kapso.message import KapsoMessage
from app.schemas.kapso.nfm_reply import extract_nfm_reply
from app.services.stripe_service import ChargeResult


def _build_text_msg(body: str) -> KapsoMessage:
    return KapsoMessage.model_validate(
        {
            "id": "wamid.TEST",
            "type": "text",
            "timestamp": "1700000000",
            "from": "5215555555555",
            "kapso": {
                "direction": "inbound",
                "status": "received",
                "processing_status": "processed",
            },
            "text": {"body": body},
        }
    )


def _build_nfm_reply_msg(payload: dict) -> KapsoMessage:
    return KapsoMessage.model_validate(
        {
            "id": "wamid.NFM",
            "type": "interactive",
            "timestamp": "1700000000",
            "from": "5215555555555",
            "kapso": {
                "direction": "inbound",
                "status": "received",
                "processing_status": "processed",
                "flow_response": payload,
            },
            "interactive": {
                "type": "nfm_reply",
                "nfm_reply": {
                    "name": "flow",
                    "body": "Sent",
                    "response_json": json.dumps(payload),
                },
            },
        }
    )


@pytest.mark.asyncio
async def test_pay_command_triggers_flow_message(monkeypatch) -> None:
    monkeypatch.setenv("KAPSO_FLOW_ID", "1234567890")
    from app.config import get_settings

    get_settings.cache_clear()

    msg = _build_text_msg("pay 50")
    client = AsyncMock()

    await handle_inbound(msg, client)

    client.send_flow_message.assert_awaited_once()
    kwargs = client.send_flow_message.await_args.kwargs
    assert kwargs["flow_id"] == "1234567890"
    assert kwargs["initial_data"]["amount_cents"] == 5000
    assert "$50.00" in kwargs["flow_cta"]
    client.send_whatsapp_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_text_for_unmatched_input() -> None:
    msg = _build_text_msg("hello")
    client = AsyncMock()
    await handle_inbound(msg, client)
    client.send_whatsapp_message.assert_awaited_once()
    body = client.send_whatsapp_message.await_args.args[1]
    assert "pay" in body.lower()


@pytest.mark.asyncio
async def test_nfm_reply_charges_and_replies_success() -> None:
    payload = {
        "card_number": "4242424242424242",
        "expiration": "12/34",
        "cvv": "123",
        "amount_cents": 100,
    }
    msg = _build_nfm_reply_msg(payload)
    client = AsyncMock()

    fake_result = ChargeResult(success=True, payment_intent_id="pi_test_123", error_message=None)
    with patch("app.bot.charge_card", new=AsyncMock(return_value=fake_result)) as charge_mock:
        await handle_inbound(msg, client)

    charge_mock.assert_awaited_once()
    call_kwargs = charge_mock.await_args.kwargs
    assert call_kwargs["card_number"] == "4242424242424242"
    assert call_kwargs["amount_cents"] == 100

    body = client.send_whatsapp_message.await_args.args[1]
    assert "✅" in body
    assert "pi_test_123" in body


def test_extract_nfm_reply_from_response_json() -> None:
    payload = {
        "card_number": "4242424242424242",
        "expiration": "01/30",
        "cvv": "999",
        "amount_cents": 250,
    }
    msg = KapsoMessage.model_validate(
        {
            "id": "wamid.X",
            "type": "interactive",
            "timestamp": "1",
            "from": "1",
            "kapso": {"direction": "inbound", "status": "received", "processing_status": "processed"},
            "interactive": {
                "type": "nfm_reply",
                "nfm_reply": {"name": "flow", "body": "Sent", "response_json": json.dumps(payload)},
            },
        }
    )
    parsed = extract_nfm_reply(msg)
    assert parsed is not None
    assert parsed.card_number == "4242424242424242"
    assert parsed.expiration == "01/30"
    assert parsed.cvv == "999"
    assert parsed.amount_cents == 250
