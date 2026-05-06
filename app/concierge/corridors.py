"""Mock Felix corridor data. Replace with a real source when wiring production."""

import math
import random
from typing import TypedDict


class Corridor(TypedDict):
    currency: str
    fx_rate: float
    fee_usd: float
    methods: list[str]
    typical_speed: dict[str, str]
    fx_history: list[float]


def _generate_fx_history(
    *, today_rate: float, days: int, drift_pct: float, noise_pct: float, seed: int
) -> list[float]:
    """
    Generate a deterministic ~30-day daily FX series ending at `today_rate`.

    drift_pct: total drift over the window (e.g. +0.012 = ended ~1.2% above the start).
    noise_pct: stddev of daily noise as fraction of rate (e.g. 0.003 = 0.3% daily).

    Reproducible per corridor via `seed`. The last element equals today_rate exactly.
    """
    rng = random.Random(seed)
    start = today_rate / (1.0 + drift_pct)
    series: list[float] = []
    for i in range(days):
        t = i / max(1, days - 1)
        # base drift + light sinusoidal swing + per-day gaussian noise
        base = start * (1.0 + drift_pct * t)
        swing = 1.0 + 0.004 * math.sin(2 * math.pi * t * 1.5)  # one-and-a-half mild waves
        noise = 1.0 + rng.gauss(0.0, noise_pct)
        series.append(base * swing * noise)
    series[-1] = today_rate  # anchor the last point to today's quoted rate
    return [round(v, 4) for v in series]


_FX_DAYS = 30


def _build_corridors() -> dict[str, Corridor]:
    return {
        "Mexico": {
            "currency": "MXN",
            "fx_rate": 16.9,
            "fee_usd": 2.99,
            "methods": ["cash_pickup", "bank_deposit"],
            "typical_speed": {"cash_pickup": "minutes", "bank_deposit": "same day"},
            "fx_history": _generate_fx_history(
                today_rate=16.9, days=_FX_DAYS, drift_pct=0.012, noise_pct=0.003, seed=11
            ),
        },
        "Guatemala": {
            "currency": "GTQ",
            "fx_rate": 7.78,
            "fee_usd": 3.49,
            "methods": ["cash_pickup", "bank_deposit"],
            "typical_speed": {"cash_pickup": "minutes", "bank_deposit": "same day"},
            "fx_history": _generate_fx_history(
                today_rate=7.78, days=_FX_DAYS, drift_pct=0.005, noise_pct=0.0015, seed=22
            ),
        },
        "Colombia": {
            "currency": "COP",
            "fx_rate": 3900.0,
            "fee_usd": 4.99,
            "methods": ["bank_deposit", "mobile_wallet"],
            "typical_speed": {"bank_deposit": "same day", "mobile_wallet": "minutes"},
            "fx_history": _generate_fx_history(
                today_rate=3900.0, days=_FX_DAYS, drift_pct=0.018, noise_pct=0.004, seed=33
            ),
        },
        "El Salvador": {
            "currency": "USD",
            "fx_rate": 1.0,
            "fee_usd": 2.99,
            "methods": ["bank_deposit", "cash_pickup"],
            "typical_speed": {"bank_deposit": "same day", "cash_pickup": "minutes"},
            "fx_history": [1.0] * _FX_DAYS,  # USD-pegged corridor: flat
        },
        "Honduras": {
            "currency": "HNL",
            "fx_rate": 24.7,
            "fee_usd": 3.99,
            "methods": ["cash_pickup", "bank_deposit"],
            "typical_speed": {"cash_pickup": "minutes", "bank_deposit": "same day"},
            "fx_history": _generate_fx_history(
                today_rate=24.7, days=_FX_DAYS, drift_pct=0.008, noise_pct=0.002, seed=44
            ),
        },
    }


FELIX_CORRIDORS: dict[str, Corridor] = _build_corridors()


COUNTRY_ALIASES: dict[str, str] = {
    "mx": "Mexico",
    "mexico": "Mexico",
    "méxico": "Mexico",
    "gt": "Guatemala",
    "guatemala": "Guatemala",
    "co": "Colombia",
    "colombia": "Colombia",
    "sv": "El Salvador",
    "el salvador": "El Salvador",
    "salvador": "El Salvador",
    "hn": "Honduras",
    "honduras": "Honduras",
}


def resolve_country(name: str) -> str | None:
    """Map free-form country text to a canonical key, else None."""
    if not name:
        return None
    return COUNTRY_ALIASES.get(name.strip().lower())
