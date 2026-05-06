"""
Inbound WhatsApp handling: champeta payment demo.

Three branches:
1. nfm_reply (user submitted the payment Flow) -> charge Stripe, reply with result.
2. text matching ``pay <amount>`` -> send the payment Flow CTA.
3. anything else -> short help text.
"""

from __future__ import annotations

import logging
import re

from app.config import get_settings
from app.schemas.kapso import KapsoMessage
from app.schemas.kapso.nfm_reply import extract_nfm_reply
from app.services.kapso_client import KapsoClient
from app.services.stripe_service import charge_card

logger = logging.getLogger(__name__)

PAY_RE = re.compile(r"^\s*pay\s+(\d+(?:\.\d{1,2})?)\s*$", re.IGNORECASE)
HELP_TEXT = "Send `pay <amount>` to start a test payment. Example: `pay 1`"


def inbound_text(msg: KapsoMessage) -> str | None:
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


async def _handle_payment_submission(msg: KapsoMessage, client: KapsoClient) -> None:
    reply = extract_nfm_reply(msg)
    if reply is None:
        await client.send_whatsapp_message(msg.phone_number, "Could not read the payment form, please try again.")
        return

    settings = get_settings()
    amount_cents = reply.amount_cents or 100  # fallback to $1 if echo failed
    amount_display = f"${amount_cents / 100:.2f}"

    result = await charge_card(
        card_number=reply.card_number,
        expiration=reply.expiration,
        cvv=reply.cvv,
        amount_cents=amount_cents,
        currency=settings.stripe_currency,
    )
    if result.success:
        body = f"✅ Charged {amount_display} — {result.payment_intent_id}"
    else:
        body = f"❌ Payment failed — {result.error_message or 'unknown error'}"
    await client.send_whatsapp_message(msg.phone_number, body)


async def _handle_pay_command(amount: float, msg: KapsoMessage, client: KapsoClient) -> None:
    settings = get_settings()
    if not settings.kapso_flow_id:
        await client.send_whatsapp_message(
            msg.phone_number,
            "Payment flow is not configured (KAPSO_FLOW_ID missing). Run `python -m app.services.flow_setup` first.",
        )
        return

    amount_cents = int(round(amount * 100))
    amount_display = f"${amount:.2f} {settings.stripe_currency.upper()}"
    await client.send_flow_message(
        to=msg.phone_number,
        flow_id=settings.kapso_flow_id,
        flow_cta=f"Pay {amount_display}",
        body_text=f"Tap below to pay {amount_display} (test mode).",
        screen="PAYMENT",
        initial_data={
            "amount_display": amount_display,
            "amount_cents": amount_cents,
        },
    )


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """Called for each inbound message after webhook verification."""
    if msg.interactive and msg.interactive.get("type") == "nfm_reply":
        await _handle_payment_submission(msg, client)
        return

    text = inbound_text(msg) or ""
    pay_match = PAY_RE.match(text)
    if pay_match:
        await _handle_pay_command(float(pay_match.group(1)), msg, client)
        return

    await client.send_whatsapp_message(msg.phone_number, HELP_TEXT)
