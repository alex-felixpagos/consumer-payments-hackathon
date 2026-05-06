"""Unit tests for Felix Pay domain (no bot / HTTP)."""

from uuid import UUID

import pytest

from app.felix_pay import (
    PaymentSessionStatus,
    apply_amount_from_quick_reply,
    process_confirm,
    start_session_after_image_stub,
)


def test_happy_path_stub_amount_confirm_receipt() -> None:
    payer = "+573009998877"
    s0 = start_session_after_image_stub(payer)
    assert s0.status == PaymentSessionStatus.AWAITING_AMOUNT
    assert s0.vendor_name == "Café El Tiempo"
    assert s0.vendor_breb_key == "+573001234567"
    assert isinstance(s0.session_id, UUID)

    s1 = apply_amount_from_quick_reply(s0, "amt_10")
    assert s1.status == PaymentSessionStatus.AWAITING_CONFIRMATION
    assert s1.amount_usd == 10.0
    assert s1.amount_cop == 42300
    assert s1.fx_rate == 4230.0

    result = process_confirm(s1)
    assert result.session.status == PaymentSessionStatus.COMPLETE
    assert isinstance(result.receipt_id, UUID)
    assert result.receipt["amount_cop"] == 42300
    assert result.receipt["amount_usd"] == 10.0
    assert result.receipt["payer_phone"] == payer


def test_apply_amount_unknown_button_raises() -> None:
    s = start_session_after_image_stub("+15550001111")
    with pytest.raises(ValueError, match="Unknown amount"):
        apply_amount_from_quick_reply(s, "amt_999")
