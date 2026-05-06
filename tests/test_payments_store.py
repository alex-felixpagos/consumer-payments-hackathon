from __future__ import annotations

from app.payments import store


def test_payment_store_persists_status_without_card_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(store, "_PAYMENTS_FILE", tmp_path / "payments.json")

    payment = store.create_payment(
        phone_number="+15551234567",
        amount_cents=1250,
        currency="usd",
        public_base_url="https://pay.example",
        movie_title="Sinners",
        order_summary="2 tickets at 7:00 PM",
    )

    assert payment.phone_number == "15551234567"
    assert payment.status == "pending"
    assert payment.payment_url == f"https://pay.example/pay/{payment.id}"

    updated = store.mark_succeeded(
        payment.id,
        stripe_payment_intent_id="pi_test_123",
        card_last4_value=store.card_last4("4242 4242 4242 4242"),
    )

    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.stripe_payment_intent_id == "pi_test_123"
    assert updated.attempts[0].card_last4 == "4242"

    raw = (tmp_path / "payments.json").read_text(encoding="utf-8")
    assert "4242 4242 4242 4242" not in raw
    assert '"cvv"' not in raw.lower()
