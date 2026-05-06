"""Pure Felix Pay domain logic (no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID, uuid4

from app.felix_pay.session import (
    PaymentSession,
    PaymentSessionStatus,
    new_session_id,
    utcnow,
)

# Stub merchant for Track B image flow until catalog wiring exists.
_STUB_VENDOR_NAME = "Café El Tiempo"
_STUB_VENDOR_BREB_KEY = "+573001234567"

# Hardcoded COP per 1 USD for hackathon demo.
_COP_PER_USD = 4230.0

_QUICK_REPLY_USD: dict[str, float] = {
    "amt_5": 5.0,
    "amt_10": 10.0,
    "amt_15": 15.0,
}


@dataclass(frozen=True)
class ConfirmResult:
    """Outcome of a successful payment confirmation (stub)."""

    session: PaymentSession
    receipt_id: UUID
    receipt: dict[str, Any]


def start_session_after_image_stub(payer_phone: str) -> PaymentSession:
    """Begin a checkout after the user shared a stub vendor image."""
    return PaymentSession(
        payer_phone=payer_phone,
        vendor_breb_key=_STUB_VENDOR_BREB_KEY,
        vendor_name=_STUB_VENDOR_NAME,
        vendor_phone=None,
        amount_usd=None,
        amount_cop=None,
        fx_rate=None,
        session_id=new_session_id(),
        created_at=utcnow(),
        status=PaymentSessionStatus.AWAITING_AMOUNT,
    )


def apply_amount_from_quick_reply(session: PaymentSession, button_id: str) -> PaymentSession:
    """Apply a quick-reply amount (e.g. ``amt_10``) and move to confirmation."""
    if button_id not in _QUICK_REPLY_USD:
        msg = f"Unknown amount button_id: {button_id!r}"
        raise ValueError(msg)
    usd = _QUICK_REPLY_USD[button_id]
    cop = int(usd * _COP_PER_USD)
    return replace(
        session,
        amount_usd=usd,
        amount_cop=cop,
        fx_rate=_COP_PER_USD,
        status=PaymentSessionStatus.AWAITING_CONFIRMATION,
    )


def build_confirmation_preview(session: PaymentSession) -> str:
    """Human-readable summary before the payer confirms."""
    if session.amount_usd is None or session.amount_cop is None:
        msg = "Session has no amount set; cannot build confirmation preview."
        raise ValueError(msg)
    lines = [
        f"Pay *{session.vendor_name}*",
        f"Amount: *${session.amount_usd:g} USD* (~{session.amount_cop:,} COP)",
        f"To: `{session.vendor_breb_key}`",
        "",
        "Reply *Confirm* to pay, or *Cancel* to go back.",
    ]
    return "\n".join(lines)


def process_confirm(session: PaymentSession) -> ConfirmResult:
    """Finalize stub payment: COMPLETE session plus receipt payload for UI."""
    if session.status != PaymentSessionStatus.AWAITING_CONFIRMATION:
        msg = "Can only confirm when status is AWAITING_CONFIRMATION."
        raise ValueError(msg)
    if session.amount_usd is None or session.amount_cop is None:
        msg = "Cannot confirm without amount_usd and amount_cop."
        raise ValueError(msg)

    receipt_id = uuid4()
    completed = replace(session, status=PaymentSessionStatus.COMPLETE)
    receipt: dict[str, Any] = {
        "receipt_id": str(receipt_id),
        "payer_phone": completed.payer_phone,
        "vendor_name": completed.vendor_name,
        "vendor_breb_key": completed.vendor_breb_key,
        "amount_usd": completed.amount_usd,
        "amount_cop": completed.amount_cop,
        "fx_rate": completed.fx_rate,
        "session_id": str(completed.session_id),
        "status": completed.status.value,
    }
    return ConfirmResult(session=completed, receipt_id=receipt_id, receipt=receipt)


def process_cancel(session: PaymentSession) -> PaymentSession:
    """Abandon confirmation intent; return to amount selection with cleared amounts."""
    return replace(
        session,
        amount_usd=None,
        amount_cop=None,
        fx_rate=None,
        status=PaymentSessionStatus.AWAITING_AMOUNT,
    )
