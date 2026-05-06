"""Pure Felix Pay domain logic (no I/O)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID, uuid4

from app.felix_pay.session import (
    PaymentSession,
    PaymentSessionStatus,
    new_session_id,
    utcnow,
)

_STUB_VENDOR_NAME = "Café El Tiempo"
_STUB_VENDOR_BREB_KEY = "+573001234567"

# Hardcoded COP per 1 USD for hackathon demo.
_COP_PER_USD = 4230.0

#: Lock window shown to the payer in the confirmation preview.
_RATE_LOCK_SECONDS = 60

#: Payment rail label that appears on the receipt + confirmation copy.
PAYMENT_RAIL_LABEL = "Bre-B"

_CURRENCY_USD = "USD"
_CURRENCY_COP = "COP"
_VALID_CURRENCIES = frozenset({_CURRENCY_USD, _CURRENCY_COP})

#: Tip percentages exposed in the WhatsApp interactive list.
ALLOWED_TIP_PCTS: tuple[float, ...] = (0.0, 0.15, 0.20, 0.25)


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
        amount_input=None,
        amount_usd=None,
        amount_cop=None,
        fx_rate=None,
        tip_pct=None,
        tip_usd=None,
        total_usd=None,
        total_cop=None,
        session_id=new_session_id(),
        created_at=utcnow(),
        status=PaymentSessionStatus.AWAITING_AMOUNT,
    )


def parse_amount_text(raw: str) -> float:
    """
    Extract a positive amount from free-text input.

    Accepts forms like ``10``, ``$10``, ``10.50``, ``1,000``, ``USD 10``.
    Raises :class:`ValueError` on empty / non-positive / unparseable input.
    """
    if raw is None:
        msg = "Empty amount"
        raise ValueError(msg)
    cleaned = raw.strip()
    if not cleaned:
        msg = "Empty amount"
        raise ValueError(msg)

    if "-" in cleaned:
        msg = f"Negative amounts are not allowed (got {raw!r})"
        raise ValueError(msg)

    digits = re.sub(r"[^0-9.]", "", cleaned.replace(",", ""))
    if not digits or digits == ".":
        msg = f"Could not parse amount from {raw!r}"
        raise ValueError(msg)

    try:
        value = float(digits)
    except ValueError as e:
        raise ValueError(f"Could not parse amount from {raw!r}") from e

    if value <= 0:
        msg = f"Amount must be positive (got {value})"
        raise ValueError(msg)

    return value


def apply_amount_input(session: PaymentSession, raw_text: str) -> PaymentSession:
    """Persist the typed amount on the session and transition to currency choice."""
    amount = parse_amount_text(raw_text)
    return replace(
        session,
        amount_input=amount,
        amount_usd=None,
        amount_cop=None,
        fx_rate=None,
        status=PaymentSessionStatus.AWAITING_CURRENCY,
    )


def apply_currency_choice(session: PaymentSession, currency: str) -> PaymentSession:
    """Resolve the typed amount into USD + COP using the demo FX rate."""
    if session.amount_input is None:
        msg = "Cannot pick currency before an amount is entered."
        raise ValueError(msg)

    code = (currency or "").strip().upper()
    if code not in _VALID_CURRENCIES:
        msg = f"Unsupported currency: {currency!r}"
        raise ValueError(msg)

    if code == _CURRENCY_USD:
        amount_usd = float(session.amount_input)
        amount_cop = int(round(amount_usd * _COP_PER_USD))
    else:
        amount_cop = int(round(session.amount_input))
        amount_usd = amount_cop / _COP_PER_USD

    return replace(
        session,
        amount_usd=amount_usd,
        amount_cop=amount_cop,
        fx_rate=_COP_PER_USD,
        status=PaymentSessionStatus.AWAITING_TIP,
    )


def apply_tip(session: PaymentSession, tip_pct: float) -> PaymentSession:
    """Apply the chosen tip percentage and compute USD + COP totals."""
    if session.amount_usd is None or session.amount_cop is None:
        msg = "Cannot pick tip before currency is chosen."
        raise ValueError(msg)
    if tip_pct < 0:
        msg = f"Tip percent must be >= 0 (got {tip_pct})."
        raise ValueError(msg)

    tip_usd = round(float(session.amount_usd) * float(tip_pct), 2)
    total_usd = round(float(session.amount_usd) + tip_usd, 2)
    total_cop = int(round(total_usd * float(session.fx_rate or _COP_PER_USD)))

    return replace(
        session,
        tip_pct=float(tip_pct),
        tip_usd=tip_usd,
        total_usd=total_usd,
        total_cop=total_cop,
        status=PaymentSessionStatus.AWAITING_CONFIRMATION,
    )


def build_confirmation_preview(session: PaymentSession) -> str:
    """Mock-style FX preview shown above the Confirm/Cancel buttons."""
    if session.amount_usd is None or session.amount_cop is None:
        msg = "Session has no amount set; cannot build confirmation preview."
        raise ValueError(msg)
    rate = int(round(session.fx_rate or _COP_PER_USD))
    total_usd = session.total_usd if session.total_usd is not None else session.amount_usd
    total_cop = session.total_cop if session.total_cop is not None else session.amount_cop
    lines = [f"*Pay {session.vendor_name}*"]
    if session.tip_pct is not None and session.tip_usd is not None and session.tip_usd > 0:
        tip_label = f"{int(round(session.tip_pct * 100))}%"
        lines.extend(
            [
                f"Subtotal: ${session.amount_usd:,.2f} USD ({session.amount_cop:,} COP)",
                f"Tip ({tip_label}): ${session.tip_usd:,.2f} USD",
                f"*Total: ${total_usd:,.2f} USD → {total_cop:,} COP*",
            ]
        )
    else:
        lines.append(f"${total_usd:,.2f} USD → {total_cop:,} COP")
    lines.append(f"Rate: {rate:,} · Locked for {_RATE_LOCK_SECONDS}s")
    return "\n".join(lines)


def process_confirm(session: PaymentSession) -> ConfirmResult:
    """Finalize stub payment: COMPLETE session plus receipt payload for UI."""
    if session.status != PaymentSessionStatus.AWAITING_CONFIRMATION:
        msg = "Can only confirm when status is AWAITING_CONFIRMATION."
        raise ValueError(msg)
    if session.amount_usd is None or session.amount_cop is None:
        msg = "Cannot confirm without amount_usd and amount_cop."
        raise ValueError(msg)

    tip_pct = session.tip_pct if session.tip_pct is not None else 0.0
    tip_usd = session.tip_usd if session.tip_usd is not None else 0.0
    total_usd = session.total_usd if session.total_usd is not None else float(session.amount_usd)
    total_cop = session.total_cop if session.total_cop is not None else int(session.amount_cop)

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
        "tip_pct": tip_pct,
        "tip_usd": tip_usd,
        "total_usd": total_usd,
        "total_cop": total_cop,
        "payment_rail": PAYMENT_RAIL_LABEL,
        "session_id": str(completed.session_id),
        "status": completed.status.value,
    }
    return ConfirmResult(session=completed, receipt_id=receipt_id, receipt=receipt)


def process_cancel(session: PaymentSession) -> PaymentSession:
    """Reset amount/currency choices but keep the vendor selection."""
    return replace(
        session,
        amount_input=None,
        amount_usd=None,
        amount_cop=None,
        fx_rate=None,
        tip_pct=None,
        tip_usd=None,
        total_usd=None,
        total_cop=None,
        status=PaymentSessionStatus.AWAITING_AMOUNT,
    )
