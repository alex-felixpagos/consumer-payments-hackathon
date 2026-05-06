"""Anthropic model discovery for agent configuration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.agents.schemas import FALLBACK_MODELS, ModelInfo
from app.config import get_settings

logger = logging.getLogger(__name__)

_ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
_ANTHROPIC_VERSION = "2023-06-01"
_CACHE_TTL = timedelta(minutes=10)
_CACHE_STATE: dict[str, Any] = {
    "models": None,
    "cached_at": None,
}


def fallback_models() -> list[ModelInfo]:
    """Local fallback used when Anthropic model discovery is unavailable."""
    return [
        ModelInfo(id=model_id, display_name=model_id)
        for model_id in FALLBACK_MODELS
    ]


def _is_cache_fresh() -> bool:
    cached_at = _CACHE_STATE["cached_at"]
    return (
        _CACHE_STATE["models"] is not None
        and isinstance(cached_at, datetime)
        and datetime.now() - cached_at < _CACHE_TTL
    )


def _model_sort_key(model: ModelInfo) -> tuple[int, str]:
    name = model.id.lower()
    priority = 0 if name.startswith("claude") else 1
    created_at = model.created_at or ""
    return (priority, created_at)


def _parse_model(raw: dict[str, Any]) -> ModelInfo | None:
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.startswith("claude"):
        return None
    display_name = raw.get("display_name")
    created_at = raw.get("created_at")
    return ModelInfo(
        id=model_id,
        display_name=display_name if isinstance(display_name, str) else model_id,
        created_at=created_at if isinstance(created_at, str) else None,
    )


async def list_anthropic_models(force_refresh: bool = False) -> list[ModelInfo]:
    """Fetch Claude models available to the configured Anthropic API key."""
    if not force_refresh and _is_cache_fresh():
        return _CACHE_STATE["models"] or fallback_models()

    api_key = get_settings().anthropic_api_key.strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not configured; using fallback model list")
        return fallback_models()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _ANTHROPIC_MODELS_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                },
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Could not fetch Anthropic models; using fallback list: %s", exc)
        return fallback_models()

    raw_models = body.get("data", [])
    models = [
        parsed
        for raw in raw_models
        if isinstance(raw, dict) and (parsed := _parse_model(raw)) is not None
    ]
    if not models:
        logger.warning("Anthropic model response did not include Claude models; using fallback list")
        return fallback_models()

    models.sort(key=_model_sort_key, reverse=True)
    _CACHE_STATE["models"] = models
    _CACHE_STATE["cached_at"] = datetime.now()
    return models


async def model_ids() -> set[str]:
    return {model.id for model in await list_anthropic_models()}
