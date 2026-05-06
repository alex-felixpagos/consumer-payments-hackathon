"""Unit tests for debt coach foundations (no HTTP)."""

import pytest

from app import debt_coach as dc


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    dc.clear_all_sessions_for_tests()
    yield
    dc.clear_all_sessions_for_tests()


def test_map_intent_label_to_command() -> None:
    assert dc.map_intent_label_to_command("unknown") is None
    assert dc.map_intent_label_to_command("") is None
    assert dc.map_intent_label_to_command("help_principal") == "help principal"
    assert dc.map_intent_label_to_command("demo_shortfall") == "demo shortfall"
    assert dc.map_intent_label_to_command("envelope") == "envelope"


def test_build_outbound_resolved_command_used_when_parse_fails() -> None:
    phone = "+10000000008"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    # "show my savings" is not a literal command; simulates LLM resolving to envelope.
    out = dc.build_outbound(phone, "show my savings", resolved_command="envelope")
    assert "simulated payment envelope" in out.text.lower()


def test_parse_command_exact() -> None:
    assert dc.parse_command("  START ") == "start"
    assert dc.parse_command("start") == "start"
    assert dc.parse_command("hello") == "hello"
    assert dc.parse_command("HELLO") == "hello"
    assert dc.parse_command("menu") == "menu"
    assert dc.parse_command("help_principal") == "help principal"
    assert dc.parse_command("help principal") == "help principal"
    assert dc.parse_command("demo shortfall") == "demo shortfall"


def test_parse_command_natural_shortfall_phrase() -> None:
    assert dc.parse_command("I can't cover principal") == "help principal"
    assert dc.parse_command("Can you help with principal?") == "help principal"


def test_parse_budget_triple() -> None:
    t = dc.parse_budget_triple("Income 3000, essentials 1800, flexible 500")
    assert t == (3000.0, 1800.0, 500.0)


def test_parse_first_amount() -> None:
    assert dc.parse_first_amount("3000") == 3000.0
    assert dc.parse_first_amount("$3,000.50") == 3000.50
    assert dc.parse_first_amount("about 4200 per month") == 4200.0
    assert dc.parse_first_amount("no numbers") is None


def test_parse_money_and_rest() -> None:
    amt, due = dc._parse_money_and_rest("$450 due May 15")
    assert amt == 450.0
    assert due == "May 15"


def test_happy_path_build_reply() -> None:
    phone = "+10000000001"
    welcome = dc.build_reply(phone, "start").lower()
    assert "debt" in welcome and ("glad" in welcome or "here" in welcome)
    assert dc.build_reply(phone, "Credit card").startswith("Thanks")
    body = dc.build_reply(phone, "$450 due May 15")
    assert "step 1" in body.lower() and "income" in body.lower()
    assert "step 2" in dc.build_reply(phone, "3000").lower()
    assert "step 3" in dc.build_reply(phone, "1800").lower()
    final = dc.build_reply(phone, "500")
    assert "payment plan is ready" in final.lower()
    assert "simulated envelope" in final.lower()


def test_amount_due_split_flow() -> None:
    phone = "+10000000007"
    dc.build_reply(phone, "start")
    after_debt = dc.build_reply(phone, "Credit card")
    assert "step 1 of 2" in after_debt.lower()

    after_amount = dc.build_reply(phone, "450")
    assert "step 2 of 2" in after_amount.lower()

    after_due = dc.build_reply(phone, "May 15")
    assert "step 1 of 3" in after_due.lower() and "income" in after_due.lower()


def test_amount_step_invalid_input_reprompts() -> None:
    phone = "+10000000009"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    out = dc.build_reply(phone, "no number here")
    assert "step 1 of 2" in out.lower()


def test_amount_due_combined_shortcut_still_works() -> None:
    phone = "+10000000010"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    body = dc.build_reply(phone, "$450 due May 15")
    assert "step 1 of 3" in body.lower() and "income" in body.lower()


def test_budget_one_line_shortcut_on_income_step() -> None:
    phone = "+10000000006"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    dc.build_reply(phone, "$450 due May 15")
    final = dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    assert "payment plan is ready" in final.lower()


def test_budget_summary_response_has_next_step_buttons() -> None:
    phone = "+10000000004"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    response = dc.build_response(phone, "500")

    ids = {b.id for b in response.buttons}
    assert ids == {"envelope", "reminder", "help_principal"}
    assert "Tap a button" in response.body or "envelope" in response.body.lower()


def test_show_reminder_button_title_routes_to_reminder() -> None:
    assert dc.parse_command("Show reminder") == "reminder"


def test_welcome_outbound_has_buttons() -> None:
    phone = "+10000000003"
    out = dc.build_outbound(phone, "start")
    assert out.has_buttons
    assert any(b["id"] == "begin" for b in out.buttons)
    assert any(b["id"] == "menu" for b in out.buttons)


def test_hello_same_welcome_as_start() -> None:
    phone = "+10000000005"
    out_hello = dc.build_outbound(phone, "hello")
    dc.clear_all_sessions_for_tests()
    out_start = dc.build_outbound(phone, "start")
    assert out_hello.text == out_start.text
    assert out_hello.buttons == out_start.buttons


def test_begin_tap_nudges_debt_question() -> None:
    phone = "+10000000004"
    dc.build_outbound(phone, "start")
    out = dc.build_outbound(phone, "begin")
    assert "which debt" in out.text.lower()


def test_help_principal_demo_shortfall() -> None:
    phone = "+10000000002"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    dc.build_reply(phone, "500")
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
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    dc.build_reply(phone, "500")
    dc.build_reply(phone, "demo shortfall")

    out = dc.build_reply(phone, "I can't cover principal")

    assert "120" in out
    assert "general options" in out.lower()
