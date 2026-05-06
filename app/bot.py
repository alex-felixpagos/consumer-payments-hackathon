"""Inbound WhatsApp handling for payment-link demo flows."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

import httpx

from app.agents.runner import TransientAgentError, run_agent_turn
from app.agents.store import get_agent_by_name
from app.config import get_settings
from app.payments import store as payment_store
from app.schemas.kapso import KapsoMessage
from app.schemas.tickets import TicketDetails
from app.services import booking_store, showtime_selection_store
from app.services.kapso_client import KapsoClient

logger = logging.getLogger(__name__)

PAY_RE = re.compile(r"^\s*pay\s+(\d+(?:\.\d{1,2})?)\s*$", re.IGNORECASE)
HELP_TEXT = "Send `pay <amount>` to create a Stripe test payment link. Example: `pay 1`"
SHOWTIME_SELECTION_PREFIX = "showtime:"

_RECENT_MESSAGE_TTL_SECONDS = 10 * 60
_MAX_RECENT_MESSAGE_IDS = 500
_RECENT_MESSAGE_IDS: dict[str, float] = {}
_RECENT_MESSAGE_IDS_LOCK = threading.Lock()


def _claim_message_once(msg: KapsoMessage) -> bool:
    """Return False for duplicate webhook deliveries of the same Kapso message."""
    now = time.monotonic()
    with _RECENT_MESSAGE_IDS_LOCK:
        expired = [
            message_id
            for message_id, seen_at in _RECENT_MESSAGE_IDS.items()
            if now - seen_at > _RECENT_MESSAGE_TTL_SECONDS
        ]
        for message_id in expired:
            _RECENT_MESSAGE_IDS.pop(message_id, None)

        if msg.id in _RECENT_MESSAGE_IDS:
            return False

        if len(_RECENT_MESSAGE_IDS) >= _MAX_RECENT_MESSAGE_IDS:
            oldest = min(_RECENT_MESSAGE_IDS, key=_RECENT_MESSAGE_IDS.get)
            _RECENT_MESSAGE_IDS.pop(oldest, None)

        _RECENT_MESSAGE_IDS[msg.id] = now
        return True


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


async def _send_whatsapp_text_safely(
    client: KapsoClient,
    to: str,
    text: str,
    context: str,
) -> bool:
    try:
        await client.send_whatsapp_message(to, text)
    except httpx.HTTPError as exc:
        logger.error("Could not send WhatsApp text during %s: %s", context, exc)
        return False
    return True


def _amount_display(amount_cents: int, currency: str) -> str:
    cur = currency.upper()
    if cur == "COP":
        return f"COP {amount_cents / 100:,.0f}"
    return f"${amount_cents / 100:.2f} {cur}"


def _selection_id_from_message(msg: KapsoMessage) -> str | None:
    candidates: list[str | None] = []
    if msg.interactive:
        button_reply = msg.interactive.get("button_reply") or {}
        list_reply = msg.interactive.get("list_reply") or {}
        candidates.extend([button_reply.get("id"), list_reply.get("id")])
    if msg.button:
        candidates.extend([msg.button.get("payload"), msg.button.get("text")])
    for value in candidates:
        if value and value.startswith(SHOWTIME_SELECTION_PREFIX):
            return value.removeprefix(SHOWTIME_SELECTION_PREFIX)
    return None


async def _handle_pay_command(
    amount: float,
    msg: KapsoMessage,
    client: KapsoClient,
    *,
    movie_title: str | None = None,
    order_summary: str | None = None,
    ticket: TicketDetails | None = None,
) -> bool:
    """Create a payment record + (optionally) a pending booking and send the link.

    When `ticket` is provided we persist a pending booking keyed by the new
    payment id so the React portal's success handler (and the Stripe webhook
    fallback) can deliver the ticket image once Stripe confirms the charge.
    """
    if amount <= 0:
        amount = 1.0
    settings = get_settings()
    amount_cents = int(round(amount * 100))
    currency = settings.stripe_currency
    amount_display = _amount_display(amount_cents, currency)

    payment = payment_store.create_payment(
        phone_number=msg.phone_number,
        amount_cents=amount_cents,
        currency=currency,
        public_base_url=settings.public_payment_base_url,
        movie_title=movie_title or (ticket.movie_title if ticket else None),
        order_summary=order_summary,
    )

    if ticket is not None:
        ticket_for_booking = ticket.model_copy(
            update={
                "amount_cents": amount_cents,
                "currency": currency,
            }
        )
        booking_store.create_pending_booking(
            phone_number=msg.phone_number,
            ticket=ticket_for_booking,
            stripe_id=payment.id,
            metadata={"payment_id": payment.id, "source": "whatsapp_payment_link"},
        )

    body_parts = [f"Your payment link is ready for {amount_display}."]
    if ticket:
        showtime_label = ticket.display_time or ticket.start_time or ""
        meta_line = " — ".join(part for part in [ticket.theater_name, showtime_label] if part)
        body_parts.append(f"Movie: {ticket.movie_title}")
        if meta_line:
            body_parts.append(meta_line)
    elif movie_title:
        body_parts.append(f"Movie: {movie_title}")
    if order_summary:
        body_parts.append(order_summary)
    body_parts.extend(
        [
            f"Pay here: {payment.payment_url}",
            "For Stripe test mode, you can use card 4242 4242 4242 4242 with any future expiry and CVC.",
        ]
    )
    return await _send_whatsapp_text_safely(
        client,
        msg.phone_number,
        "\n\n".join(body_parts),
        "payment link send",
    )


def _payment_trigger_amount(payment_trigger: Any) -> float:
    if not isinstance(payment_trigger, dict):
        return 1.0
    amount = payment_trigger.get("amount")
    try:
        if amount is None and payment_trigger.get("amount_cents") is not None:
            amount = float(payment_trigger["amount_cents"]) / 100
        parsed = float(amount if amount is not None else 1.0)
    except (TypeError, ValueError):
        return 1.0
    return parsed if parsed > 0 else 1.0


async def _handle_showtime_selection(
    selection_id: str,
    msg: KapsoMessage,
    client: KapsoClient,
) -> None:
    selection = showtime_selection_store.get_selection(msg.phone_number, selection_id)
    if selection is None:
        await client.send_whatsapp_message(
            msg.phone_number,
            "I could not find that showtime anymore. Send the movie name again and I will refresh the options.",
        )
        return

    ticket = selection.ticket
    settings = get_settings()
    amount_cents = ticket.amount_cents or settings.ticket_default_amount_cents
    amount = amount_cents / 100
    showtime_label = ticket.display_time or ticket.start_time or ""
    order_summary = " — ".join(
        part for part in [ticket.theater_name, showtime_label, ticket.format] if part
    )
    await _handle_pay_command(
        amount,
        msg,
        client,
        movie_title=ticket.movie_title,
        order_summary=order_summary or None,
        ticket=ticket,
    )


async def _send_showtime_selection_buttons(
    phone_number: str,
    showtime_results: list[dict],
    client: KapsoClient,
) -> None:
    selections = showtime_selection_store.save_showtime_options(phone_number, showtime_results)
    if not selections:
        return
    buttons = [
        {"id": f"{SHOWTIME_SELECTION_PREFIX}{selection.selection_id}", "title": selection.title}
        for selection in selections[:3]
    ]
    try:
        await client.send_interactive_buttons(
            to=phone_number,
            header="Book tickets",
            body_text="Pick a showtime and I will send you a secure payment link.",
            buttons=buttons,
        )
    except Exception:
        logger.exception("Could not send showtime selection buttons to %s", phone_number)


async def handle_inbound(
    msg: KapsoMessage,
    client: KapsoClient,
    public_base_url: str | None = None,
) -> None:
    """Called for each inbound message after webhook verification."""
    _ = public_base_url  # currently unused; kept for future webhook-driven flows

    selection_id = _selection_id_from_message(msg)
    if selection_id:
        await _handle_showtime_selection(selection_id, msg, client)
        return

    text = inbound_text(msg) or ""
    pay_match = PAY_RE.match(text)
    if pay_match:
        await _handle_pay_command(float(pay_match.group(1)), msg, client)
        return

    await client.send_whatsapp_message(msg.phone_number, HELP_TEXT)


async def handle_agent_inbound(
    agent_name: str,
    msg: KapsoMessage,
    client: KapsoClient,
    public_base_url: str | None = None,
) -> None:
    """Run the named agent for an inbound WhatsApp message and reply via Kapso."""
    if not _claim_message_once(msg):
        logger.info("Ignoring duplicate inbound Kapso message id=%s", msg.id)
        return

    text = inbound_text(msg) or ""
    if _selection_id_from_message(msg) or PAY_RE.match(text):
        await handle_inbound(msg, client, public_base_url=public_base_url)
        return

    agent = get_agent_by_name(agent_name)
    if agent is None:
        logger.error("Inbound webhook requested unknown agent name=%s", agent_name)
        await client.send_whatsapp_message(
            msg.phone_number,
            f"I couldn't find the agent '{agent_name}'. Please check the webhook URL.",
        )
        return

    if not text or not text.strip():
        await client.send_whatsapp_message(
            msg.phone_number,
            "I can help best with text messages right now. Send me what you'd like to do.",
        )
        return

    try:
        result = await run_agent_turn(
            agent=agent,
            phone_number=msg.phone_number,
            user_message=text.strip(),
        )
    except TransientAgentError:
        logger.warning("Agent provider is temporarily unavailable for agent=%s", agent.name)
        await client.send_whatsapp_message(
            msg.phone_number,
            "My movie brain is a little slammed right now. Try me again in a minute and I'll pick it back up.",
        )
        return
    except RuntimeError:
        logger.exception("Agent runtime failed for agent=%s", agent.name)
        await client.send_whatsapp_message(
            msg.phone_number,
            "I hit a setup issue while trying to answer. Please check the server logs and try again.",
        )
        return

    reply_text = (result.get("response") or "").strip()
    payment_trigger = result.get("payment_trigger")
    showtime_results = result.get("showtime_results") or []
    if not reply_text and not payment_trigger and not showtime_results:
        logger.warning("Agent %s produced empty reply for phone=%s", agent.name, msg.phone_number)
        return

    if reply_text:
        await _send_whatsapp_text_safely(client, msg.phone_number, reply_text, "agent reply")

    if showtime_results:
        await _send_showtime_selection_buttons(msg.phone_number, showtime_results, client)

    if payment_trigger:
        await _handle_pay_command(
            _payment_trigger_amount(payment_trigger),
            msg,
            client,
            movie_title=payment_trigger.get("movie_title"),
            order_summary=payment_trigger.get("order_summary"),
        )
