"""HTTP client for the Procinal cinema API (apinew.procinal.com.co).

Buys real movie tickets in Colombia. Self-contained — no Kapso, no Stripe.

Endpoints used (all under ``settings.procinal_base_url``):
- ``POST /api/auth/login``                      — JWT (Bearer), cached in module global
- ``GET  /api/cinemas``                         — theatre catalog
- ``GET  /api/movies``                          — movie catalog
- ``GET  /api/showtimes``                       — showtime catalog (no auth required)
- ``GET  /api/showtimes/{id}?email={email}``    — seat map + score_bill (Secuencia)
- ``POST /api/auth/payment/reservation``        — hold seats, returns reservation
- ``POST /api/auth/payment/card``               — direct ePayco card charge

Sharp edges (learned the hard way):
- ``score_bill.Secuencia`` is voided after a failed payment. Always re-fetch
  showtime detail just before reserving.
- Reservation TTL is ~10 minutes. Pay immediately after reserving.
- Login response includes ``access_token`` and an ``expires_at``. Token TTL
  is ~6 months in practice; we cache and re-login on 401.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ---- Constants ----------------------------------------------------------

DEFAULT_PRICE_CODE = 103          # "50% Base 2D (Web)" — General zone, web
DEFAULT_PRICE_VALOR = 6250        # COP — at the same code (snapshot 2026-05-06)
HTTP_TIMEOUT = 30.0


# ---- Module state -------------------------------------------------------

_jwt_cache: str | None = None


def _origin_headers(token: str | None = None) -> dict[str, str]:
    """Headers that look like the official SPA — Procinal's Laravel app
    is fine without them, but they keep us indistinguishable from a browser."""
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://procinal.com.co",
        "Referer": "https://procinal.com.co/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        ),
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ---- Auth ---------------------------------------------------------------

class ProcinalAuthError(RuntimeError):
    pass


async def login(force_refresh: bool = False) -> str:
    """Return a Bearer JWT for Procinal. Cached in a module global."""
    global _jwt_cache
    if _jwt_cache and not force_refresh:
        return _jwt_cache

    settings = get_settings()
    if not settings.procinal_documento or not settings.procinal_clave:
        raise ProcinalAuthError(
            "PROCINAL_DOCUMENTO and PROCINAL_CLAVE must be set in .env"
        )

    payload = {
        "documento": settings.procinal_documento,
        "clave": settings.procinal_clave,
    }
    code, body = await _request("POST", "/api/auth/login", json=payload, auth=False)
    if code != 200:
        raise ProcinalAuthError(f"Procinal login failed: HTTP {code} — {str(body)[:300]}")
    token = body.get("access_token")
    if not token:
        raise ProcinalAuthError(f"login response missing access_token: {body}")
    _jwt_cache = token
    logger.info("Procinal login OK (user_id=%s)", body.get("user", {}).get("id"))
    return token


async def _request(
    method: str,
    path: str,
    *,
    json: Any = None,
    auth: bool = False,
    params: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Single HTTP wrapper with auto-refresh on 401."""
    settings = get_settings()
    url = f"{settings.procinal_base_url}{path}"

    async def _do(token: str | None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            return await client.request(
                method, url, json=json, params=params, headers=_origin_headers(token)
            )

    token = await login() if auth else None
    resp = await _do(token)
    if resp.status_code == 401 and auth:
        logger.info("Procinal 401 — refreshing JWT and retrying")
        token = await login(force_refresh=True)
        resp = await _do(token)

    try:
        body = resp.json()
    except Exception:
        body = {"_raw": resp.text[:500]}
    return resp.status_code, body


# ---- Catalog (no auth required) ----------------------------------------

async def list_movies() -> list[dict[str, Any]]:
    code, body = await _request("GET", "/api/movies")
    if code != 200:
        raise RuntimeError(f"list_movies HTTP {code}: {body}")
    return body.get("movies", [])


async def list_showtimes(
    *,
    only_dates: list[str] | None = None,
    cinema_ids: list[int] | None = None,
    only_active: bool = True,
) -> list[dict[str, Any]]:
    """Return showtimes filtered client-side (the API returns everything)."""
    code, body = await _request("GET", "/api/showtimes")
    if code != 200:
        raise RuntimeError(f"list_showtimes HTTP {code}: {body}")
    items: list[dict[str, Any]] = body.get("data", [])
    if only_active:
        items = [s for s in items if s.get("is_active") == 1]
    if only_dates:
        items = [s for s in items if s.get("fecha_funcion") in only_dates]
    if cinema_ids:
        # cinemas → rooms → room_id; we filter by the precomputed cinemas index
        cinemas = await list_cinemas()
        room_to_cinema = {r["id"]: c["id"] for c in cinemas for r in c.get("rooms", [])}
        items = [s for s in items if room_to_cinema.get(s.get("room_id")) in cinema_ids]
    return items


async def list_cinemas() -> list[dict[str, Any]]:
    code, body = await _request("GET", "/api/cinemas")
    if code != 200:
        raise RuntimeError(f"list_cinemas HTTP {code}: {body}")
    return body.get("data", [])


# ---- Showtime detail + seat picking ------------------------------------

async def get_showtime_detail(showtime_id: int, email: str) -> dict[str, Any]:
    """Returns the dict with keys: ``bill``, ``prices``, ``mapRoom``, ``statusRoom``,
    ``puntoVenta``. The ``email`` query param is required to populate ``statusRoom``
    correctly — without it the seats array is empty/invalid.
    """
    code, body = await _request(
        "GET",
        f"/api/showtimes/{showtime_id}",
        params={"email": email},
    )
    if code != 200:
        raise RuntimeError(f"get_showtime_detail HTTP {code}: {body}")
    return body


def pick_seat(detail: dict[str, Any], pref: str = "middle") -> dict[str, int | str]:
    """Pick the first available General-zone seat from ``statusRoom``.

    ``pref="middle"`` favors rows D/E/F/G (FilaRelativa). ``pref="any"`` picks
    the first available. We restrict to ``TipoZona == "GENERAL"`` so the
    default price code (103) is always zone-compatible — Procinal rejects
    reservations where tarifa-zone ≠ seat-zone with SP00039.

    Returns a chair dict ready for the reservation/payment payload:
    ``{Fila, Columna, FilRelativa, ColRelativa, Tarifa}``.
    """
    map_room = detail["mapRoom"]
    status = detail["statusRoom"]

    # Build a lookup: (FilaRelativa, ColumnaRelativa) -> mapRoom index, but only
    # for General/GENERAL seats. Pasillos and GENERAL+ are excluded.
    n = len(map_room["FilaTotal"])
    general_idx: dict[tuple[str, int], int] = {}
    for i in range(n):
        if (
            map_room["TipoSilla"][i] == "General"
            and map_room["TipoZona"][i] == "GENERAL"
        ):
            key = (map_room["FilaRelativa"][i], map_room["ColumnaRelativa"][i])
            general_idx[key] = i

    middle_rows = {"D", "E", "F", "G"} if pref == "middle" else None
    target_idx: int | None = None

    def _scan(rows_filter: set[str] | None) -> int | None:
        for row in status:
            if rows_filter is not None and row.get("filRel") not in rows_filter:
                continue
            for s in row.get("DescripcionSilla", []):
                if s.get("TipoSilla") != "General" or s.get("EstadoSilla") != "S":
                    continue
                key = (row["filRel"], s["Columna"])
                if key in general_idx:
                    return general_idx[key]
        return None

    if middle_rows:
        target_idx = _scan(middle_rows)
    if target_idx is None:
        target_idx = _scan(None)

    if target_idx is None:
        raise RuntimeError("No available General-zone seats in this showtime")

    return {
        "Fila": map_room["FilaTotal"][target_idx],
        "Columna": map_room["ColumnaTotal"][target_idx],
        "FilRelativa": map_room["FilaRelativa"][target_idx],
        "ColRelativa": map_room["ColumnaRelativa"][target_idx],
        "Tarifa": DEFAULT_PRICE_CODE,
    }


def build_reservation_body(
    showtime_id: int,
    chair: dict[str, Any],
    detail: dict[str, Any],
    price_code: int = DEFAULT_PRICE_CODE,
) -> dict[str, Any]:
    """Construct the body shared by ``/auth/payment/reservation`` and
    ``/auth/payment/card`` — Procinal expects identical seat/score data on both.
    """
    # Find the matching price entry
    price_entry = next(
        (p for p in detail["prices"] if p["codigo"] == price_code),
        detail["prices"][0],
    )
    price_val = price_entry["valor"]
    internet_fee = detail["bill"][0]["Recargo_Venta_Internet"]
    secuencia = detail["bill"][0]["Secuencia"]
    total = price_val + internet_fee

    return {
        "showtime": showtime_id,
        "chairs": [chair],
        "products": [],
        "products_bepass": [],
        "description": "",
        "total": total,
        "total_transaction": total,
        "subtotal": price_val,
        "cash_payment": 0,
        "score_bill": secuencia,
        "is_member": False,
    }


# ---- Reservation + payment ---------------------------------------------

async def reserve(body: dict[str, Any]) -> dict[str, Any]:
    code, resp = await _request("POST", "/api/auth/payment/reservation", json=body, auth=True)
    if code != 200:
        raise RuntimeError(f"reserve HTTP {code}: {resp}")
    return resp


@dataclass
class CardData:
    number: str
    exp_month: str          # "MM"
    exp_year: str           # "YYYY"
    cvc: str
    dues: str = "1"

    @classmethod
    def from_settings(cls) -> "CardData":
        s = get_settings()
        if not all([s.procinal_card_number, s.procinal_card_exp_month,
                    s.procinal_card_exp_year, s.procinal_card_cvc]):
            raise RuntimeError(
                "PROCINAL_CARD_NUMBER/EXP_MONTH/EXP_YEAR/CVC must all be set in .env"
            )
        return cls(
            number=s.procinal_card_number,
            exp_month=s.procinal_card_exp_month,
            exp_year=s.procinal_card_exp_year,
            cvc=s.procinal_card_cvc,
        )


async def pay_with_card(reservation_body: dict[str, Any], card: CardData) -> dict[str, Any]:
    """Direct ePayco card charge.

    Procinal returns 200 on success and a non-200 (commonly 403/401) on issuer
    rejection — but the ``pay.data.estado`` field in either case carries the
    real result. We don't raise on non-200; we let the caller inspect.
    """
    body = {
        **reservation_body,
        "payment_type": 1,
        "card_number": card.number,
        "exp_month": card.exp_month,
        "exp_year": card.exp_year,
        "cvc": card.cvc,
        "dues": card.dues,
    }
    code, resp = await _request("POST", "/api/auth/payment/card", json=body, auth=True)
    return {"http_status": code, **resp}


async def pay_with_inswitch_hosted(reservation_body: dict[str, Any]) -> dict[str, Any]:
    """Returns ``{success, data:{factura, pse_url, ...}}`` — 3DS-safe fallback.

    Use this if direct card charge keeps hitting 3DS or merchant blocks. The
    caller hands ``data.pse_url`` to the user (e.g. via WhatsApp CTA).
    """
    body = {**reservation_body, "payment_type": 1}
    code, resp = await _request(
        "POST", "/api/auth/v1/inswitch/pay-with-card", json=body, auth=True
    )
    if code != 200:
        raise RuntimeError(f"pay_with_inswitch_hosted HTTP {code}: {resp}")
    return resp
