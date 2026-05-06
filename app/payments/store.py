"""JSON-file backed payment store.

Card numbers and CVVs are intentionally never written to disk. The store keeps
payment status, Stripe references, retry attempts, and enough order context to
debug a demo from `config/payments.json`.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.payments import PaymentRecord

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_PAYMENTS_FILE = _CONFIG_DIR / "payments.json"

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_file() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _PAYMENTS_FILE.exists():
        _PAYMENTS_FILE.write_text(json.dumps({"payments": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_PAYMENTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"payments": []}
    if "payments" not in data or not isinstance(data["payments"], list):
        data = {"payments": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _PAYMENTS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _normalize_phone(phone: str) -> str:
    return phone.strip().lstrip("+")


def _payment_url(base_url: str, payment_id: str) -> str:
    return f"{base_url.rstrip('/')}/pay/{payment_id}"


def _to_record(raw: dict[str, Any]) -> PaymentRecord:
    return PaymentRecord(**raw)


def _find(data: dict[str, Any], payment_id: str) -> dict[str, Any] | None:
    for raw in data["payments"]:
        if raw.get("id") == payment_id:
            return raw
    return None


def card_last4(card_number: str) -> str | None:
    digits = re.sub(r"\D", "", card_number)
    if len(digits) < 4:
        return None
    return digits[-4:]


def list_payments() -> list[PaymentRecord]:
    with _LOCK:
        data = _load_raw()
    payments = [_to_record(raw) for raw in data["payments"]]
    return sorted(payments, key=lambda item: item.updated_at, reverse=True)


def get_payment(payment_id: str) -> PaymentRecord | None:
    with _LOCK:
        data = _load_raw()
    raw = _find(data, payment_id)
    if raw is None:
        return None
    return _to_record(raw)


def create_payment(
    *,
    phone_number: str,
    amount_cents: int,
    currency: str,
    public_base_url: str,
    movie_title: str | None = None,
    order_summary: str | None = None,
) -> PaymentRecord:
    now = _now()
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"
    record = {
        "id": payment_id,
        "phone_number": _normalize_phone(phone_number),
        "amount_cents": max(1, int(amount_cents)),
        "currency": (currency or "usd").lower(),
        "status": "pending",
        "payment_url": _payment_url(public_base_url, payment_id),
        "movie_title": movie_title,
        "order_summary": order_summary,
        "stripe_payment_intent_id": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
        "paid_at": None,
        "failed_at": None,
        "attempts": [],
    }

    with _LOCK:
        data = _load_raw()
        data["payments"].append(record)
        _save_raw(data)
    return _to_record(record)


def mark_processing(payment_id: str) -> PaymentRecord | None:
    now = _now()
    with _LOCK:
        data = _load_raw()
        raw = _find(data, payment_id)
        if raw is None:
            return None
        raw["status"] = "processing"
        raw["updated_at"] = now
        raw["error_message"] = None
        _save_raw(data)
        return _to_record(raw)


def mark_succeeded(
    payment_id: str,
    *,
    stripe_payment_intent_id: str | None,
    card_last4_value: str | None,
) -> PaymentRecord | None:
    now = _now()
    with _LOCK:
        data = _load_raw()
        raw = _find(data, payment_id)
        if raw is None:
            return None
        raw["status"] = "succeeded"
        raw["stripe_payment_intent_id"] = stripe_payment_intent_id
        raw["error_message"] = None
        raw["updated_at"] = now
        raw["paid_at"] = now
        raw["failed_at"] = None
        raw.setdefault("attempts", []).append(
            {
                "status": "succeeded",
                "created_at": now,
                "stripe_payment_intent_id": stripe_payment_intent_id,
                "card_last4": card_last4_value,
                "error_message": None,
            }
        )
        _save_raw(data)
        return _to_record(raw)


def mark_failed(
    payment_id: str,
    *,
    error_message: str,
    stripe_payment_intent_id: str | None = None,
    card_last4_value: str | None = None,
) -> PaymentRecord | None:
    now = _now()
    with _LOCK:
        data = _load_raw()
        raw = _find(data, payment_id)
        if raw is None:
            return None
        raw["status"] = "failed"
        raw["stripe_payment_intent_id"] = stripe_payment_intent_id
        raw["error_message"] = error_message
        raw["updated_at"] = now
        raw["failed_at"] = now
        raw.setdefault("attempts", []).append(
            {
                "status": "failed",
                "created_at": now,
                "stripe_payment_intent_id": stripe_payment_intent_id,
                "card_last4": card_last4_value,
                "error_message": error_message,
            }
        )
        _save_raw(data)
        return _to_record(raw)
