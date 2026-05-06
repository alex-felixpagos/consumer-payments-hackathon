"""
Inbound WhatsApp handling: reply to users via Kapso.

Delegates to ``app.debt_coach.build_outbound`` (state machine + commands; welcome uses buttons).
"""

from app.debt_coach import build_outbound
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
            # Prefer stable button ids over titles so commands (start, menu) match reliably.
            bid = button_reply.get("id")
            if bid:
                return bid
            return button_reply.get("title")
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
    out = build_outbound(msg.phone_number, text)
    if out.buttons:
        await client.send_interactive_buttons(
            msg.phone_number,
            out.text,
            [{"id": b["id"], "title": b["title"]} for b in out.buttons],
            header=out.header,
            footer=out.footer,
        )
    else:
        await client.send_whatsapp_message(msg.phone_number, out.text)
