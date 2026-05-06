"""Idempotent ticket delivery by Stripe ID."""

from __future__ import annotations

from typing import Any

from app.services import booking_store
from app.services.kapso_client import KapsoClient
from app.services.ticket_service import send_movie_ticket


class BookingNotFoundError(RuntimeError):
    pass


async def deliver_ticket_for_stripe_id(
    stripe_id: str,
    *,
    public_base_url: str,
    client: KapsoClient | None = None,
) -> dict[str, Any]:
    """Send the ticket for a paid Stripe transaction exactly once."""

    claim_status, booking = booking_store.claim_ticket_delivery(stripe_id)
    if booking is None:
        raise BookingNotFoundError("No booking found for Stripe ID")

    if claim_status == "already_sent":
        return {
            "status": "already_sent",
            "stripe_id": stripe_id,
            "booking_id": booking.booking_id,
        }

    if claim_status == "already_sending":
        return {
            "status": "already_sending",
            "stripe_id": stripe_id,
            "booking_id": booking.booking_id,
        }

    try:
        result = await send_movie_ticket(
            to=booking.phone_number,
            ticket=booking.ticket,
            client=client,
            public_base_url=public_base_url,
            ticket_id=booking.booking_id,
        )
    except Exception as exc:
        booking_store.mark_booking_failed(booking.booking_id, str(exc))
        raise

    booking_store.mark_ticket_sent(booking.booking_id)
    return {
        "status": "ticket_sent",
        "stripe_id": stripe_id,
        "booking_id": booking.booking_id,
        "media_url": result.get("media_url"),
        "seats": result.get("seats", []),
    }
