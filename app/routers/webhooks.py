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
    logger.info("Kapso webhook POST: %s bytes", len(raw))

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
            logger.warning(
                "Webhook signature invalid — Kapso POST rejected. If testing locally, "
                "ensure KAPSO_WEBHOOK_SECRET matches the signing secret in Kapso or leave it empty in .env."
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        webhook = KapsoWebhook.model_validate_json(raw)
    except Exception as e:
        logger.exception("Invalid webhook JSON: %s", e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload") from e

    msg = webhook.message
    logger.info(
        "Parsed webhook message id=%s type=%s direction=%s from=%s",
        msg.id,
        msg.type,
        msg.direction,
        msg.phone_number,
    )
    if msg.direction != "inbound":
        logger.info("Skipping non-inbound message (direction=%r)", msg.direction)
        return {"status": "ignored"}

    try:
        client = KapsoClient()
    except ValueError as e:
        logger.error("Kapso client not configured: %s", e)
        return {"status": "received", "note": "kapso not configured; set .env"}

    try:
        await handle_inbound(msg, client)
        logger.info("handle_inbound finished for message id=%s", msg.id)
    except Exception:
        logger.exception(
            "handle_inbound failed — check Uvicorn logs for Kapso HTTP errors "
            "(401/403 API key, wrong KAPSO_PHONE_NUMBER_ID, 24h messaging window, sandbox recipient)."
        )
        # Still acknowledge to avoid provider retry storms; log and optionally notify.
    return {"status": "received"}


@router.post("/debug")
async def debug_webhook(request: Request) -> dict:
    """Log and return raw JSON — use while wiring Kapso to your environment."""
    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError:
        payload = (await request.body()).decode("utf-8", errors="replace")
    logger.info("Webhook debug payload: %s", json.dumps(payload) if isinstance(payload, dict) else payload)
    return {"status": "ok", "payload": payload}
