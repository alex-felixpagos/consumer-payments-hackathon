from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.services import booking_store, ticket_delivery


def _ticket_payload() -> dict:
    return {
        "movie_title": "Dune: Part Two",
        "theater_name": "Cine Colombia Andino",
        "theater_address": "Cra. 11 #82-71, Bogota",
        "start_time": "2026-05-06T19:05:00",
        "display_time": "7:05 PM",
        "format": "IMAX",
        "amount_cents": 4500000,
        "currency": "cop",
    }


def test_create_pending_booking_api_persists_stripe_mapping(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    client = TestClient(app)

    response = client.post(
        "/api/bookings/pending",
        json={
            "stripe_id": "pi_test_api",
            "phone_number": "+573001112233",
            "ticket": _ticket_payload(),
            "booking_id": "book_api",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["booking_id"] == "book_api"
    assert data["stripe_id"] == "pi_test_api"
    assert data["payment_intent_id"] == "pi_test_api"
    assert data["phone_number"] == "573001112233"

    stored = booking_store.get_by_stripe_id("pi_test_api")
    assert stored is not None
    assert stored.ticket.movie_title == "Dune: Part Two"


def test_stripe_webhook_sends_ticket_and_marks_booking_sent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    send_ticket = AsyncMock(
        return_value={
            "media_url": "https://agripina-unblamed-mickey.ngrok-free.dev/media/tickets/book_webhook.png",
            "seats": ["E8"],
        }
    )
    monkeypatch.setattr(ticket_delivery, "send_movie_ticket", send_ticket)
    client = TestClient(app)

    create_response = client.post(
        "/api/bookings/pending",
        json={
            "stripe_id": "pi_test_webhook",
            "phone_number": "+573001112233",
            "ticket": _ticket_payload(),
            "booking_id": "book_webhook",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.post(
        "/webhooks/stripe",
        json={"stripe_id": "pi_test_webhook"},
        headers={
            "host": "agripina-unblamed-mickey.ngrok-free.dev",
            "x-forwarded-proto": "https",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ticket_sent"
    assert response.json()["booking_id"] == "book_webhook"

    send_ticket.assert_awaited_once()
    kwargs = send_ticket.await_args.kwargs
    assert kwargs["to"] == "573001112233"
    assert kwargs["ticket"].payment_reference == "pi_test_webhook"
    assert kwargs["public_base_url"] == "https://agripina-unblamed-mickey.ngrok-free.dev"
    assert kwargs["ticket_id"] == "book_webhook"

    booking = booking_store.get_by_stripe_id("pi_test_webhook")
    assert booking is not None
    assert booking.status == "ticket_sent"
    assert booking.ticket.payment_reference == "pi_test_webhook"

    send_ticket.reset_mock()
    duplicate = client.post("/webhooks/stripe", json={"stripe_id": "pi_test_webhook"})

    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "already_sent"
    send_ticket.assert_not_awaited()


def test_stripe_webhook_extracts_nested_stripe_event_object(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    send_ticket = AsyncMock(return_value={"media_url": "https://example.test/ticket.png", "seats": ["F9"]})
    monkeypatch.setattr(ticket_delivery, "send_movie_ticket", send_ticket)
    client = TestClient(app)

    create_response = client.post(
        "/api/bookings/pending",
        json={
            "stripe_id": "cs_test_webhook",
            "phone_number": "573001112233",
            "ticket": _ticket_payload(),
            "booking_id": "book_nested",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.post(
        "/webhooks/stripe",
        json={
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_webhook", "payment_intent": "pi_unmapped"}},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ticket_sent"
    assert response.json()["stripe_id"] == "cs_test_webhook"


def test_stripe_webhook_returns_404_for_unknown_stripe_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    client = TestClient(app)

    response = client.post("/webhooks/stripe", json={"stripe_id": "pi_missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No booking found for Stripe ID"


def test_stripe_webhook_accepts_form_encoded_stripe_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    send_ticket = AsyncMock(return_value={"media_url": "https://example.test/ticket.png", "seats": ["F9"]})
    monkeypatch.setattr(ticket_delivery, "send_movie_ticket", send_ticket)
    client = TestClient(app)

    create_response = client.post(
        "/api/bookings/pending",
        json={
            "stripe_id": "pi_form_webhook",
            "phone_number": "573001112233",
            "ticket": _ticket_payload(),
            "booking_id": "book_form",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.post(
        "/webhooks/stripe",
        content="stripe_id=pi_form_webhook",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ticket_sent"


def test_stripe_webhook_does_not_duplicate_while_ticket_is_sending(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")
    send_ticket = AsyncMock(return_value={"media_url": "https://example.test/ticket.png", "seats": ["F9"]})
    monkeypatch.setattr(ticket_delivery, "send_movie_ticket", send_ticket)
    client = TestClient(app)

    create_response = client.post(
        "/api/bookings/pending",
        json={
            "stripe_id": "pi_sending_webhook",
            "phone_number": "573001112233",
            "ticket": _ticket_payload(),
            "booking_id": "book_sending",
        },
    )
    assert create_response.status_code == 200, create_response.text

    claim_status, booking = booking_store.claim_ticket_delivery("pi_sending_webhook")
    assert claim_status == "claimed"
    assert booking is not None
    assert booking.status == "ticket_sending"

    response = client.post("/webhooks/stripe", json={"stripe_id": "pi_sending_webhook"})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "already_sending"
    send_ticket.assert_not_awaited()
