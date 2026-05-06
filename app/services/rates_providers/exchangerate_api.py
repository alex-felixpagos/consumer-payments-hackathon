"""exchangerate-api.com v4 — free, key-less USD-base FX rates.

Endpoint: ``GET https://api.exchangerate-api.com/v4/latest/USD``.
Payload shape: ``{"base": "USD", "rates": {"MXN": 17.05, ...}, ...}``.

This is intentionally a separate, independent source from ``open.er-api``
so the bot can show side-by-side quotes from two distinct upstreams.
"""

from typing import Any

import httpx

from .base import FxProvider


class ExchangeRateApiProvider(FxProvider):
    name = "exchangerate-api"
    source_url = "https://www.exchangerate-api.com"
    base = "USD"

    URL = "https://api.exchangerate-api.com/v4/latest/USD"

    async def fetch(self, client: httpx.AsyncClient) -> dict[str, float]:
        response = await client.get(self.URL)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if "rates" not in data:
            raise ValueError(f"Unexpected exchangerate-api payload: {data!r}")

        rates = data["rates"]
        if not isinstance(rates, dict):
            raise ValueError("rates payload is not a dict")
        return {code: float(value) for code, value in rates.items()}
