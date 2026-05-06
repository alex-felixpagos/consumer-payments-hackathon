"""POST /api/buy-ticket — buys a real Procinal ticket using Felix's stored card.

Self-contained: no Kapso, no Stripe. Synchronous (~3-5s end-to-end).
"""

import logging

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.buy_ticket import BuyTicketRequest, BuyTicketResponse
from app.services import procinal_client
from app.services.procinal_client import CardData, ProcinalAuthError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/buy-ticket", response_model=BuyTicketResponse)
async def buy_ticket(req: BuyTicketRequest) -> BuyTicketResponse:
    settings = get_settings()
    email = settings.procinal_email or "buy-ticket@felixpago.com"

    # 1. Login (cached)
    try:
        await procinal_client.login()
    except ProcinalAuthError as e:
        logger.exception("login failed")
        return BuyTicketResponse(success=False, stage="login", message=str(e))

    # 2. Fresh showtime detail (gets a new score_bill.Secuencia)
    try:
        detail = await procinal_client.get_showtime_detail(req.showtime_id, email)
    except Exception as e:
        logger.exception("showtime_detail failed")
        return BuyTicketResponse(success=False, stage="showtime_detail", message=str(e))

    # 3. Pick seat + build payload
    try:
        chair = procinal_client.pick_seat(detail, pref=req.seat_pref)
        body = procinal_client.build_reservation_body(req.showtime_id, chair, detail)
    except Exception as e:
        logger.exception("seat picking failed")
        return BuyTicketResponse(success=False, stage="reserve", message=str(e))

    # 4. Reserve seat
    try:
        await procinal_client.reserve(body)
    except Exception as e:
        logger.exception("reserve failed")
        return BuyTicketResponse(success=False, stage="reserve", message=str(e))

    # 5. Charge card
    try:
        card = CardData.from_settings()
    except RuntimeError as e:
        return BuyTicketResponse(success=False, stage="card_charge", message=str(e))

    try:
        result = await procinal_client.pay_with_card(body, card)
    except Exception as e:
        logger.exception("pay_with_card raised")
        return BuyTicketResponse(success=False, stage="card_charge", message=str(e))

    pay = result.get("pay") or {}
    pay_data = pay.get("data") or {} if isinstance(pay, dict) else {}
    estado = pay_data.get("estado")
    seat_label = f"{chair['Fila']}{chair['Columna']}"

    if estado == "Aceptada":
        return BuyTicketResponse(
            success=True,
            factura=pay_data.get("factura"),
            ref_payco=pay_data.get("ref_payco"),
            autorizacion=pay_data.get("autorizacion"),
            seat=seat_label,
            total_cop=pay_data.get("valor"),
            descripcion=pay_data.get("descripcion"),
            estado=estado,
        )

    # Rejected — surface the issuer/processor reason structurally
    return BuyTicketResponse(
        success=False,
        stage="card_charge",
        factura=pay_data.get("factura"),
        code=pay_data.get("cod_error") or str(pay_data.get("cod_respuesta", "")),
        message=pay_data.get("respuesta") or result.get("message") or "Pago rechazado",
        estado=estado,
        seat=seat_label,
    )
