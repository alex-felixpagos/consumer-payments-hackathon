"""Tests for the payment-link bot logic."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import handle_agent_inbound, handle_inbound
from app.payments import store as payment_store
from app.schemas.kapso.message import KapsoMessage


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


@pytest.mark.asyncio
async def test_pay_command_creates_payment_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(payment_store, "_PAYMENTS_FILE", tmp_path / "payments.json")
    msg = _build_text_msg("pay 50")
    client = AsyncMock()

    settings = SimpleNamespace(
        stripe_currency="usd",
        public_payment_base_url="https://pay.example",
    )
    with patch("app.bot.get_settings", return_value=settings):
        await handle_inbound(msg, client)

    client.send_whatsapp_message.assert_awaited_once()
    body = client.send_whatsapp_message.await_args.args[1]
    assert "$50.00 USD" in body
    assert "https://pay.example/pay/pay_" in body
    client.send_flow_message.assert_not_awaited()

    payments = payment_store.list_payments()
    assert len(payments) == 1
    assert payments[0].amount_cents == 5000
    assert payments[0].status == "pending"
    assert payments[0].payment_url.startswith("https://pay.example/pay/pay_")


@pytest.mark.asyncio
async def test_agent_webhook_pay_command_creates_payment_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(payment_store, "_PAYMENTS_FILE", tmp_path / "payments.json")
    msg = _build_text_msg("pay 1")
    client = AsyncMock()

    settings = SimpleNamespace(
        stripe_currency="usd",
        public_payment_base_url="https://pay.example",
    )
    with patch("app.bot.get_settings", return_value=settings):
        await handle_agent_inbound("hackaton-movie-agent", msg, client)

    client.send_whatsapp_message.assert_awaited_once()
    body = client.send_whatsapp_message.await_args.args[1]
    assert "$1.00 USD" in body
    assert "https://pay.example/pay/pay_" in body
    client.send_flow_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_text_for_unmatched_input() -> None:
    msg = _build_text_msg("hello")
    client = AsyncMock()
    await handle_inbound(msg, client)
    client.send_whatsapp_message.assert_awaited_once()
    body = client.send_whatsapp_message.await_args.args[1]
    assert "pay" in body.lower()


