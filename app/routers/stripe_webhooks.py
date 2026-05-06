"""Stripe payment-completed webhook integration for ticket delivery."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request

from app.services import ticket_delivery

router = APIRouter()
logger = logging.getLogger(__name__)


def _add_candidate(candidates: list[str], value: Any) -> None:
    if isinstance(value, str) and value.strip() and value not in candidates:
        candidates.append(value.strip())


def _stripe_id_candidates(payload: Any, query_params: dict[str, str]) -> list[str]:
    candidates: list[str] = []

    keys = (
        "stripe_id",
        "stripeId",
        "payment_intent_id",
        "paymentIntentId",
        "payment_intent",
        "paymentIntent",
        "checkout_session_id",
        "checkoutSessionId",
        "session_id",
        "sessionId",
    )

    for key in keys:
        _add_candidate(candidates, query_params.get(key))

    if isinstance(payload, str):
        _add_candidate(candidates, payload)
        return candidates

    if not isinstance(payload, dict):
        return candidates

    for key in keys:
        _add_candidate(candidates, payload.get(key))

    data = payload.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if isinstance(obj, dict):
        for key in (*keys, "id"):
            _add_candidate(candidates, obj.get(key))

    # Use top-level `id` last so real Stripe event IDs (`evt_...`) do not beat
    # nested PaymentIntent or Checkout Session IDs.
    top_level_id = payload.get("id")
    if isinstance(top_level_id, str) and not top_level_id.startswith("evt_"):
        _add_candidate(candidates, top_level_id)

    return candidates


async def _request_payload(request: Request) -> Any:
    raw = await request.body()
    if not raw:
        return {}
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(raw.decode("utf-8", errors="replace"))
        return {key: values[0] for key, values in parsed.items() if values}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace").strip()


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


@router.post("/stripe")
async def receive_stripe_webhook(request: Request) -> dict[str, Any]:
    """Receive a completed Stripe transaction ID and send the matching ticket."""

    payload = await _request_payload(request)
    candidates = _stripe_id_candidates(payload, dict(request.query_params))
    if not candidates:
        raise HTTPException(status_code=400, detail="Missing Stripe ID")

    for candidate in candidates:
        try:
            return await ticket_delivery.deliver_ticket_for_stripe_id(
                candidate,
                public_base_url=_public_base_url(request),
            )
        except ticket_delivery.BookingNotFoundError:
            continue
        except Exception as exc:
            logger.exception("Ticket send failed for stripe_id=%s", candidate)
            raise HTTPException(status_code=502, detail=f"Ticket send failed: {exc}") from exc

    logger.warning("Stripe webhook did not match a booking: candidates=%s", candidates)
    raise HTTPException(status_code=404, detail="No booking found for Stripe ID")
