"""Base types for FX rate providers.

Each provider knows how to fetch USD-base exchange rates from a single
upstream source. Concrete providers subclass :class:`FxProvider` and
override :meth:`fetch`. The orchestration layer (``rates_providers/__init__.py``)
runs every registered provider concurrently and aggregates their results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class FxProviderResult:
    """Successful response from a single FX provider."""

    provider: str
    base: str
    rates: dict[str, float]
    source_url: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FxProvider(ABC):
    """One FX data source. Implementations only need to override :meth:`fetch`."""

    #: Human-readable display name shown to the end user.
    name: str = "fx-provider"

    #: Public-facing source URL for attribution / debugging.
    source_url: str | None = None

    #: Base currency the implementation returns rates against.
    base: str = "USD"

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> dict[str, float]:
        """Return ``{currency_code: rate}`` quoted against :attr:`base`."""

    async def fetch_result(
        self, client: httpx.AsyncClient | None = None
    ) -> FxProviderResult:
        """
        Wrap :meth:`fetch` in an :class:`FxProviderResult`.

        If a shared ``client`` is provided we use it (and don't close it);
        otherwise we create and tear down our own ``httpx.AsyncClient``.
        """
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=10.0)
        try:
            rates = await self.fetch(client)
        finally:
            if owns_client:
                await client.aclose()

        return FxProviderResult(
            provider=self.name,
            base=self.base,
            rates=rates,
            source_url=self.source_url,
        )
