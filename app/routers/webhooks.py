"""Kapso WhatsApp webhooks: verification (GET) and inbound messages (POST)."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.bot import handle_agent_inbound, handle_inbound
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


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


@router.get("")
@router.get("/{agent_name}")
async def verify_webhook(
    agent_name: str | None = None,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
) -> str:
    """Meta/Kapso webhook subscription verification."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.kapso_verify_token and hub_challenge:
        if agent_name:
            logger.info("Webhook verified for agent=%s", agent_name)
        else:
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
        webhook = KapsoWebhook.model_validate_json(raw)
    except Exception as e:
        logger.exception("Invalid webhook JSON: %s", e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload") from e

    msg = webhook.message
    if msg.direction != "inbound":
        return {"status": "ignored"}

    try:
        client = KapsoClient()
    except ValueError as e:
        logger.error("Kapso client not configured: %s", e)
        return {"status": "received", "note": "kapso not configured; set .env"}

    try:
        await handle_inbound(msg, client, public_base_url=_public_base_url(request))
    except Exception:
        logger.exception("handle_inbound failed")
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


@router.post("/{agent_name}")
async def receive_agent_webhook(agent_name: str, request: Request) -> dict[str, str]:
    """Inbound Kapso events routed to a named agent from the webhook path."""
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
        webhook = KapsoWebhook.model_validate_json(raw)
    except Exception as e:
        logger.exception("Invalid webhook JSON for agent %s: %s", agent_name, e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload") from e

    msg = webhook.message
    if msg.direction != "inbound":
        return {"status": "ignored", "agent": agent_name}

    try:
        client = KapsoClient()
    except ValueError as e:
        logger.error("Kapso client not configured: %s", e)
        return {"status": "received", "agent": agent_name, "note": "kapso not configured; set .env"}

    try:
        await handle_agent_inbound(agent_name, msg, client, public_base_url=_public_base_url(request))
    except Exception:
        logger.exception("handle_agent_inbound failed for agent=%s", agent_name)
        # Still acknowledge to avoid provider retry storms; log and optionally notify.
    return {"status": "received", "agent": agent_name}
