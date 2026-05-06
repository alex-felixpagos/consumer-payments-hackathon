"""
Inbound WhatsApp handling: Felix Pay demo flow (mock settle) via Kapso.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from app.config import get_settings
from app.felix_pay import (
    PaymentSessionStatus,
    SessionStore,
    apply_amount_from_quick_reply,
    build_confirmation_preview,
    process_cancel,
    process_confirm,
    start_session_after_image_stub,
)
from app.felix_pay.user_messages import (
    COLD_START_HINT,
    PAYMENT_CANCELLED,
    PAYMENT_SENT,
    VENDOR_AMOUNT_PROMPT,
)
from app.receipts_memory import ReceiptRecord, save_receipt
from app.schemas.kapso import KapsoMessage
from app.services.kapso_client import KapsoClient

logger = logging.getLogger(__name__)

_STORE = SessionStore()

_AMOUNT_BUTTONS: list[dict[str, str]] = [
    {"id": "amt_5", "title": "$5"},
    {"id": "amt_10", "title": "$10"},
    {"id": "amt_15", "title": "$15"},
]

_CONFIRM_BUTTONS: list[dict[str, str]] = [
    {"id": "pay_confirm", "title": "Confirm ✓"},
    {"id": "pay_cancel", "title": "Cancel ✗"},
]


def reset_felix_pay_state_for_tests() -> None:
    """Clear in-memory payment sessions (used by pytest)."""
    _STORE.clear()


def inbound_text(msg: KapsoMessage) -> str | None:
    """Best-effort text or button title from an inbound Kapso/WA message."""
    if msg.type == "text" and msg.text:
        return msg.text.body
    if msg.interactive:
        button_reply = msg.interactive.get("button_reply") or {}
        list_reply = msg.interactive.get("list_reply") or {}
        if button_reply:
            return button_reply.get("title") or button_reply.get("id")
        if list_reply:
            return list_reply.get("title") or list_reply.get("id")
    if msg.button:
        return msg.button.get("text") or msg.button.get("payload")
    if msg.kapso.content:
        return msg.kapso.content
    return None


def inbound_button_id(msg: KapsoMessage) -> str | None:
    """Prefer stable button id for interactive replies (amounts / confirm)."""
    if msg.interactive:
        button_reply = msg.interactive.get("button_reply") or {}
        bid = button_reply.get("id")
        if isinstance(bid, str) and bid.strip():
            return bid.strip()
    return None


async def _send_amount_prompt(client: KapsoClient, to: str, vendor_name: str) -> None:
    body = VENDOR_AMOUNT_PROMPT.format(vendor_name=vendor_name)
    await client.send_interactive_buttons(to, body, _AMOUNT_BUTTONS)


async def _send_confirmation_prompt(client: KapsoClient, to: str, session_preview: str) -> None:
    await client.send_interactive_buttons(
        to,
        session_preview,
        _CONFIRM_BUTTONS,
        footer="Demo FX rate — no real money moves.",
    )


def _receipt_base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """
    Felix Pay mock flow: image → amount buttons → confirm → receipt link.
    """
    phone = msg.phone_number
    session = _STORE.get(phone)

    # --- New payment: inbound image (Bre-B QR photo) ---
    if msg.type == "image":
        new_session = start_session_after_image_stub(phone)
        _STORE.set(phone, new_session)
        await _send_amount_prompt(client, phone, new_session.vendor_name)
        return

    # --- Cold start: text with no active session ---
    if session is None and msg.type == "text":
        await client.send_whatsapp_message(phone, COLD_START_HINT)
        return

    if session is None:
        await client.send_whatsapp_message(phone, COLD_START_HINT)
        return

    button_id = inbound_button_id(msg)
    text_body = (inbound_text(msg) or "").strip()

    # --- Awaiting USD amount choice ---
    if session.status == PaymentSessionStatus.AWAITING_AMOUNT:
        if button_id and button_id.startswith("amt_"):
            try:
                updated = apply_amount_from_quick_reply(session, button_id)
            except ValueError:
                await client.send_whatsapp_message(
                    phone,
                    "Tap *$5*, *$10*, or *$15* below to pick an amount.",
                )
                await _send_amount_prompt(client, phone, session.vendor_name)
                return
            _STORE.set(phone, updated)
            preview = build_confirmation_preview(updated)
            await _send_confirmation_prompt(client, phone, preview)
            return

        await client.send_whatsapp_message(
            phone,
            "Tap an amount below to continue.",
        )
        await _send_amount_prompt(client, phone, session.vendor_name)
        return

    # --- Awaiting confirm / cancel ---
    if session.status == PaymentSessionStatus.AWAITING_CONFIRMATION:
        if button_id == "pay_confirm" or text_body.lower() in {"confirm", "yes", "si", "sí"}:
            try:
                result = process_confirm(session)
            except ValueError as e:
                logger.warning("confirm rejected: %s", e)
                await client.send_whatsapp_message(phone, "Nothing to confirm yet. Pick an amount first.")
                _STORE.delete(phone)
                return

            rid = str(result.receipt_id)
            save_receipt(
                ReceiptRecord(
                    receipt_id=rid,
                    amount_usd=float(result.receipt["amount_usd"]),
                    amount_cop=float(result.receipt["amount_cop"]),
                    fx_rate=float(result.receipt["fx_rate"]),
                    vendor_name=str(result.receipt["vendor_name"]),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            _STORE.delete(phone)
            url = f"{_receipt_base_url()}/r/{rid}"
            await client.send_whatsapp_message(
                phone,
                f"{PAYMENT_SENT}\n{url}",
            )
            return

        if button_id == "pay_cancel" or text_body.lower() in {"cancel", "no", "stop"}:
            rolled = process_cancel(session)
            _STORE.set(phone, rolled)
            await client.send_whatsapp_message(phone, PAYMENT_CANCELLED)
            await _send_amount_prompt(client, phone, rolled.vendor_name)
            return

        preview = build_confirmation_preview(session)
        await client.send_whatsapp_message(
            phone,
            "Tap *Confirm* to pay or *Cancel* to change the amount.",
        )
        await _send_confirmation_prompt(client, phone, preview)
        return

    # --- Terminal / unexpected ---
    if session.status == PaymentSessionStatus.COMPLETE:
        _STORE.delete(phone)
    await client.send_whatsapp_message(phone, COLD_START_HINT)
