"""Tests for the FX rates service used by inbound message handling."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.services import rates_service


SAMPLE_RATES_PAYLOAD: dict[str, Any] = {
    "result": "success",
    "base_code": "USD",
    "rates": {
        "USD": 1.0,
        "MXN": 17.0512,
        "COP": 3925.4,
        "GTQ": 7.78,
        "HNL": 24.65,
        "DOP": 58.9,
        "BRL": 5.12,
        "ARS": 1000.0,
    },
}


@pytest.fixture(autouse=True)
def _reset_pending_state() -> None:
    """Make sure no test leaks pending-rates flags into others."""
    rates_service._pending_rates.clear()
    yield
    rates_service._pending_rates.clear()


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _stub_fetch(monkeypatch: pytest.MonkeyPatch, rates: dict[str, float]) -> None:
    async def fake_fetch(*_: Any, **__: Any) -> dict[str, float]:
        return rates

    monkeypatch.setattr(rates_service, "fetch_usd_rates", fake_fetch)


def _stub_fetch_error(
    monkeypatch: pytest.MonkeyPatch, exc: Exception | None = None
) -> None:
    async def fake_fetch(*_: Any, **__: Any) -> dict[str, float]:
        raise exc or httpx.ConnectError("network down")

    monkeypatch.setattr(rates_service, "fetch_usd_rates", fake_fetch)


class TestIsRatesRequest:
    @pytest.mark.parametrize(
        "text",
        [
            "rate",
            "What are the rates today?",
            "Quiero saber la tasa",
            "Cuál es el tipo de cambio?",
            "cambio USD MXN",
            "fx please",
            "COTIZACION",
        ],
    )
    def test_matches_known_keywords(self, text: str) -> None:
        assert rates_service.is_rates_request(text) is True

    @pytest.mark.parametrize(
        "text",
        [None, "", "hello there", "send 100 dollars", "transfer money"],
    )
    def test_ignores_unrelated_text(self, text: str | None) -> None:
        assert rates_service.is_rates_request(text) is False


class TestParseCountryAndAmount:
    @pytest.mark.parametrize(
        "text, expected_code, expected_amount",
        [
            ("Mexico 250", "MXN", 250.0),
            ("send 100 to brazil", "BRL", 100.0),
            ("BRL 50.5", "BRL", 50.5),
            ("100,5 mxn", "MXN", 100.5),
            ("$1,000 to colombia", "COP", 1000.0),
            ("República Dominicana 75", "DOP", 75.0),
            ("guatemala", "GTQ", None),
            ("250", None, 250.0),
        ],
    )
    def test_parses_combinations(
        self, text: str, expected_code: str | None, expected_amount: float | None
    ) -> None:
        country, amount = rates_service.parse_country_and_amount(text)
        actual_code = country[0] if country else None
        assert actual_code == expected_code
        if expected_amount is None:
            assert amount is None
        else:
            assert amount == pytest.approx(expected_amount)

    def test_returns_none_for_empty_text(self) -> None:
        assert rates_service.parse_country_and_amount("") == (None, None)
        assert rates_service.parse_country_and_amount(None) == (None, None)


class TestFetchUsdRates:
    def test_returns_rates_dict_on_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "open.er-api.com"
            return httpx.Response(200, json=SAMPLE_RATES_PAYLOAD)

        async def run() -> dict[str, float]:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
                return await rates_service.fetch_usd_rates(client=client)

        rates = asyncio.run(run())

        assert rates["MXN"] == pytest.approx(17.0512)
        assert rates["COP"] == pytest.approx(3925.4)

    def test_raises_on_http_error(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        async def run() -> None:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
                await rates_service.fetch_usd_rates(client=client)

        with pytest.raises(httpx.HTTPError):
            asyncio.run(run())

    def test_raises_value_error_on_malformed_payload(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": "error"})

        async def run() -> None:
            async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
                await rates_service.fetch_usd_rates(client=client)

        with pytest.raises(ValueError):
            asyncio.run(run())


class TestFormatQuoteMessage:
    def test_renders_quote_with_conversion(self) -> None:
        message = rates_service.format_quote_message("Mexico", "MXN", 250.0, 17.0512)
        assert "Mexico" in message
        assert "250.00 USD" in message
        assert "MXN" in message
        # 250 * 17.0512 = 4262.80
        assert "4,262.80" in message


class TestHandleRatesMessage:
    PHONE = "+15551234567"

    def test_initial_request_prompts_for_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, SAMPLE_RATES_PAYLOAD["rates"])

        reply = asyncio.run(rates_service.handle_rates_message(self.PHONE, "rates"))

        assert "country" in reply.lower()
        assert "amount" in reply.lower()
        assert rates_service.is_awaiting_rates_input(self.PHONE) is True

    def test_followup_with_country_and_amount_returns_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, SAMPLE_RATES_PAYLOAD["rates"])
        rates_service._mark_pending(self.PHONE)

        reply = asyncio.run(
            rates_service.handle_rates_message(self.PHONE, "Mexico 250")
        )

        assert "Mexico" in reply
        assert "250.00 USD" in reply
        assert "MXN" in reply
        assert rates_service.is_awaiting_rates_input(self.PHONE) is False

    def test_one_shot_message_with_keyword_country_and_amount(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, SAMPLE_RATES_PAYLOAD["rates"])

        reply = asyncio.run(
            rates_service.handle_rates_message(self.PHONE, "rates Brazil 100")
        )

        assert "Brazil" in reply
        assert "BRL" in reply
        assert rates_service.is_awaiting_rates_input(self.PHONE) is False

    def test_followup_missing_amount_reprompts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, SAMPLE_RATES_PAYLOAD["rates"])
        rates_service._mark_pending(self.PHONE)

        reply = asyncio.run(rates_service.handle_rates_message(self.PHONE, "Mexico"))

        assert "USD" in reply
        assert rates_service.is_awaiting_rates_input(self.PHONE) is True

    def test_followup_missing_country_reprompts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, SAMPLE_RATES_PAYLOAD["rates"])
        rates_service._mark_pending(self.PHONE)

        reply = asyncio.run(rates_service.handle_rates_message(self.PHONE, "250"))

        assert "country" in reply.lower()
        assert rates_service.is_awaiting_rates_input(self.PHONE) is True

    def test_returns_friendly_error_when_fetch_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch_error(monkeypatch)
        rates_service._mark_pending(self.PHONE)

        reply = asyncio.run(
            rates_service.handle_rates_message(self.PHONE, "Mexico 250")
        )

        assert "couldn't fetch" in reply.lower()
        assert rates_service.is_awaiting_rates_input(self.PHONE) is False

    def test_handles_unsupported_currency_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fetch(monkeypatch, {"USD": 1.0})
        rates_service._mark_pending(self.PHONE)

        reply = asyncio.run(
            rates_service.handle_rates_message(self.PHONE, "Mexico 250")
        )

        assert "couldn't find" in reply.lower()
