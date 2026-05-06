from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.payments import store
from app.schemas.payments import CardPaymentRequest, PaymentPublic
from app.services.kapso_client import KapsoClient
from app.services.stripe_service import charge_card

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_public(record) -> PaymentPublic:
    return PaymentPublic(**record.model_dump())


async def _notify_whatsapp(record, message: str) -> None:
    if not record.phone_number:
        return
    try:
        client = KapsoClient()
        await client.send_whatsapp_message(record.phone_number, message)
    except (ValueError, httpx.HTTPError):
        logger.exception("Could not send WhatsApp payment status for payment=%s", record.id)


@router.get("/payments", response_model=list[PaymentPublic])
async def list_payments() -> list[PaymentPublic]:
    return [_to_public(record) for record in store.list_payments()]


@router.get("/payments/{payment_id}", response_model=PaymentPublic)
async def get_payment(payment_id: str) -> PaymentPublic:
    record = store.get_payment(payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _to_public(record)


@router.post("/payments/{payment_id}/pay", response_model=PaymentPublic)
async def pay(payment_id: str, payload: CardPaymentRequest) -> PaymentPublic:
    record = store.get_payment(payment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if record.status == "succeeded":
        return _to_public(record)

    processing = store.mark_processing(payment_id)
    if processing is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    last4 = store.card_last4(payload.card_number)
    try:
        result = await charge_card(
            card_number=payload.card_number,
            expiration=payload.expiration,
            cvv=payload.cvv,
            amount_cents=processing.amount_cents,
            currency=processing.currency,
        )
    except ValueError as exc:
        failed = store.mark_failed(
            payment_id,
            error_message=str(exc),
            card_last4_value=last4,
        )
        assert failed is not None
        return _to_public(failed)

    amount_display = f"${processing.amount_cents / 100:.2f} {processing.currency.upper()}"
    if result.success:
        updated = store.mark_succeeded(
            payment_id,
            stripe_payment_intent_id=result.payment_intent_id,
            card_last4_value=last4,
        )
        assert updated is not None
        await _notify_whatsapp(
            updated,
            f"Payment received for {amount_display}. Reference: {result.payment_intent_id}",
        )
        return _to_public(updated)

    updated = store.mark_failed(
        payment_id,
        error_message=result.error_message or "Payment failed",
        stripe_payment_intent_id=result.payment_intent_id,
        card_last4_value=last4,
    )
    assert updated is not None
    await _notify_whatsapp(
        updated,
        f"Payment failed for {amount_display}: {updated.error_message or 'unknown error'}",
    )
    return _to_public(updated)
