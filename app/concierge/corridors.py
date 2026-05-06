"""Mock Felix corridor data. Replace with a real source when wiring production."""

from typing import TypedDict


class Corridor(TypedDict):
    currency: str
    fx_rate: float
    fee_usd: float
    methods: list[str]
    typical_speed: dict[str, str]
    fx_history: list[float]


FELIX_CORRIDORS: dict[str, Corridor] = {
    "Mexico": {
        "currency": "MXN",
        "fx_rate": 16.9,
        "fee_usd": 2.99,
        "methods": ["cash_pickup", "bank_deposit"],
        "typical_speed": {
            "cash_pickup": "minutes",
            "bank_deposit": "same day",
        },
        "fx_history": [16.75, 16.80, 16.82, 16.88, 16.90],
    },
    "Guatemala": {
        "currency": "GTQ",
        "fx_rate": 7.78,
        "fee_usd": 3.49,
        "methods": ["cash_pickup", "bank_deposit"],
        "typical_speed": {
            "cash_pickup": "minutes",
            "bank_deposit": "same day",
        },
        "fx_history": [7.74, 7.76, 7.77, 7.78, 7.78],
    },
    "Colombia": {
        "currency": "COP",
        "fx_rate": 3900.0,
        "fee_usd": 4.99,
        "methods": ["bank_deposit", "mobile_wallet"],
        "typical_speed": {
            "bank_deposit": "same day",
            "mobile_wallet": "minutes",
        },
        "fx_history": [3840, 3865, 3880, 3890, 3900],
    },
    "El Salvador": {
        "currency": "USD",
        "fx_rate": 1.0,
        "fee_usd": 2.99,
        "methods": ["bank_deposit", "cash_pickup"],
        "typical_speed": {
            "bank_deposit": "same day",
            "cash_pickup": "minutes",
        },
        "fx_history": [1.0, 1.0, 1.0, 1.0, 1.0],
    },
    "Honduras": {
        "currency": "HNL",
        "fx_rate": 24.7,
        "fee_usd": 3.99,
        "methods": ["cash_pickup", "bank_deposit"],
        "typical_speed": {
            "cash_pickup": "minutes",
            "bank_deposit": "same day",
        },
        "fx_history": [24.55, 24.60, 24.65, 24.68, 24.70],
    },
}


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
