"""Kapso WhatsApp webhooks: verification (GET) and inbound messages (POST)."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.bot import handle_inbound
from app.config import get_settings
from app.schemas import KapsoWebhook
from app.services.kapso_client import KapsoClient

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not secret:
        return False
    sig = signature_header
    if "=" in sig:
        sig = sig.split("=", 1)[1]
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


@router.get("")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
) -> str:
    """Meta/Kapso webhook subscription verification."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.kapso_verify_token and hub_challenge:
        logger.info("Webhook verified")
        return hub_challenge
    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request) -> dict[str, str]:
    """Inbound Kapso events (typically one message per request)."""
    settings = get_settings()
    raw = await request.body()

    if settings.kapso_webhook_secret:
        signature = (
            request.headers.get("X-Kapso-Signature")
            or request.headers.get("X-Signature")
            or request.headers.get("X-Hub-Signature-256")
            or request.headers.get("X-Hub-Signature")
        )
        if not signature:
            if settings.environment == "production":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        elif not _verify_signature(raw, signature, settings.kapso_webhook_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Webhook body is not valid JSON; acknowledging and ignoring")
        return {"status": "ignored", "reason": "invalid_json"}

    logger.info("Webhook received: %s", json.dumps(payload)[:2000])

    # Kapso wraps message events in an envelope: {"type": "...", "data": ...}
    # `data` may be a single object OR (when batching is on) a list of objects.
    # Only act on `whatsapp.message.received`; ignore sent/delivered/read/etc. so
    # we don't reply to our own outbound messages.
    event_type = payload.get("type") or payload.get("event")
    if event_type and not event_type.endswith("message.received"):
        return {"status": "ignored", "event": event_type}

    raw_data = payload.get("data", payload)
    items = raw_data if isinstance(raw_data, list) else [raw_data]

    webhooks: list[KapsoWebhook] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            webhooks.append(KapsoWebhook.model_validate(item))
        except Exception as e:
            logger.warning("Skipping item that did not match KapsoWebhook schema: %s", e)

    if not webhooks:
        return {"status": "ignored", "reason": "no_valid_messages"}

    try:
        client = KapsoClient()
    except ValueError as e:
        logger.error("Kapso client not configured: %s", e)
        return {"status": "received", "note": "kapso not configured; set .env"}

    handled = 0
    for webhook in webhooks:
        msg = webhook.message
        if msg.direction != "inbound":
            continue
        try:
            await handle_inbound(msg, client)
            handled += 1
        except Exception:
            logger.exception("handle_inbound failed")
            # Still acknowledge to avoid provider retry storms.
    return {"status": "received", "handled": str(handled)}


@router.post("/debug")
async def debug_webhook(request: Request) -> dict:
    """Log and return raw JSON — use while wiring Kapso to your environment."""
    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError:
        payload = (await request.body()).decode("utf-8", errors="replace")
    logger.info("Webhook debug payload: %s", json.dumps(payload) if isinstance(payload, dict) else payload)
    return {"status": "ok", "payload": payload}
