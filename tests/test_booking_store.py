from __future__ import annotations

from app.schemas.tickets import TicketDetails
from app.services import booking_store


def test_pending_booking_can_be_found_and_marked_sent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(booking_store, "_BOOKINGS_FILE", tmp_path / "pending_bookings.json")

    ticket = TicketDetails(
        movie_title="Dune: Part Two",
        theater_name="Cine Colombia Andino",
        start_time="2026-05-06T19:05:00",
        display_time="7:05 PM",
        format="IMAX",
        seat="d6",
        amount_cents=4500000,
        currency="cop",
    )

    booking = booking_store.create_pending_booking(
        phone_number="+573001112233",
        ticket=ticket,
        stripe_id="pi_test_123",
        payment_intent_id="pi_test_123",
        checkout_session_id="cs_test_123",
        booking_id="book_test_123",
    )

    assert booking.phone_number == "573001112233"
    assert booking.status == "pending_payment"
    assert booking.ticket.seats == ["D6"]

    by_intent = booking_store.get_by_payment_intent("pi_test_123")
    assert by_intent is not None
    assert by_intent.booking_id == "book_test_123"

    by_stripe_id = booking_store.get_by_stripe_id("pi_test_123")
    assert by_stripe_id is not None
    assert by_stripe_id.booking_id == "book_test_123"

    paid = booking_store.mark_booking_paid("book_test_123", payment_reference="pi_test_123")
    assert paid is not None
    assert paid.status == "paid"
    assert paid.ticket.payment_reference == "pi_test_123"

    sent = booking_store.mark_ticket_sent("book_test_123")
    assert sent is not None
    assert sent.status == "ticket_sent"
    assert sent.ticket_sent_at is not None
