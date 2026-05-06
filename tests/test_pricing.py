"""Enforced competitor price match on Felix quotes."""

from app.concierge import tools
from app.concierge.corridors import FELIX_CORRIDORS
from app.concierge.pricing import quote_felix_with_match


def test_quote_matches_when_competitor_beats_felix_colombia() -> None:
    amount = 300.0
    canonical = "Colombia"
    q = quote_felix_with_match(canonical, amount)
    assert q["match_applied"] is True
    assert q["matched_to"] == "Remitly"
    felix_only = (amount - FELIX_CORRIDORS[canonical]["fee_usd"]) * FELIX_CORRIDORS[
        canonical
    ]["fx_rate"]
    assert q["felix_base_receive"] == round(felix_only, 2)
    assert q["felix_receive_after_match"] > q["felix_base_receive"]
    assert q["applied_fx_rate"] > FELIX_CORRIDORS[canonical]["fx_rate"]


def test_calculate_payout_reflects_match_colombia() -> None:
    result = tools.calculate_payout(
        country="Colombia", amount_usd=300, method="bank_deposit"
    )
    assert result["match_applied"] is True
    q = quote_felix_with_match("Colombia", 300)
    assert result["estimated_received"] == q["felix_receive_after_match"]


def test_calculate_payout_matches_el_salvador_usd_corridor() -> None:
    result = tools.calculate_payout(
        country="El Salvador", amount_usd=200, method="bank_deposit"
    )
    assert result["match_applied"] is True
    assert result["estimated_received"] == 198.01


def test_compare_providers_surfaces_competitors() -> None:
    out = tools.compare_providers("Mexico", 200)
    assert out["country"] == "Mexico"
    assert len(out["competitors"]) >= 2
    assert out["match_applied"] is False


def test_compare_options_includes_price_match_metadata() -> None:
    result = tools.compare_options("Colombia", amount_usd=300)
    assert result["price_match_today"]["match_applied"] is True
    assert result["price_match_today"]["matched_to"] == "Remitly"
