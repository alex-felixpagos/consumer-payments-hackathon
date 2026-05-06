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


def inbound_image_url(msg: KapsoMessage) -> tuple[str | None, str]:
    """Extract image URL and caption from an image message.

    Kapso delivers image messages with a URL embedded in kapso.content
    following the pattern: 'Image attached (...) URL: https://...'
    The user's caption (if any) is in msg.image.get('caption').
    Returns (url, caption).
    """
    url: str | None = None
    content = msg.kapso.content or ""
    if "URL:" in content:
        url = content.split("URL:", 1)[1].strip().split()[0]
    elif msg.image and msg.image.get("link"):
        url = msg.image["link"]
    caption = (msg.image or {}).get("caption") or ""
    return url, caption


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

    # Hero image served directly from GitHub raw content (always public, no deploy needed)
    _WELCOME_IMAGE_URL = "https://raw.githubusercontent.com/alex-felixpagos/consumer-payments-hackathon/feature/cumbia-team/web/biovibe-hero.png"
    _WELCOME_TRIGGER = "hey biovibe, i'm ready to start tracking my health!"
    _PROFILE_SETUP_BTN_ID = "setup_profile"

    if text and text.strip().lower() == _WELCOME_TRIGGER:
        logger.info("OUTBOUND | to=%s message=<welcome image + interactive>", msg.phone_number)
        try:
            await client.send_media_message(
                msg.phone_number,
                "image",
                _WELCOME_IMAGE_URL,
                caption="BioVibe — AI Health Tracking on WhatsApp 🌱",
            )
        except Exception:
            logger.warning("Could not send welcome image; falling back to text-only")
        await client.send_interactive_buttons(
            msg.phone_number,
            body_text=(
                "Welcome to BioVibe! 🌱\n\n"
                "Your AI health companion on WhatsApp. Log meals, symptoms, workouts and sleep — I'll remember everything and give you personalized insights.\n\n"
                "Want to set up your profile for a better experience?"
            ),
            buttons=[{"id": _PROFILE_SETUP_BTN_ID, "title": "Set up my profile ✨"}],
            footer="Or just start chatting — I learn as we go!",
        )
        return

    # Handle profile setup button tap
    if msg.interactive:
        button_reply = msg.interactive.get("button_reply") or {}
        if button_reply.get("id") == _PROFILE_SETUP_BTN_ID:
            logger.info("OUTBOUND | to=%s message=<profile setup prompt>", msg.phone_number)
            await client.send_whatsapp_message(
                msg.phone_number,
                "Great! Tell me a bit about yourself 👤\n\n"
                "Feel free to share things like:\n\n"
                "• Your name\n"
                "• Dietary restrictions (vegan, lactose intolerant, gluten-free…)\n"
                "• Allergies\n"
                "• Health goals (lose weight, sleep better, more energy…)\n"
                "• Any conditions I should know about\n\n"
                "Just write it naturally — I'll take care of the rest! 🧠",
            )
            return

    brain = load_brain(user_id)
    logger.info("BRAIN | user=%s log_entries=%d", user_id, len(brain["log_history"]))

    gemini = GeminiClient()

    if msg.type == "image":
        image_url, caption = inbound_image_url(msg)
        logger.info("INBOUND IMAGE | url=%s caption=%r", image_url, caption)
        if image_url:
            result = await gemini.process_image(image_url, caption, brain)
        else:
            logger.warning("Image message received but no URL found — falling back to text flow")
            result = await gemini.process_message(caption or "", msg.type, brain)
    else:
        result = await gemini.process_message(text or "", msg.type, brain)
    intent = result.get("intent", "unrecognized")

    logger.info("GEMINI | intent=%s category=%s", intent, result.get("category"))

    # Always save profile info if present, regardless of intent
    pu = result.get("profile_update") or {}
    pu_name = pu.get("name")
    pu_traits = pu.get("traits") or []
    if pu_name or pu_traits:
        update_profile(user_id, name=pu_name, traits=pu_traits)
        logger.info("BRAIN | profile updated for user=%s name=%s traits=%s", user_id, pu_name, pu_traits)

    if intent == "log":
        if msg.type == "image":
            img_url, img_caption = inbound_image_url(msg)
            raw_input = f"{img_url} | {img_caption}" if img_caption else (img_url or "")
        else:
            raw_input = text or ""
        updated_brain = append_log(user_id, {
            "category": result.get("category"),
            "raw_input": raw_input,
            "media_type": msg.type,
            "structured": result.get("structured", {}),
        })
        if should_refresh_summary(updated_brain):
            new_summary = await gemini.summarize_brain(updated_brain)
            update_summary(user_id, new_summary)
            logger.info("BRAIN | summary refreshed for user=%s", user_id)

    reply = result.get("reply", "")
    logger.info("OUTBOUND | to=%s message=%r", msg.phone_number, reply)
    await client.send_whatsapp_message(msg.phone_number, reply)
