"""In-memory receipt store for Felix Pay (hackathon; not thread-safe)."""

from __future__ import annotations

from dataclasses import dataclass

_STORE: dict[str, ReceiptRecord] = {}


@dataclass
class ReceiptRecord:
    """A persisted receipt row keyed by ``receipt_id``."""

    receipt_id: str
    amount_usd: float
    amount_cop: float
    fx_rate: float
    vendor_name: str
    created_at: str  # ISO 8601 string
    tip_pct: float = 0.0
    tip_usd: float = 0.0
    total_usd: float = 0.0
    total_cop: float = 0.0
    payment_rail: str = "Bre-B"
    new_balance_usd: float = 0.0


def save_receipt(record: ReceiptRecord) -> str:
    """Persist ``record`` and return its ``receipt_id``."""
    _STORE[record.receipt_id] = record
    return record.receipt_id


def get_receipt(receipt_id: str) -> ReceiptRecord | None:
    """Return the receipt for ``receipt_id``, or ``None`` if absent."""
    return _STORE.get(receipt_id)


def clear_receipts_for_tests() -> None:
    """Clear all stored receipts (pytest only)."""
    _STORE.clear()


def list_receipt_ids_for_tests() -> list[str]:
    """Return all stored receipt ids (pytest only)."""
    return list(_STORE.keys())
