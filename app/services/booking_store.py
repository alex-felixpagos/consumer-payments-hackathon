"""JSON-backed store for pending movie booking/payment snapshots."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.tickets import BookingStatus, PendingBooking, TicketDetails

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_BOOKINGS_FILE = _CONFIG_DIR / "pending_bookings.json"

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_phone(phone_number: str) -> str:
    return phone_number.strip().lstrip("+")


def _ensure_file() -> None:
    _BOOKINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _BOOKINGS_FILE.exists():
        _BOOKINGS_FILE.write_text(json.dumps({"bookings": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_BOOKINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"bookings": []}
    if "bookings" not in data or not isinstance(data["bookings"], list):
        data = {"bookings": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _BOOKINGS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _to_booking(raw: dict[str, Any]) -> PendingBooking:
    return PendingBooking.model_validate(raw)


def create_pending_booking(
    *,
    phone_number: str,
    ticket: TicketDetails,
    stripe_id: str | None = None,
    payment_intent_id: str | None = None,
    checkout_session_id: str | None = None,
    booking_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PendingBooking:
    """Persist the selected showing before payment leaves the conversation flow."""

    now = _now()
    raw = {
        "booking_id": booking_id or f"book_{uuid.uuid4().hex[:12]}",
        "phone_number": _normalize_phone(phone_number),
        "status": "pending_payment",
        "ticket": ticket.model_dump(),
        "stripe_id": stripe_id,
        "payment_intent_id": payment_intent_id,
        "checkout_session_id": checkout_session_id,
        "created_at": now,
        "updated_at": now,
        "ticket_sent_at": None,
        "failure_reason": None,
        "metadata": metadata or {},
    }

    with _LOCK:
        data = _load_raw()
        data["bookings"] = [
            item for item in data["bookings"] if item.get("booking_id") != raw["booking_id"]
        ]
        data["bookings"].append(raw)
        _save_raw(data)

    return _to_booking(raw)


def list_bookings(status: BookingStatus | None = None) -> list[PendingBooking]:
    with _LOCK:
        data = _load_raw()
    bookings = [_to_booking(item) for item in data["bookings"]]
    if status:
        bookings = [booking for booking in bookings if booking.status == status]
    return sorted(bookings, key=lambda booking: booking.updated_at, reverse=True)


def get_booking(booking_id: str) -> PendingBooking | None:
    with _LOCK:
        data = _load_raw()
    for item in data["bookings"]:
        if item.get("booking_id") == booking_id:
            return _to_booking(item)
    return None


def get_by_payment_intent(payment_intent_id: str) -> PendingBooking | None:
    with _LOCK:
        data = _load_raw()
    for item in data["bookings"]:
        if item.get("payment_intent_id") == payment_intent_id:
            return _to_booking(item)
    return None


def get_by_checkout_session(checkout_session_id: str) -> PendingBooking | None:
    with _LOCK:
        data = _load_raw()
    for item in data["bookings"]:
        if item.get("checkout_session_id") == checkout_session_id:
            return _to_booking(item)
    return None


def get_by_stripe_id(stripe_id: str) -> PendingBooking | None:
    """Find a booking by the generic Stripe ID returned by the payment webhook.

    The incoming ID may be a PaymentIntent (`pi_...`), Checkout Session (`cs_...`),
    or another integration-specific Stripe object ID saved as `stripe_id`.
    """

    if not stripe_id:
        return None
    with _LOCK:
        data = _load_raw()
    for item in data["bookings"]:
        if stripe_id in {
            item.get("stripe_id"),
            item.get("payment_intent_id"),
            item.get("checkout_session_id"),
        }:
            return _to_booking(item)
    return None


def _matches_stripe_id(item: dict[str, Any], stripe_id: str) -> bool:
    return stripe_id in {
        item.get("stripe_id"),
        item.get("payment_intent_id"),
        item.get("checkout_session_id"),
    }


def claim_ticket_delivery(stripe_id: str) -> tuple[str, PendingBooking | None]:
    """Atomically claim ticket delivery for a Stripe ID.

    Returns (`claimed`, booking) for the single caller that should send the
    ticket. Concurrent callers get `already_sending` or `already_sent`.
    """

    if not stripe_id:
        return "missing", None

    with _LOCK:
        data = _load_raw()
        for item in data["bookings"]:
            if not _matches_stripe_id(item, stripe_id):
                continue

            status = item.get("status")
            if status == "ticket_sent":
                return "already_sent", _to_booking(item)
            if status == "ticket_sending":
                return "already_sending", _to_booking(item)

            ticket = TicketDetails.model_validate(item["ticket"])
            item["ticket"] = ticket.model_copy(update={"payment_reference": stripe_id}).model_dump()
            item["stripe_id"] = item.get("stripe_id") or stripe_id
            if stripe_id.startswith("pi_"):
                item["payment_intent_id"] = item.get("payment_intent_id") or stripe_id
            if stripe_id.startswith("cs_"):
                item["checkout_session_id"] = item.get("checkout_session_id") or stripe_id
            item["status"] = "ticket_sending"
            item["failure_reason"] = None
            item["updated_at"] = _now()
            _save_raw(data)
            return "claimed", _to_booking(item)
    return "missing", None


def _update_booking(booking_id: str, updates: dict[str, Any]) -> PendingBooking | None:
    with _LOCK:
        data = _load_raw()
        for item in data["bookings"]:
            if item.get("booking_id") != booking_id:
                continue
            item.update(updates)
            item["updated_at"] = _now()
            _save_raw(data)
            return _to_booking(item)
    return None


def mark_booking_paid(booking_id: str, payment_reference: str | None = None) -> PendingBooking | None:
    updates: dict[str, Any] = {"status": "paid", "failure_reason": None}
    if payment_reference:
        booking = get_booking(booking_id)
        if booking:
            ticket = booking.ticket.model_copy(update={"payment_reference": payment_reference})
            updates["ticket"] = ticket.model_dump()
    return _update_booking(booking_id, updates)


def mark_ticket_sent(booking_id: str) -> PendingBooking | None:
    return _update_booking(
        booking_id,
        {
            "status": "ticket_sent",
            "ticket_sent_at": _now(),
            "failure_reason": None,
        },
    )


def mark_booking_failed(booking_id: str, reason: str | None = None) -> PendingBooking | None:
    return _update_booking(booking_id, {"status": "failed", "failure_reason": reason})
