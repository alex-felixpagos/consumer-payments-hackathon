"""
Inbound WhatsApp handling: Felix Pay demo flow (mock settle) via Kapso.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from app.felix_pay import (
    PAYMENT_RAIL_LABEL,
    PaymentSession,
    PaymentSessionStatus,
    SessionStore,
    WalletStore,
    apply_amount_input,
    apply_currency_choice,
    apply_tip,
    build_confirmation_preview,
    process_confirm,
    start_session_after_image_stub,
)
from app.felix_pay.user_messages import (
    COLD_START_HINT,
    CURRENCY_PROMPT,
    INVALID_AMOUNT_HINT,
    PAYMENT_CANCELLED,
    PROCESSING_PAYMENT,
    RECEIPT_BREAKDOWN_WITH_TIP,
    RECEIPT_CHAT_MESSAGE,
    STUB_VENDOR_LOCATION,
    TIP_INVALID_HINT,
    TIP_LIST_BUTTON,
    TIP_PROMPT,
    VENDOR_AMOUNT_PROMPT,
    VENDOR_FOUND_CARD,
    WALLET_BALANCE_CARD,
)

PROCESSING_DELAY_SECONDS = 1.5
from app.receipts_memory import ReceiptRecord, save_receipt
from app.schemas.kapso import KapsoMessage
from app.services.kapso_client import KapsoClient

logger = logging.getLogger(__name__)

_STORE = SessionStore()
_WALLET = WalletStore()

_CURRENCY_BUTTONS: list[dict[str, str]] = [
    {"id": "cur_usd", "title": "🇺🇸 USD"},
    {"id": "cur_cop", "title": "🇨🇴 COP"},
]

_CONFIRM_BUTTONS: list[dict[str, str]] = [
    {"id": "pay_confirm", "title": "Confirm ✓"},
    {"id": "pay_cancel", "title": "Cancel ✗"},
]

_CURRENCY_BUTTON_TO_CODE: dict[str, str] = {
    "cur_usd": "USD",
    "cur_cop": "COP",
}

#: Tip option ids -> tip percentage. Order matches what we send to WhatsApp.
_TIP_LIST_OPTIONS: list[tuple[str, str, float]] = [
    ("tip_0", "No tip", 0.0),
    ("tip_15", "15%", 0.15),
    ("tip_20", "20%", 0.20),
    ("tip_25", "25%", 0.25),
]
_TIP_ID_TO_PCT: dict[str, float] = {opt[0]: opt[2] for opt in _TIP_LIST_OPTIONS}


def reset_felix_pay_state_for_tests() -> None:
    """Clear in-memory payment sessions and wallet balances (used by pytest)."""
    _STORE.clear()
    _WALLET.clear()


def _is_hola(msg: KapsoMessage) -> bool:
    """True when the user sent text equal to ``hola`` (case- and punctuation-insensitive)."""
    if msg.type != "text" or msg.text is None:
        return False
    body = (msg.text.body or "").strip().strip("!?.,¿¡").lower()
    return body == "hola"


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


async def _send_wallet_card(client: KapsoClient, to: str, balance_usd: float) -> None:
    await client.send_whatsapp_message(
        to, WALLET_BALANCE_CARD.format(balance_usd=balance_usd)
    )


async def _send_vendor_found_card(client: KapsoClient, to: str, session: PaymentSession) -> None:
    body = VENDOR_FOUND_CARD.format(
        vendor_name=session.vendor_name,
        vendor_location=STUB_VENDOR_LOCATION,
        amount_prompt=VENDOR_AMOUNT_PROMPT,
    )
    await client.send_whatsapp_message(to, body)


async def _send_amount_prompt(client: KapsoClient, to: str, vendor_name: str) -> None:
    """Lighter re-prompt without the full vendor card (used when state is unexpected)."""
    await client.send_whatsapp_message(to, VENDOR_AMOUNT_PROMPT)


async def _send_currency_prompt(client: KapsoClient, to: str) -> None:
    await client.send_interactive_buttons(to, CURRENCY_PROMPT, _CURRENCY_BUTTONS)


async def _send_tip_prompt(client: KapsoClient, to: str) -> None:
    sections = [
        {
            "title": "Tip",
            "rows": [
                {"id": opt_id, "title": title}
                for opt_id, title, _pct in _TIP_LIST_OPTIONS
            ],
        }
    ]
    await client.send_interactive_list(
        to,
        body_text=TIP_PROMPT,
        button_text=TIP_LIST_BUTTON,
        sections=sections,
    )


def _build_receipt_chat_message(
    *,
    vendor_name: str,
    amount_usd: float,
    amount_cop: int | float,
    tip_pct: float,
    tip_usd: float,
    total_usd: float,
    total_cop: int | float,
    payment_rail: str,
    new_balance_usd: float,
) -> str:
    if tip_pct > 0 and tip_usd > 0:
        breakdown = RECEIPT_BREAKDOWN_WITH_TIP.format(
            amount_usd=float(amount_usd),
            amount_cop=int(amount_cop),
            tip_label=f"{int(round(tip_pct * 100))}%",
            tip_usd=float(tip_usd),
        )
    else:
        breakdown = ""
    return RECEIPT_CHAT_MESSAGE.format(
        vendor_name=vendor_name,
        total_usd=float(total_usd),
        total_cop=int(total_cop),
        breakdown=breakdown,
        payment_rail=payment_rail,
        new_balance_usd=float(new_balance_usd),
    )


async def _send_confirmation_prompt(client: KapsoClient, to: str, session_preview: str) -> None:
    await client.send_interactive_buttons(
        to,
        session_preview,
        _CONFIRM_BUTTONS,
        footer="Demo FX rate — no real money moves.",
    )


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """
    Felix Pay mock flow: image → amount buttons → confirm → receipt link.
    """
    phone = msg.phone_number

    # --- Reset: user typed `hola` (any state) ---
    if _is_hola(msg):
        _STORE.delete(phone)
        await client.send_whatsapp_message(phone, COLD_START_HINT)
        return

    session = _STORE.get(phone)

    # --- New payment: inbound image (Bre-B QR photo) ---
    if msg.type == "image":
        new_session = start_session_after_image_stub(phone)
        _STORE.set(phone, new_session)
        await _send_wallet_card(client, phone, _WALLET.get_balance(phone))
        await _send_vendor_found_card(client, phone, new_session)
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

    # --- Awaiting free-text amount ---
    if session.status == PaymentSessionStatus.AWAITING_AMOUNT:
        if msg.type == "text" and text_body:
            try:
                updated = apply_amount_input(session, text_body)
            except ValueError:
                await client.send_whatsapp_message(phone, INVALID_AMOUNT_HINT)
                return
            _STORE.set(phone, updated)
            await _send_currency_prompt(client, phone)
            return

        await _send_amount_prompt(client, phone, session.vendor_name)
        return

    # --- Awaiting currency choice (USD / COP) ---
    if session.status == PaymentSessionStatus.AWAITING_CURRENCY:
        currency_code = _CURRENCY_BUTTON_TO_CODE.get(button_id or "")
        if currency_code is None and msg.type == "text":
            normalized = text_body.upper().strip(" $.")
            if normalized in {"USD", "DOLLAR", "DOLLARS"}:
                currency_code = "USD"
            elif normalized in {"COP", "PESO", "PESOS"}:
                currency_code = "COP"

        if currency_code is None:
            await _send_currency_prompt(client, phone)
            return

        try:
            updated = apply_currency_choice(session, currency_code)
        except ValueError:
            await client.send_whatsapp_message(phone, INVALID_AMOUNT_HINT)
            _STORE.delete(phone)
            return
        _STORE.set(phone, updated)
        await _send_tip_prompt(client, phone)
        return

    # --- Awaiting tip selection ---
    if session.status == PaymentSessionStatus.AWAITING_TIP:
        list_id = None
        if msg.interactive:
            list_reply = msg.interactive.get("list_reply") or {}
            list_id = list_reply.get("id") or None
        tip_pct = _TIP_ID_TO_PCT.get(list_id or button_id or "")
        if tip_pct is None and msg.type == "text":
            normalized = text_body.lower().replace("%", "").strip()
            if normalized in {"no", "no tip", "none", "skip", "0"}:
                tip_pct = 0.0
            elif normalized == "15":
                tip_pct = 0.15
            elif normalized == "20":
                tip_pct = 0.20
            elif normalized == "25":
                tip_pct = 0.25

        if tip_pct is None:
            await client.send_whatsapp_message(phone, TIP_INVALID_HINT)
            await _send_tip_prompt(client, phone)
            return

        try:
            updated = apply_tip(session, tip_pct)
        except ValueError:
            await client.send_whatsapp_message(phone, INVALID_AMOUNT_HINT)
            _STORE.delete(phone)
            return
        _STORE.set(phone, updated)
        preview = build_confirmation_preview(updated)
        await _send_confirmation_prompt(client, phone, preview)
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

            await client.send_whatsapp_message(phone, PROCESSING_PAYMENT)
            await asyncio.sleep(PROCESSING_DELAY_SECONDS)

            total_usd = float(result.receipt["total_usd"])
            total_cop = int(result.receipt["total_cop"])
            new_balance_usd = _WALLET.debit(phone, total_usd)

            rid = str(result.receipt_id)
            save_receipt(
                ReceiptRecord(
                    receipt_id=rid,
                    amount_usd=float(result.receipt["amount_usd"]),
                    amount_cop=float(result.receipt["amount_cop"]),
                    fx_rate=float(result.receipt["fx_rate"]),
                    vendor_name=str(result.receipt["vendor_name"]),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    tip_pct=float(result.receipt["tip_pct"]),
                    tip_usd=float(result.receipt["tip_usd"]),
                    total_usd=total_usd,
                    total_cop=float(total_cop),
                    payment_rail=str(result.receipt.get("payment_rail", PAYMENT_RAIL_LABEL)),
                    new_balance_usd=float(new_balance_usd),
                )
            )
            _STORE.delete(phone)
            await client.send_whatsapp_message(
                phone,
                _build_receipt_chat_message(
                    vendor_name=str(result.receipt["vendor_name"]),
                    amount_usd=float(result.receipt["amount_usd"]),
                    amount_cop=int(result.receipt["amount_cop"]),
                    tip_pct=float(result.receipt["tip_pct"]),
                    tip_usd=float(result.receipt["tip_usd"]),
                    total_usd=total_usd,
                    total_cop=total_cop,
                    payment_rail=str(result.receipt.get("payment_rail", PAYMENT_RAIL_LABEL)),
                    new_balance_usd=float(new_balance_usd),
                ),
            )
            logger.info(
                "wallet debit applied: phone=%s total_usd=%s new_balance=%s receipt_id=%s",
                phone,
                total_usd,
                new_balance_usd,
                rid,
            )
            return

        if button_id == "pay_cancel" or text_body.lower() in {"cancel", "no", "stop"}:
            _STORE.delete(phone)
            await client.send_whatsapp_message(phone, PAYMENT_CANCELLED)
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
