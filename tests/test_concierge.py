"""Unit tests for the concierge tools — deterministic, no LLM calls."""

from app.concierge import tools
from app.concierge.corridors import FELIX_CORRIDORS, resolve_country


def test_supported_countries_match_corridors() -> None:
    result = tools.list_supported_countries()
    assert set(result["countries"]) == set(FELIX_CORRIDORS.keys())


def test_resolve_country_aliases() -> None:
    assert resolve_country("mx") == "Mexico"
    assert resolve_country("MEXICO") == "Mexico"
    assert resolve_country("colombia") == "Colombia"
    assert resolve_country("nowhere") is None


def test_get_corridor_returns_methods_and_fx() -> None:
    result = tools.get_corridor("Mexico")
    assert result["currency"] == "MXN"
    assert "cash_pickup" in result["methods"]
    assert result["fx_rate"] > 0


def test_get_corridor_unknown_country_returns_error() -> None:
    result = tools.get_corridor("Atlantis")
    assert "error" in result


def test_calculate_payout_uses_fee_and_rate() -> None:
    result = tools.calculate_payout(country="Mexico", amount_usd=200, method="cash_pickup")
    fee = FELIX_CORRIDORS["Mexico"]["fee_usd"]
    rate = FELIX_CORRIDORS["Mexico"]["fx_rate"]
    assert result["estimated_received"] == round((200 - fee) * rate, 2)
    assert result["currency"] == "MXN"
    assert result["match_applied"] is False
    assert result["fx_rate_base"] == rate
    assert result["fx_rate_applied"] == result["fx_rate_base"]


def test_calculate_payout_rejects_unsupported_method() -> None:
    result = tools.calculate_payout(
        country="Colombia", amount_usd=300, method="cash_pickup"
    )
    assert "error" in result
    assert "available_methods" in result


def test_fx_trend_reports_direction_and_impact() -> None:
    result = tools.get_fx_trend(country="Mexico", amount_usd=200)
    assert "pct_change_5d" in result
    assert "direction" in result
    assert "suggestion" in result


def test_run_tool_dispatches_by_name() -> None:
    result = tools.run_tool("get_corridor", {"country": "Mexico"})
    assert result["currency"] == "MXN"


def test_run_tool_unknown_returns_error() -> None:
    result = tools.run_tool("not_a_tool", {})
    assert "error" in result
