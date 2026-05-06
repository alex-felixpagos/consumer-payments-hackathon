"""FastAPI entrypoint — Kapso WhatsApp hackathon starter."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import (
    agents,
    api,
    bookings,
    buy_ticket,
    chat,
    health,
    payments,
    stripe_webhooks,
    webhooks,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "tickets").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Minimal send/receive WhatsApp backend via [Kapso](https://docs.kapso.ai/docs/introduction).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/webhooks/whatsapp", tags=["Kapso Webhook"])
app.include_router(stripe_webhooks.router, prefix="/webhooks", tags=["Stripe Webhook"])
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(bookings.router, prefix="/api", tags=["Bookings"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(buy_ticket.router, prefix="/api", tags=["Buy Ticket"])
app.include_router(payments.router, prefix="/api", tags=["Payments"])

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "webhook": "POST /webhooks/whatsapp (configure this URL in Kapso)",
        "stripe_webhook": "POST /webhooks/stripe",
        "kapso_docs": "https://docs.kapso.ai/docs/introduction",
    }


@app.get("/pay/{payment_id}")
async def payment_page(payment_id: str) -> FileResponse:
    """Serve the React checkout for payment links sent over WhatsApp."""
    _ = payment_id
    if not FRONTEND_INDEX.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment page is not built. Run `npm run build` in frontend.",
        )
    return FileResponse(FRONTEND_INDEX)
