"""Schemas for the buy-ticket endpoint."""

from typing import Literal

from pydantic import BaseModel, Field


class BuyTicketRequest(BaseModel):
    showtime_id: int = Field(description="Procinal showtime id (from /api/showtimes)")
    seat_pref: Literal["middle", "any"] = Field(
        default="middle",
        description="Seat-picking preference. 'middle' favors rows D/E/F/G.",
    )


class BuyTicketResponse(BaseModel):
    success: bool
    factura: str | None = None
    ref_payco: int | None = None
    autorizacion: str | None = None
    seat: str | None = None
    total_cop: int | None = None
    descripcion: str | None = None
    estado: str | None = None
    # Failure fields
    stage: Literal["login", "showtime_detail", "reserve", "card_charge", "unknown"] | None = None
    code: str | None = None
    message: str | None = None
