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
