"""FX rate providers and aggregation helpers.

Add a new provider in three steps:

1. Create ``app/services/rates_providers/<your_provider>.py`` and subclass
   :class:`FxProvider`.
2. Import it here.
3. Append an instance to :data:`PROVIDERS` below.

``fetch_all_quotes`` runs every provider concurrently and discards
individual failures so a flaky upstream doesn't block the rest.
"""

import asyncio
import logging

import httpx

from .base import FxProvider, FxProviderResult
from .exchangerate_api import ExchangeRateApiProvider
from .open_er_api import OpenErApiProvider

logger = logging.getLogger(__name__)

# Order matters: results are returned (and rendered) in this order.
PROVIDERS: list[FxProvider] = [
    OpenErApiProvider(),
    ExchangeRateApiProvider(),
]


async def fetch_all_quotes(
    providers: list[FxProvider] | None = None,
) -> list[FxProviderResult]:
    """
    Query every provider concurrently. Failures are logged, not raised.

    Returns successful results in the same order as the input ``providers``
    list (or :data:`PROVIDERS` when omitted), with failed providers
    silently dropped.
    """
    chosen = providers if providers is not None else PROVIDERS

    async def safe_fetch(provider: FxProvider) -> FxProviderResult | None:
        try:
            return await provider.fetch_result()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("FX provider %s failed: %s", provider.name, exc)
            return None

    results = await asyncio.gather(*(safe_fetch(p) for p in chosen))
    return [r for r in results if r is not None]


__all__ = [
    "ExchangeRateApiProvider",
    "FxProvider",
    "FxProviderResult",
    "OpenErApiProvider",
    "PROVIDERS",
    "fetch_all_quotes",
]
