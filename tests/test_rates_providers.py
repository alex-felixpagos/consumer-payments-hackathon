"""Tests for FX rate providers and the multi-provider aggregator."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.services import rates_providers
from app.services.rates_providers import (
    ExchangeRateApiProvider,
    FxProvider,
    OpenErApiProvider,
    fetch_all_quotes,
)
from app.services.rates_providers.base import FxProviderResult


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Provider-level tests
# ---------------------------------------------------------------------------


class TestOpenErApiProvider:
    SAMPLE: dict[str, Any] = {
        "result": "success",
        "base_code": "USD",
        "rates": {"USD": 1.0, "MXN": 17.05, "COP": 3925.4},
    }

    def test_fetch_returns_rates(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "open.er-api.com"
            return httpx.Response(200, json=self.SAMPLE)

        async def run() -> FxProviderResult:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as c:
                return await OpenErApiProvider().fetch_result(client=c)

        result = asyncio.run(run())

        assert result.provider == "open.er-api"
        assert result.base == "USD"
        assert result.rates["MXN"] == pytest.approx(17.05)
        assert result.source_url == "https://open.er-api.com"

    def test_raises_on_http_error(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        async def run() -> None:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as c:
                await OpenErApiProvider().fetch_result(client=c)

        with pytest.raises(httpx.HTTPError):
            asyncio.run(run())

    def test_raises_value_error_on_malformed_payload(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": "error"})

        async def run() -> None:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as c:
                await OpenErApiProvider().fetch_result(client=c)

        with pytest.raises(ValueError):
            asyncio.run(run())


class TestExchangeRateApiProvider:
    SAMPLE: dict[str, Any] = {
        "base": "USD",
        "date": "2026-05-06",
        "rates": {"USD": 1.0, "MXN": 17.10, "BRL": 5.15},
    }

    def test_fetch_returns_rates(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "api.exchangerate-api.com"
            return httpx.Response(200, json=self.SAMPLE)

        async def run() -> FxProviderResult:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as c:
                return await ExchangeRateApiProvider().fetch_result(client=c)

        result = asyncio.run(run())

        assert result.provider == "exchangerate-api"
        assert result.rates["BRL"] == pytest.approx(5.15)

    def test_raises_value_error_on_malformed_payload(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": True})

        async def run() -> None:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as c:
                await ExchangeRateApiProvider().fetch_result(client=c)

        with pytest.raises(ValueError):
            asyncio.run(run())


# ---------------------------------------------------------------------------
# Aggregator tests
# ---------------------------------------------------------------------------


class _StaticProvider(FxProvider):
    """Test double — returns canned rates without any HTTP."""

    def __init__(
        self, name: str, rates: dict[str, float], should_fail: Exception | None = None
    ) -> None:
        self.name = name
        self.source_url = f"https://example.test/{name}"
        self.base = "USD"
        self._rates = rates
        self._should_fail = should_fail

    async def fetch(self, client: httpx.AsyncClient) -> dict[str, float]:
        if self._should_fail is not None:
            raise self._should_fail
        return dict(self._rates)


class TestFetchAllQuotes:
    def test_aggregates_all_successful_providers(self) -> None:
        providers = [
            _StaticProvider("alpha", {"MXN": 17.0}),
            _StaticProvider("beta", {"MXN": 17.5}),
        ]
        results = asyncio.run(fetch_all_quotes(providers=providers))

        assert [r.provider for r in results] == ["alpha", "beta"]
        assert results[0].rates["MXN"] == 17.0
        assert results[1].rates["MXN"] == 17.5

    def test_drops_failing_providers_silently(self) -> None:
        providers = [
            _StaticProvider("alpha", {"MXN": 17.0}),
            _StaticProvider(
                "broken", {}, should_fail=httpx.ConnectError("nope")
            ),
            _StaticProvider("gamma", {"MXN": 17.2}),
        ]
        results = asyncio.run(fetch_all_quotes(providers=providers))

        assert [r.provider for r in results] == ["alpha", "gamma"]

    def test_returns_empty_list_when_all_fail(self) -> None:
        providers = [
            _StaticProvider("a", {}, should_fail=httpx.ConnectError("nope")),
            _StaticProvider("b", {}, should_fail=ValueError("malformed")),
        ]
        results = asyncio.run(fetch_all_quotes(providers=providers))

        assert results == []

    def test_default_uses_module_providers_list(self) -> None:
        assert isinstance(rates_providers.PROVIDERS, list)
        assert len(rates_providers.PROVIDERS) >= 2
        assert all(isinstance(p, FxProvider) for p in rates_providers.PROVIDERS)
