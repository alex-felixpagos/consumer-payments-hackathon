"""Schemas for pending movie bookings and generated ticket details."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


BookingStatus = Literal[
    "pending_payment",
    "paid",
    "ticket_sending",
    "ticket_sent",
    "failed",
    "expired",
]


class TicketDetails(BaseModel):
    """Movie showing data needed to render an e-ticket."""

    movie_title: str = Field(..., min_length=1)
    theater_name: str = Field(..., min_length=1)
    theater_address: str | None = None
    start_time: str | None = Field(
        default=None,
        description="ISO datetime for the selected showtime, when available.",
    )
    display_time: str | None = Field(
        default=None,
        description="Human-friendly showtime label returned by the movie provider.",
    )
    format: str | None = None
    seats: list[str] = Field(default_factory=list)
    booking_reference: str | None = None
    payment_reference: str | None = None
    amount_cents: int | None = None
    currency: str | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _accept_single_seat(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("seats") and data.get("seat"):
            return {**data, "seats": [str(data["seat"])]}
        return data

    @model_validator(mode="after")
    def _normalize_seats(self) -> "TicketDetails":
        self.seats = [seat.strip().upper() for seat in self.seats if seat and seat.strip()]
        return self


class PendingBooking(BaseModel):
    """Durable snapshot created before payment and consumed by a later webhook."""

    booking_id: str
    phone_number: str = Field(..., min_length=5)
    status: BookingStatus = "pending_payment"
    ticket: TicketDetails
    stripe_id: str | None = None
    payment_intent_id: str | None = None
    checkout_session_id: str | None = None
    created_at: str
    updated_at: str
    ticket_sent_at: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreatePendingBookingRequest(BaseModel):
    """Payload used by payment setup code to persist the pre-webhook mapping."""

    stripe_id: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=5)
    ticket: TicketDetails
    booking_id: str | None = None
    payment_intent_id: str | None = None
    checkout_session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
