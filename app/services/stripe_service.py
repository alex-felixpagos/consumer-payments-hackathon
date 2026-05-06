"""Stripe charge wrapper — test mode, raw card data."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import stripe

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChargeResult:
    success: bool
    payment_intent_id: str | None
    error_message: str | None


def _parse_expiration(expiration: str) -> tuple[int, int]:
    """Accept '12/34', '12 / 34', '1234', '12-34'. Returns (month, year_4digit)."""
    digits = re.sub(r"\D", "", expiration)
    if len(digits) != 4:
        raise ValueError(f"expiration must be MM/YY: got {expiration!r}")
    month = int(digits[:2])
    year = 2000 + int(digits[2:])
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month in expiration: {expiration!r}")
    return month, year


def _charge_sync(
    card_number: str, expiration: str, cvv: str, amount_cents: int, currency: str
) -> ChargeResult:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    month, year = _parse_expiration(expiration)
    clean_number = re.sub(r"\s", "", card_number)
    try:
        pm = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": clean_number,
                "exp_month": month,
                "exp_year": year,
                "cvc": cvv,
            },
        )
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            payment_method=pm.id,
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        )
    except stripe.CardError as e:
        msg = e.user_message or str(e)
        logger.warning("Stripe CardError: %s", msg)
        return ChargeResult(False, None, msg)
    except stripe.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e)
        logger.error("Stripe error: %s", msg)
        return ChargeResult(False, None, msg)

    if intent.status == "succeeded":
        return ChargeResult(True, intent.id, None)
    return ChargeResult(False, intent.id, f"PaymentIntent status: {intent.status}")


async def charge_card(
    card_number: str,
    expiration: str,
    cvv: str,
    amount_cents: int,
    currency: str | None = None,
) -> ChargeResult:
    settings = get_settings()
    cur = (currency or settings.stripe_currency or "usd").lower()
    return await asyncio.to_thread(
        _charge_sync, card_number, expiration, cvv, amount_cents, cur
    )
