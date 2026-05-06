"""Felix Pay in-memory session models and store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class PaymentSessionStatus(StrEnum):
    """Allowed payment session lifecycle states."""

    AWAITING_AMOUNT = "AWAITING_AMOUNT"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"


@dataclass
class PaymentSession:
    """Typed state for a single payer's Felix Pay checkout stub."""

    payer_phone: str
    vendor_breb_key: str
    vendor_name: str
    vendor_phone: str | None
    amount_usd: float | None
    amount_cop: int | None
    fx_rate: float | None
    session_id: UUID
    created_at: datetime
    status: PaymentSessionStatus


class SessionStore:
    """Phone-keyed in-memory session index (not persisted)."""

    def __init__(self) -> None:
        self._by_phone: dict[str, PaymentSession] = {}

    def get(self, phone: str) -> PaymentSession | None:
        return self._by_phone.get(phone)

    def set(self, phone: str, session: PaymentSession) -> None:
        self._by_phone[phone] = session

    def delete(self, phone: str) -> None:
        self._by_phone.pop(phone, None)

    def clear(self) -> None:
        """Remove all sessions (tests only)."""
        self._by_phone.clear()


def utcnow() -> datetime:
    """Timezone-aware UTC `now` (injectable in tests via monkeypatch if needed)."""
    return datetime.now(timezone.utc)


def new_session_id() -> UUID:
    return uuid4()
