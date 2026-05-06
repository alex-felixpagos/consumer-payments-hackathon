"""
Inbound WhatsApp handling: reply to users via Kapso.

Default demo replies with a fixed template that quotes what they sent. Replace
``handle_inbound`` with LLM flows, payments, or state machines — keep it async.
"""

import logging

from app.schemas.kapso import KapsoMessage
from app.services.brain import append_log, load_brain, should_refresh_summary, update_profile, update_summary
from app.services.gemini_client import GeminiClient
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
        content = msg.kapso.content
        # Strip audio metadata — keep only the transcript text
        if "Transcript:" in content:
            content = content.split("Transcript:", 1)[1].strip()
        return content
    return None


async def handle_inbound(msg: KapsoMessage, client: KapsoClient) -> None:
    """
    Called for each *inbound* message after webhook verification.

    ``msg.phone_number`` is the user to reply to (same format Kapso expects for ``to``).
    """
    user_id = msg.phone_number
    text = inbound_text(msg)

    logger.info(
        "INBOUND | from=%s type=%s message=%r",
        msg.phone_number,
        msg.type,
        text or f"<{msg.type} — no text extracted>",
    )

    _WELCOME_TRIGGER = "hey biovibe, i'm ready to start tracking my health!"
    if text and text.strip().lower() == _WELCOME_TRIGGER:
        welcome = (
            "Welcome to BioVibe! 🌱\n\n"
            "I'm your personal health tracking assistant. Here's what you can do:\n\n"
            "• Tell me what you ate: \"Had oatmeal and coffee for breakfast\"\n"
            "• Log how you feel: \"I have a mild headache since noon\"\n"
            "• Track your workout: \"Ran 5km this morning\"\n"
            "• Check in on your mood: \"Feeling anxious today\"\n\n"
            "I'll remember everything and share insights to help you feel your best.\n\n"
            "What would you like to track first?"
        )
        logger.info("OUTBOUND | to=%s message=<welcome>", msg.phone_number)
        await client.send_whatsapp_message(msg.phone_number, welcome)
        return

    brain = load_brain(user_id)
    logger.info("BRAIN | user=%s log_entries=%d", user_id, len(brain["log_history"]))

    gemini = GeminiClient()
    result = await gemini.process_message(text or "", msg.type, brain)
    intent = result.get("intent", "unrecognized")

    logger.info("GEMINI | intent=%s category=%s", intent, result.get("category"))

    if intent == "log":
        updated_brain = append_log(user_id, {
            "category": result.get("category"),
            "raw_input": text or "",
            "media_type": msg.type,
            "structured": result.get("structured", {}),
        })
        if should_refresh_summary(updated_brain):
            new_summary = await gemini.summarize_brain(updated_brain)
            update_summary(user_id, new_summary)
            logger.info("BRAIN | summary refreshed for user=%s", user_id)
    elif intent == "profile_update":
        pu = result.get("profile_update", {})
        update_profile(
            user_id,
            name=pu.get("name"),
            traits=pu.get("traits", []),
        )
        logger.info("BRAIN | profile updated for user=%s", user_id)

    reply = result.get("reply", "")
    logger.info("OUTBOUND | to=%s message=%r", msg.phone_number, reply)
    await client.send_whatsapp_message(msg.phone_number, reply)
