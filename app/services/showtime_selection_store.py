"""Short-lived showtime selection store keyed by WhatsApp phone number."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.tickets import TicketDetails

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_SELECTIONS_FILE = _CONFIG_DIR / "showtime_selections.json"

_LOCK = threading.Lock()
_MAX_OPTIONS_PER_PHONE = 3


class ShowtimeSelection(BaseModel):
    selection_id: str
    phone_number: str
    title: str
    ticket: TicketDetails
    created_at: str
    raw: dict[str, Any] = Field(default_factory=dict)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_phone(phone_number: str) -> str:
    return phone_number.strip().lstrip("+")


def _ensure_file() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _SELECTIONS_FILE.exists():
        _SELECTIONS_FILE.write_text(json.dumps({"selections": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_SELECTIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"selections": []}
    if "selections" not in data or not isinstance(data["selections"], list):
        data = {"selections": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _SELECTIONS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _to_selection(raw: dict[str, Any]) -> ShowtimeSelection:
    return ShowtimeSelection.model_validate(raw)


def _ticket_from_showtime(showtime: dict[str, Any]) -> TicketDetails | None:
    movie_title = showtime.get("movie_title")
    theater_name = showtime.get("theater_name")
    if not movie_title or not theater_name:
        return None

    settings = get_settings()
    amount_cents = showtime.get("amount_cents") or showtime.get("price_cents") or settings.ticket_default_amount_cents
    currency = showtime.get("currency") or settings.stripe_currency
    return TicketDetails(
        movie_title=str(movie_title),
        theater_name=str(theater_name),
        theater_address=showtime.get("theater_address"),
        start_time=showtime.get("start_time"),
        display_time=showtime.get("display_time"),
        format=showtime.get("format"),
        amount_cents=int(amount_cents) if amount_cents is not None else None,
        currency=str(currency).lower() if currency else None,
    )


def _button_title(ticket: TicketDetails) -> str:
    parts = [part for part in [ticket.display_time, ticket.format] if part]
    title = " ".join(parts) or ticket.movie_title
    return title[:20]


def save_showtime_options(phone_number: str, showtimes: list[dict[str, Any]]) -> list[ShowtimeSelection]:
    """Replace the user's last selectable options with up to three showtimes."""

    phone = _normalize_phone(phone_number)
    now = _now()
    selections: list[dict[str, Any]] = []
    for showtime in showtimes[:_MAX_OPTIONS_PER_PHONE]:
        ticket = _ticket_from_showtime(showtime)
        if ticket is None:
            continue
        selection_id = f"sel_{uuid.uuid4().hex[:10]}"
        selections.append(
            {
                "selection_id": selection_id,
                "phone_number": phone,
                "title": _button_title(ticket),
                "ticket": ticket.model_dump(),
                "created_at": now,
                "raw": showtime,
            }
        )

    with _LOCK:
        data = _load_raw()
        data["selections"] = [item for item in data["selections"] if item.get("phone_number") != phone]
        data["selections"].extend(selections)
        _save_raw(data)

    return [_to_selection(item) for item in selections]


def get_selection(phone_number: str, selection_id: str) -> ShowtimeSelection | None:
    phone = _normalize_phone(phone_number)
    with _LOCK:
        data = _load_raw()
    for item in data["selections"]:
        if item.get("phone_number") == phone and item.get("selection_id") == selection_id:
            return _to_selection(item)
    return None
