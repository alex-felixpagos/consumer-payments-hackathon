"""
Mock competitor quotes per corridor (hackathon / demo).

Each entry uses the same convention as Felix: estimated local received =
(max(0, amount_usd - fee_usd)) * fx_rate.

Replace with live provider data in production.
"""

from typing import TypedDict


class CompetitorQuote(TypedDict):
    name: str
    fee_usd: float
    fx_rate: float


# Canonical country keys must match FELIX_CORRIDORS.
COMPETITORS: dict[str, list[CompetitorQuote]] = {
    "Mexico": [
        {"name": "Remitly", "fee_usd": 3.99, "fx_rate": 16.72},
        {"name": "Wise", "fee_usd": 4.29, "fx_rate": 16.78},
    ],
    "Guatemala": [
        {"name": "Remitly", "fee_usd": 3.99, "fx_rate": 7.65},
        {"name": "Western Union", "fee_usd": 4.99, "fx_rate": 7.70},
    ],
    "Colombia": [
        # Stronger than mock Felix on common send sizes — triggers price match.
        {"name": "Remitly", "fee_usd": 3.99, "fx_rate": 3950.0},
        {"name": "Wise", "fee_usd": 4.99, "fx_rate": 3920.0},
    ],
    "El Salvador": [
        {"name": "Remitly", "fee_usd": 1.99, "fx_rate": 1.0},
    ],
    "Honduras": [
        {"name": "Remitly", "fee_usd": 3.99, "fx_rate": 24.5},
        {"name": "Wise", "fee_usd": 4.49, "fx_rate": 24.55},
    ],
}
