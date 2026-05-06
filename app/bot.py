"""
Inbound WhatsApp handling: reply to users via Kapso.

Delegates copy to ``app.debt_coach.build_reply`` (state machine + commands).
"""

from app.debt_coach import build_reply
from app.schemas.kapso import KapsoMessage
from app.services.kapso_client import KapsoClient


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


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """
    Called for each *inbound* message after webhook verification.

    ``msg.phone_number`` is the user to reply to (same format Kapso expects for ``to``).
    """
    text = inbound_text(msg)
    body = build_reply(msg.phone_number, text)
    await client.send_whatsapp_message(msg.phone_number, body)
