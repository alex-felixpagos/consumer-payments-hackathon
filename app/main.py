"""FastAPI entrypoint — Kapso WhatsApp hackathon starter."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import api, health, receipts, webhooks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

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
app.include_router(receipts.router, prefix="", tags=["Receipts"])
app.include_router(webhooks.router, prefix="/webhooks/whatsapp", tags=["Kapso Webhook"])
app.include_router(api.router, prefix="/api", tags=["API"])


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "webhook": "POST /webhooks/whatsapp (configure this URL in Kapso)",
        "kapso_docs": "https://docs.kapso.ai/docs/introduction",
    }
