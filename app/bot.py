"""
Inbound WhatsApp handling: reply to users via Kapso.

Default demo replies with a fixed template that quotes what they sent. Replace
``handle_inbound`` with LLM flows, payments, or state machines — keep it async.
"""

from app.schemas.kapso import KapsoMessage
from app.services.kapso_client import KapsoClient
from app.services.rates_service import (
    handle_rates_message,
    is_awaiting_rates_input,
    is_rates_request,
)


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


def _reply_body_for_demo(user_payload: str | None, message_type: str) -> str:
    if user_payload:
        quoted = user_payload
    else:
        quoted = f"a {message_type} message (send text for a full quote)"
    return f"I just received: {quoted}. Lets start building 🚀"


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """
    Called for each *inbound* message after webhook verification.

    ``msg.phone_number`` is the user to reply to (same format Kapso expects for ``to``).
    """
    text = inbound_text(msg)

    if is_rates_request(text) or is_awaiting_rates_input(msg.phone_number):
        body = await handle_rates_message(msg.phone_number, text)
    else:
        body = _reply_body_for_demo(text, msg.type)

    await client.send_whatsapp_message(msg.phone_number, body)
