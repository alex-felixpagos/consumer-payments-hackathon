"""
Inbound WhatsApp handling: reply to users via Kapso.

Delegates to ``app.debt_coach.build_outbound`` (state machine + commands; welcome uses buttons).
If ``parse_command`` does not match, optionally resolves intent via ``get_intent`` (Haiku router).
"""

import logging

from app.debt_coach import (
    build_outbound,
    get_session,
    map_intent_label_to_command,
    parse_command,
    should_run_intent_fallback,
)
from app.schemas.kapso import KapsoMessage
from app.services.claude_client import get_intent
from app.services.kapso_client import KapsoClient

logger = logging.getLogger(__name__)


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
    phone = msg.phone_number
    resolved_command: str | None = None
    if text and text.strip():
        raw = text.strip()
        if parse_command(raw) is None and should_run_intent_fallback(get_session(phone)):
            try:
                intent_label = await get_intent(raw)
                resolved_command = map_intent_label_to_command(intent_label)
            except Exception as exc:
                logger.warning("get_intent fallback skipped: %s", exc)

    out = build_outbound(phone, text, resolved_command=resolved_command)
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
