"""Inbound payload from a completed WhatsApp Flow (nfm_reply)."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.kapso.message import KapsoMessage
from app.schemas.tickets import TicketDetails

logger = logging.getLogger(__name__)


class NfmReply(BaseModel):
    """Parsed contents of `interactive.nfm_reply.response_json` for our payment flow."""

    flow_token: str | None = None
    card_number: str
    expiration: str
    cvv: str
    amount_cents: int | None = None
    booking_id: str | None = None
    movie_title: str | None = None
    theater_name: str | None = None
    theater_address: str | None = None
    start_time: str | None = None
    display_time: str | None = None
    format: str | None = None
    currency: str | None = None

    model_config = ConfigDict(extra="allow")

    def to_ticket_details(self) -> TicketDetails | None:
        if not self.movie_title or not self.theater_name:
            return None
        return TicketDetails(
            movie_title=self.movie_title,
            theater_name=self.theater_name,
            theater_address=self.theater_address,
            start_time=self.start_time,
            display_time=self.display_time,
            format=self.format,
            booking_reference=self.booking_id,
            amount_cents=self.amount_cents,
            currency=self.currency,
        )


def extract_nfm_reply(message: KapsoMessage) -> NfmReply | None:
    """Return parsed payment-flow data, or None if this isn't an nfm_reply message.

    Kapso pre-parses the response into `kapso.flow_response`; we prefer that path
    and fall back to decoding `interactive.nfm_reply.response_json` ourselves.
    """
    interactive = message.interactive
    if not interactive or interactive.get("type") != "nfm_reply":
        return None

    flow_response = (message.kapso.model_extra or {}).get("flow_response")
    if isinstance(flow_response, dict):
        return NfmReply.model_validate(flow_response)

    raw = (interactive.get("nfm_reply") or {}).get("response_json")
    if not raw:
        logger.warning("nfm_reply missing response_json: %s", interactive)
        return None
    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("nfm_reply response_json invalid JSON: %s — raw=%r", e, raw)
        return None
    return NfmReply.model_validate(parsed)
