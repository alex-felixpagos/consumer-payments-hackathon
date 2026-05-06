from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PaymentStatus = Literal["pending", "processing", "succeeded", "failed"]


class PaymentAttempt(BaseModel):
    status: PaymentStatus
    created_at: datetime
    stripe_payment_intent_id: str | None = None
    card_last4: str | None = None
    error_message: str | None = None


class PaymentRecord(BaseModel):
    id: str
    phone_number: str
    amount_cents: int = Field(..., ge=1)
    currency: str = Field(default="usd", min_length=3, max_length=3)
    status: PaymentStatus
    payment_url: str
    movie_title: str | None = None
    order_summary: str | None = None
    stripe_payment_intent_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    failed_at: datetime | None = None
    attempts: list[PaymentAttempt] = Field(default_factory=list)


class PaymentPublic(BaseModel):
    id: str
    amount_cents: int
    currency: str
    status: PaymentStatus
    payment_url: str
    movie_title: str | None = None
    order_summary: str | None = None
    stripe_payment_intent_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    failed_at: datetime | None = None


class CardPaymentRequest(BaseModel):
    cardholder_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=254)
    card_number: str = Field(..., min_length=12, max_length=32)
    expiration: str = Field(..., min_length=4, max_length=16)
    cvv: str = Field(..., min_length=3, max_length=8)
