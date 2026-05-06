"""30-day FX intelligence + chart URL."""

from app.concierge import tools
from app.concierge.corridors import FELIX_CORRIDORS


def test_each_corridor_has_thirty_day_history() -> None:
    for country, data in FELIX_CORRIDORS.items():
        assert len(data["fx_history"]) == 30, country
        assert data["fx_history"][-1] == data["fx_rate"], country


def test_assess_fx_window_returns_verdict_and_band() -> None:
    result = tools.assess_fx_window(country="Mexico", amount_usd=200)
    assert result["verdict"] in {
        "great_time",
        "decent",
        "neutral",
        "low_end",
        "wait_if_possible",
    }
    assert 0 <= result["percentile_in_30d"] <= 1
    assert result["thirty_day_low"] <= result["today_rate"] <= result["thirty_day_high"]
    assert result["week_direction"] in {"up", "down", "flat"}


def test_assess_fx_window_unknown_country() -> None:
    result = tools.assess_fx_window(country="Atlantis", amount_usd=200)
    assert "error" in result


def test_render_fx_chart_returns_quickchart_url() -> None:
    result = tools.render_fx_chart(country="Mexico")
    assert result["url"].startswith("https://quickchart.io/chart?")
    assert "MXN" in result["caption"]


def test_render_fx_chart_url_is_within_get_size() -> None:
    """quickchart GET URLs must stay well under 6KB."""
    result = tools.render_fx_chart(country="Colombia")
    assert len(result["url"]) < 6000


def test_render_fx_chart_unknown_country() -> None:
    result = tools.render_fx_chart(country="Atlantis")
    assert "error" in result


def test_render_fx_chart_marked_as_media_producing() -> None:
    assert "render_fx_chart" in tools.MEDIA_PRODUCING_TOOLS


def test_run_tool_render_fx_chart_dispatch() -> None:
    result = tools.run_tool("render_fx_chart", {"country": "Mexico"})
    assert "url" in result
