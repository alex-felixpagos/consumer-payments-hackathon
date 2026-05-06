"""
Inbound WhatsApp handling.

Thin orchestrator: parse text from the channel-specific message, ask the
concierge agent for a reply, send it (and any attached chart images) back
through the channel.
"""

import logging

from app.channels.base import Channel
from app.concierge import respond
from app.concierge.i18n import get_locale
from app.concierge.prompts import system_message
from app.schemas.kapso import KapsoMessage
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
            return button_reply.get("title") or button_reply.get("id")
        if list_reply:
            return list_reply.get("title") or list_reply.get("id")
    if msg.button:
        return msg.button.get("text") or msg.button.get("payload")
    if msg.kapso.content:
        return msg.kapso.content
    return None


async def handle_inbound(msg: KapsoMessage, client: KapsoClient | Channel) -> None:
    """
    Called for each *inbound* message after webhook verification.

    The second argument is treated as a Channel; KapsoClient is wrapped on the
    fly so existing webhook code keeps working.
    """
    from app.channels.kapso import KapsoChannel

    channel: Channel = client if isinstance(client, Channel) else KapsoChannel(client)
    user_id = msg.phone_number
    user_text = inbound_text(msg)

    if not user_text:
        await channel.send_text(user_id, system_message(get_locale(user_id), "non_text"))
        return

    try:
        reply = await respond(user_id, user_text)
    except Exception:
        logger.exception("concierge.respond failed")
        await channel.send_text(user_id, system_message(get_locale(user_id), "agent_error"))
        return

    await channel.send_text(user_id, reply.text)
    for attachment in reply.media:
        try:
            if attachment.kind == "image":
                await channel.send_image(user_id, attachment.url, caption=attachment.caption)
        except Exception:
            logger.exception("failed to send attachment %s", attachment.url)
