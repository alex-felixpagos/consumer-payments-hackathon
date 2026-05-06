"""open.er-api.com — free, key-less USD-base FX rates.

Docs: https://www.exchangerate-api.com/docs/free
Endpoint shape: ``{"result": "success", "rates": {"MXN": 17.05, ...}}``.
"""

from typing import Any

import httpx

from .base import FxProvider


class OpenErApiProvider(FxProvider):
    name = "open.er-api"
    source_url = "https://open.er-api.com"
    base = "USD"

    URL = "https://open.er-api.com/v6/latest/USD"

    async def fetch(self, client: httpx.AsyncClient) -> dict[str, float]:
        response = await client.get(self.URL)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("result") != "success" or "rates" not in data:
            raise ValueError(f"Unexpected open.er-api payload: {data!r}")

        rates = data["rates"]
        if not isinstance(rates, dict):
            raise ValueError("rates payload is not a dict")
        return {code: float(value) for code, value in rates.items()}
