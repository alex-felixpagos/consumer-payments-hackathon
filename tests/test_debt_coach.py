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
    assert dc.map_intent_label_to_command("wallet") == "envelope"


def test_build_outbound_resolved_command_used_when_parse_fails() -> None:
    phone = "+10000000008"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    # "show my savings" is not a literal command; stands in for LLM resolving to wallet/envelope.
    out = dc.build_outbound(phone, "show my savings", resolved_command="envelope")
    assert "send to wallet" in out.text.lower()
    assert "lined up" in out.text.lower()


def test_parse_command_help_principal_suggestion_buttons() -> None:
    assert dc.parse_command("hp_reduce_flex") == "hp_reduce_flex"
    assert dc.parse_command("hp_lender_terms") == "hp_lender_terms"
    assert dc.parse_command("hp_minimum_pay") == "hp_minimum_pay"


def test_parse_command_exact() -> None:
    assert dc.parse_command("  START ") == "start"
    assert dc.parse_command("start") == "start"
    assert dc.parse_command("hello") == "hello"
    assert dc.parse_command("HELLO") == "hello"
    assert dc.parse_command("menu") == "menu"
    assert dc.parse_command("wallet") == "envelope"
    assert dc.parse_command("m_wallet") == "envelope"
    assert dc.parse_command("m_budget") == "budget"
    assert dc.parse_command("m_help_principal") == "help principal"
    assert dc.parse_command("help_principal") == "help principal"
    assert dc.parse_command("help principal") == "help principal"
    assert dc.parse_command("im_short") == "im short"
    assert dc.parse_command("I'm short") == "im short"
    assert dc.parse_command("demo shortfall") == "demo shortfall"


def test_parse_command_natural_shortfall_phrase() -> None:
    assert dc.parse_command("I can't cover principal") == "im short"
    assert dc.parse_command("Can you help with principal?") == "im short"


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
    assert "monthly income" in body.lower()
    assert "essentials" in dc.build_reply(phone, "3000").lower()
    assert "flexible spending" in dc.build_reply(phone, "1800").lower()
    final = dc.build_reply(phone, "500")
    assert "payment plan is ready" in final.lower()
    assert "send to wallet" in final.lower()


def test_amount_due_split_flow() -> None:
    phone = "+10000000007"
    dc.build_reply(phone, "start")
    after_debt = dc.build_reply(phone, "Credit card")
    assert "how much do you need to pay" in after_debt.lower()

    after_amount = dc.build_reply(phone, "450")
    assert "when is it due" in after_amount.lower()

    after_due = dc.build_reply(phone, "May 15")
    assert "monthly income" in after_due.lower()


def test_amount_step_invalid_input_reprompts() -> None:
    phone = "+10000000009"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    out = dc.build_reply(phone, "no number here")
    assert "how much do you need to pay" in out.lower()


def test_amount_due_combined_shortcut_still_works() -> None:
    phone = "+10000000010"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    body = dc.build_reply(phone, "$450 due May 15")
    assert "monthly income" in body.lower()


def test_budget_one_line_shortcut_on_income_step() -> None:
    phone = "+10000000006"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Card")
    dc.build_reply(phone, "$450 due May 15")
    final = dc.build_reply(phone, "Income 3000, essentials 1800, flexible 500")
    assert "payment plan is ready" in final.lower()


def test_budget_summary_response_has_action_buttons() -> None:
    phone = "+10000000004"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    response = dc.build_response(phone, "500")

    ids = {b.id for b in response.buttons}
    assert ids == {"reminder", "wallet"}
    assert response.buttons == (
        dc.ReplyButton(id="reminder", title="Set reminder"),
        dc.ReplyButton(id="wallet", title="Send to wallet"),
    )
    assert "Tap a button" in response.body
    assert "send to wallet" in response.body.lower()


def test_budget_summary_when_tight_shows_reminder_and_im_short() -> None:
    phone = "+10000000014"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "2000")
    response = dc.build_response(phone, "900")

    assert {b.id for b in response.buttons} == {"reminder", "im_short"}
    assert "that is tight" in response.body.lower()
    assert "i'm short" in response.body.lower()


def test_set_reminder_phrase_routes_to_reminder() -> None:
    assert dc.parse_command("Set reminder") == "reminder"
    assert dc.parse_command("Show reminder") == "reminder"


def test_reminder_mentions_im_short() -> None:
    phone = "+10000000011"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")

    out = dc.build_reply(phone, "reminder")

    assert "one day before" in out.lower()
    assert "may 15" in out.lower()
    assert "If covering principal is stressful" in out
    assert "I'm short" in out


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
    response = dc.build_response(phone, "help principal")
    out = response.body
    assert "120" in out
    assert "three general directions" in out.lower()
    assert "lender terms" in out.lower()
    ids = {b.id for b in response.buttons}
    assert ids == {"hp_reduce_flex", "hp_lender_terms", "hp_minimum_pay"}


def test_im_short_uses_demo_shortfall_when_happy_path_has_no_gap() -> None:
    phone = "+10000000012"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    dc.build_reply(phone, "500")

    response = dc.build_response(phone, "I'm short")

    assert "120" in response.body
    assert "three general directions" in response.body.lower()
    assert {b.id for b in response.buttons} == {
        "hp_reduce_flex",
        "hp_lender_terms",
        "hp_minimum_pay",
    }


def test_help_principal_reduce_flexible_reopens_flexible_step() -> None:
    phone = "+10000000013"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    dc.build_reply(phone, "500")
    dc.build_reply(phone, "demo shortfall")
    dc.build_response(phone, "help principal")
    flex_prompt = dc.build_reply(phone, "hp_reduce_flex")
    assert "flexible spending" in flex_prompt.lower()
    assert dc.get_session(phone).step == dc.CoachStep.WAITING_BUDGET_FLEXIBLE
    summary = dc.build_reply(phone, "350")
    assert "payment plan is ready" in summary.lower()


def test_natural_shortfall_phrase_routes_to_help_principal() -> None:
    phone = "+10000000003"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")
    dc.build_reply(phone, "3000")
    dc.build_reply(phone, "1800")
    dc.build_reply(phone, "500")
    dc.build_reply(phone, "demo shortfall")

    response = dc.build_response(phone, "I can't cover principal")

    assert "120" in response.body
    assert "three general directions" in response.body.lower()
    assert {b.id for b in response.buttons} == {
        "hp_reduce_flex",
        "hp_lender_terms",
        "hp_minimum_pay",
    }


def test_menu_command_returns_interactive_list_idle_state() -> None:
    """With no goal yet, menu only shows start, set-goal, demo-shortfall."""
    phone = "+10000000009"
    out = dc.build_outbound(phone, "menu")
    assert out.has_list
    assert out.list_button == "See options"
    assert len(out.list_sections) == 1
    rows = out.list_sections[0]["rows"]
    ids = {r["id"] for r in rows}
    assert ids == {"m_start", "m_goal", "m_demo_shortfall"}
    assert all("description" not in r for r in rows)
    assert all(r["title"][0] in {"🚀", "🎯", "🧪"} for r in rows)
    assert "m_hello" not in ids and "m_menu" not in ids


def test_menu_expands_after_goal_is_set() -> None:
    """After a payment goal exists, menu offers budget, send-to-wallet, reminder, help."""
    phone = "+10000000019"
    dc.build_reply(phone, "start")
    dc.build_reply(phone, "Credit card")
    dc.build_reply(phone, "$450 due May 15")

    out = dc.build_outbound(phone, "menu")
    rows = out.list_sections[0]["rows"]
    ids = {r["id"] for r in rows}
    assert {
        "m_start",
        "m_budget",
        "m_wallet",
        "m_reminder",
        "m_help_principal",
        "m_demo_shortfall",
    }.issubset(ids)
    assert "m_goal" not in ids  # goal already complete
