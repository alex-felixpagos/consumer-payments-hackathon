"""Unit tests for Felix Pay domain (no bot / HTTP)."""

from uuid import UUID

import pytest

from app.felix_pay import (
    PaymentSessionStatus,
    apply_amount_input,
    apply_currency_choice,
    apply_tip,
    build_confirmation_preview,
    parse_amount_text,
    process_confirm,
    start_session_after_image_stub,
)


def test_happy_path_text_amount_usd_tip_confirm_receipt() -> None:
    payer = "+573009998877"
    s0 = start_session_after_image_stub(payer)
    assert s0.status == PaymentSessionStatus.AWAITING_AMOUNT
    assert s0.vendor_name == "Café El Tiempo"
    assert s0.vendor_breb_key == "+573001234567"
    assert isinstance(s0.session_id, UUID)

    s1 = apply_amount_input(s0, "10")
    assert s1.status == PaymentSessionStatus.AWAITING_CURRENCY
    assert s1.amount_input == 10.0
    assert s1.amount_usd is None and s1.amount_cop is None

    s2 = apply_currency_choice(s1, "USD")
    assert s2.status == PaymentSessionStatus.AWAITING_TIP
    assert s2.amount_usd == 10.0
    assert s2.amount_cop == 42300
    assert s2.fx_rate == 4230.0

    s3 = apply_tip(s2, 0.20)
    assert s3.status == PaymentSessionStatus.AWAITING_CONFIRMATION
    assert s3.tip_pct == 0.20
    assert s3.tip_usd == 2.0
    assert s3.total_usd == 12.0
    assert s3.total_cop == 50760

    preview = build_confirmation_preview(s3)
    assert "Café El Tiempo" in preview
    assert "Subtotal: $10.00 USD" in preview
    assert "Tip (20%)" in preview
    assert "Total: $12.00 USD" in preview
    assert "50,760 COP" in preview
    assert "Locked for 60s" in preview

    result = process_confirm(s3)
    assert result.session.status == PaymentSessionStatus.COMPLETE
    assert isinstance(result.receipt_id, UUID)
    assert result.receipt["amount_cop"] == 42300
    assert result.receipt["amount_usd"] == 10.0
    assert result.receipt["tip_usd"] == 2.0
    assert result.receipt["total_usd"] == 12.0
    assert result.receipt["total_cop"] == 50760
    assert result.receipt["payment_rail"] == "Bre-B"
    assert result.receipt["payer_phone"] == payer


def test_no_tip_skips_breakdown_in_preview() -> None:
    s = start_session_after_image_stub("+15550001111")
    s = apply_amount_input(s, "10")
    s = apply_currency_choice(s, "USD")
    s = apply_tip(s, 0.0)
    preview = build_confirmation_preview(s)
    assert "Subtotal" not in preview
    assert "Tip" not in preview
    assert "$10.00 USD → 42,300 COP" in preview


def test_currency_choice_cop_uses_typed_value_as_cop() -> None:
    s0 = start_session_after_image_stub("+15550001111")
    s1 = apply_amount_input(s0, "10000")
    s2 = apply_currency_choice(s1, "COP")
    assert s2.amount_cop == 10000
    assert s2.amount_usd == pytest.approx(10000 / 4230.0)


def test_apply_tip_rejects_negative() -> None:
    s = start_session_after_image_stub("+15550001111")
    s = apply_amount_input(s, "10")
    s = apply_currency_choice(s, "USD")
    with pytest.raises(ValueError, match="Tip percent"):
        apply_tip(s, -0.1)


def test_apply_tip_requires_currency_first() -> None:
    s = start_session_after_image_stub("+15550001111")
    s = apply_amount_input(s, "10")
    with pytest.raises(ValueError, match="Cannot pick tip"):
        apply_tip(s, 0.20)


def test_parse_amount_text_accepts_currency_decorations() -> None:
    assert parse_amount_text("10") == 10.0
    assert parse_amount_text("$10") == 10.0
    assert parse_amount_text("10.50") == 10.5
    assert parse_amount_text("USD 10") == 10.0
    assert parse_amount_text("1,000") == 1000.0


@pytest.mark.parametrize("bad", ["", "   ", "abc", "$", "0", "-5"])
def test_parse_amount_text_rejects_bad_input(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_amount_text(bad)


def test_apply_currency_choice_rejects_unknown_currency() -> None:
    s = start_session_after_image_stub("+15550001111")
    s = apply_amount_input(s, "10")
    with pytest.raises(ValueError, match="Unsupported currency"):
        apply_currency_choice(s, "EUR")


def test_apply_currency_choice_requires_amount_first() -> None:
    s = start_session_after_image_stub("+15550001111")
    with pytest.raises(ValueError, match="Cannot pick currency"):
        apply_currency_choice(s, "USD")
