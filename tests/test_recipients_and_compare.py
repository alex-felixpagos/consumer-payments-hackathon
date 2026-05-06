"""Recipient memory + advisory tools."""

import pytest

from app.concierge import recipients as recipients_store
from app.concierge import tools


@pytest.fixture(autouse=True)
def _clean_recipients():
    recipients_store.reset()
    yield
    recipients_store.reset()


def test_save_recipient_persists_and_lists() -> None:
    saved = tools.run_tool(
        "save_recipient",
        {"name": "Maria", "country": "Mexico", "method": "cash_pickup"},
        user_id="+15551234567",
    )
    assert saved["saved"] is True
    listed = tools.run_tool("list_recipients", {}, user_id="+15551234567")
    names = [r["name"] for r in listed["recipients"]]
    assert "Maria" in names


def test_recipient_isolation_between_users() -> None:
    tools.run_tool(
        "save_recipient",
        {"name": "Maria", "country": "Mexico"},
        user_id="+1111",
    )
    listed_other = tools.run_tool("list_recipients", {}, user_id="+2222")
    assert listed_other["recipients"] == []


def test_user_scoped_tool_requires_bound_user_id() -> None:
    result = tools.run_tool("list_recipients", {})
    assert "error" in result


def test_save_recipient_rejects_unsupported_country() -> None:
    result = tools.run_tool(
        "save_recipient",
        {"name": "Ana", "country": "Atlantis"},
        user_id="+1111",
    )
    assert "error" in result


def test_save_recipient_canonicalizes_country() -> None:
    tools.run_tool(
        "save_recipient",
        {"name": "Ana", "country": "mx"},
        user_id="+1111",
    )
    listed = tools.run_tool("list_recipients", {}, user_id="+1111")
    assert listed["recipients"][0]["country"] == "Mexico"


def test_compare_options_returns_grid() -> None:
    result = tools.compare_options(country="Mexico", amount_usd=200)
    assert result["currency"] == "MXN"
    assert "price_match_today" in result
    assert "match_applied" in result["price_match_today"]
    methods = {opt["method"] for opt in result["options"]}
    assert methods == {"cash_pickup", "bank_deposit"}
    for opt in result["options"]:
        assert opt["send_today"] > 0
        assert "send_in_2_days" in opt
        assert "delta_if_wait" in opt
        assert "speed" in opt


def test_compare_options_unknown_country_errors() -> None:
    result = tools.compare_options(country="Atlantis", amount_usd=100)
    assert "error" in result


def test_user_id_not_in_llm_facing_schema() -> None:
    """user_id is injected by the agent, never exposed to the LLM."""
    schemas_by_name = {s["name"]: s for s in tools.TOOL_SCHEMAS}
    for name in tools.USER_SCOPED_TOOLS:
        props = schemas_by_name[name]["input_schema"].get("properties", {})
        assert "user_id" not in props, f"{name} schema must not expose user_id"
