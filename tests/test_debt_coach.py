"""Unit tests for debt coach foundations (no HTTP)."""

import pytest

from app import debt_coach as dc


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    dc.clear_all_sessions_for_tests()
    yield
    dc.clear_all_sessions_for_tests()


def test_parse_command_exact() -> None:
    assert dc.parse_command("  START ") == "start"
    assert dc.parse_command("start") == "start"
    assert dc.parse_command("menu") == "menu"
    assert dc.parse_command("help principal") == "help principal"
    assert dc.parse_command("demo shortfall") == "demo shortfall"


def test_parse_command_natural_shortfall_phrase() -> None:
    assert dc.parse_command("I can't cover principal") == "help principal"
    assert dc.parse_command("Can you help with principal?") == "help principal"


def test_parse_budget_triple() -> None:
    t = dc.parse_budget_triple("Income 3000, essentials 1800, flexible 500")
    assert t == (3000.0, 1800.0, 500.0)


def test_parse_money_and_rest() -> None:
    amt, due = dc._parse_money_and_rest("$450 due May 15")
    assert amt == 450.0
    assert due == "May 15"


def test_happy_path_build_reply() -> None:
    phone = "+10000000001"
    assert "plan a debt payment" in dc.build_reply(phone, "start").lower()
    assert dc.build_reply(phone, "Credit card").startswith("Thanks")
    body = dc.build_reply(phone, "$450 due May 15")
    assert "3000" in body or "income" in body.lower()
    final = dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    assert "payment plan is ready" in final.lower()
    assert "simulated envelope" in final.lower()
    assert "type **envelope**" not in final


def test_budget_summary_response_has_reminder_button() -> None:
    phone = "+10000000004"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")

    response = dc.build_response(phone, "Income 3000, essentials 1800, flexible 500")

    assert response.buttons == (dc.ReplyButton(id="reminder", title="Show reminder"),)
    assert "Next, I can show the day-before payment reminder." in response.body


def test_show_reminder_button_title_routes_to_reminder() -> None:
    assert dc.parse_command("Show reminder") == "reminder"


def test_help_principal_demo_shortfall() -> None:
    phone = "+10000000002"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    dc.build_reply(phone, "demo shortfall")
    out = dc.build_reply(phone, "help principal")
    assert "120" in out
    assert "general options" in out.lower()
    assert "lender terms" in out.lower()


def test_natural_shortfall_phrase_routes_to_help_principal() -> None:
    phone = "+10000000003"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    dc.build_reply(phone, "demo shortfall")

    out = dc.build_reply(phone, "I can't cover principal")

    assert "120" in out
    assert "general options" in out.lower()
