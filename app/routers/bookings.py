"""Booking reservation helpers used before async payment webhooks arrive."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.tickets import CreatePendingBookingRequest, PendingBooking
from app.services import booking_store

router = APIRouter()


@router.post("/bookings/pending", response_model=PendingBooking)
async def create_pending_booking(req: CreatePendingBookingRequest) -> PendingBooking:
    """Persist `stripe_id -> booking` before the user completes payment."""

    payment_intent_id = req.payment_intent_id
    checkout_session_id = req.checkout_session_id
    if req.stripe_id.startswith("pi_") and payment_intent_id is None:
        payment_intent_id = req.stripe_id
    if req.stripe_id.startswith("cs_") and checkout_session_id is None:
        checkout_session_id = req.stripe_id

    return booking_store.create_pending_booking(
        phone_number=req.phone_number,
        ticket=req.ticket,
        stripe_id=req.stripe_id,
        payment_intent_id=payment_intent_id,
        checkout_session_id=checkout_session_id,
        booking_id=req.booking_id,
        metadata=req.metadata,
    )


@router.get("/bookings/{booking_id}", response_model=PendingBooking)
async def get_booking(booking_id: str) -> PendingBooking:
    booking = booking_store.get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking
