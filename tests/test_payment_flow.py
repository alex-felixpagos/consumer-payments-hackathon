"""Tests for the payment-link bot logic."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import handle_agent_inbound, handle_inbound
from app.payments import store as payment_store
from app.schemas.kapso.message import KapsoMessage
from app.schemas.kapso.nfm_reply import extract_nfm_reply
from app.services import booking_store, showtime_selection_store


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


def _build_button_msg(button_id: str, title: str = "7:05 PM IMAX") -> KapsoMessage:
    return KapsoMessage.model_validate(
        {
            "id": f"wamid.BUTTON.{button_id}",
            "type": "interactive",
            "timestamp": "1700000000",
            "from": "5215555555555",
            "kapso": {
                "direction": "inbound",
                "status": "received",
                "processing_status": "processed",
            },
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": button_id, "title": title},
            },
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
        ticket_default_amount_cents=100,
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
        ticket_default_amount_cents=100,
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


@pytest.mark.asyncio
async def test_showtime_selection_creates_payment_link_and_pending_booking(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        showtime_selection_store, "_SELECTIONS_FILE", tmp_path / "showtime_selections.json"
    )
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    monkeypatch.setattr(payment_store, "_PAYMENTS_FILE", tmp_path / "payments.json")

    settings = SimpleNamespace(
        stripe_currency="usd",
        public_payment_base_url="https://pay.example",
        ticket_default_amount_cents=100,
    )
    with patch("app.services.showtime_selection_store.get_settings", return_value=settings):
        selections = showtime_selection_store.save_showtime_options(
            "+5215555555555",
            [
                {
                    "movie_title": "Dune: Part Two",
                    "theater_name": "Cine Colombia Andino",
                    "theater_address": "Cra. 11 #82-71, Bogota",
                    "start_time": "2026-05-06T19:05:00",
                    "display_time": "7:05 PM",
                    "format": "IMAX",
                }
            ],
        )
    msg = _build_button_msg(f"showtime:{selections[0].selection_id}")
    client = AsyncMock()

    with patch("app.bot.get_settings", return_value=settings):
        await handle_inbound(msg, client)

    client.send_whatsapp_message.assert_awaited_once()
    body = client.send_whatsapp_message.await_args.args[1]
    assert "https://pay.example/pay/pay_" in body
    assert "Dune: Part Two" in body
    client.send_flow_message.assert_not_awaited()

    payments = payment_store.list_payments()
    assert len(payments) == 1
    assert payments[0].amount_cents == 100

    bookings = booking_store.list_bookings()
    assert len(bookings) == 1
    assert bookings[0].status == "pending_payment"
    assert bookings[0].ticket.movie_title == "Dune: Part Two"
    assert bookings[0].stripe_id == payments[0].id


@pytest.mark.asyncio
async def test_agent_showtime_results_send_selection_buttons(monkeypatch) -> None:
    msg = _build_text_msg("show me dune tonight")
    msg.id = "wamid.AGENT.SHOWTIMES"
    client = AsyncMock()
    agent = SimpleNamespace(id="agent_123", name="hackaton-movie-agent")
    result = {
        "response": "I found a good option.",
        "showtime_results": [
            {
                "movie_title": "Dune: Part Two",
                "theater_name": "Cine Colombia Andino",
                "start_time": "2026-05-06T19:05:00",
                "display_time": "7:05 PM",
                "format": "IMAX",
            }
        ],
    }

    with (
        patch("app.bot.get_agent_by_name", return_value=agent),
        patch("app.bot.run_agent_turn", new=AsyncMock(return_value=result)),
        patch("app.bot.showtime_selection_store.save_showtime_options") as save_options,
    ):
        save_options.return_value = [
            SimpleNamespace(selection_id="sel_test", title="7:05 PM IMAX")
        ]
        await handle_agent_inbound("hackaton-movie-agent", msg, client)

    client.send_whatsapp_message.assert_awaited_once()
    client.send_interactive_buttons.assert_awaited_once()
    kwargs = client.send_interactive_buttons.await_args.kwargs
    assert kwargs["buttons"][0]["id"] == "showtime:sel_test"


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
