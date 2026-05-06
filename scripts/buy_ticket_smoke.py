"""Smoke-test the buy-ticket flow against the real Procinal API.

Reads PROCINAL_* from .env (or shell). Two modes:

    python -m scripts.buy_ticket_smoke list
        — prints the soonest 10 bookable showtimes today/tomorrow

    python -m scripts.buy_ticket_smoke buy <showtime_id>
        — reserves and charges a ticket using PROCINAL_CARD_* from .env

Without args: lists. Useful for grabbing an id, then running ``buy``.
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.services import procinal_client as pc


async def cmd_list() -> None:
    cinemas = await pc.list_cinemas()
    room_to_cinema = {
        r["id"]: c for c in cinemas for r in c.get("rooms", [])
    }
    movies = {m["id"]: m for m in await pc.list_movies()}
    sh = await pc.list_showtimes()

    today_ish = [
        s for s in sh
        if s.get("fecha_funcion", "") >= "2026-05-06"
        and s.get("is_active") == 1
    ]
    today_ish.sort(key=lambda s: (s["fecha_funcion"], s["hora_funcion"]))

    print(f"{'showtime':>9}  {'date':10}  {'time':8}  {'cinema':<28}  {'movie'}")
    print("-" * 90)
    for s in today_ish[:15]:
        cn = room_to_cinema.get(s["room_id"], {})
        mv = movies.get(s["movie_id"], {})
        print(
            f"{s['id']:>9}  "
            f"{s['fecha_funcion']:10}  "
            f"{s['hora_funcion'][:5]:8}  "
            f"{(cn.get('nombre_completo') or '?')[:28]:<28}  "
            f"{(mv.get('titulo') or '?')[:50]}"
        )


async def cmd_buy(showtime_id: int) -> None:
    from app.config import get_settings
    from app.services.procinal_client import CardData

    settings = get_settings()
    email = settings.procinal_email or "buy-ticket@felixpago.com"

    print(f"--- Login + showtime {showtime_id} ---")
    await pc.login()
    detail = await pc.get_showtime_detail(showtime_id, email)
    print(f"Secuencia: {detail['bill'][0]['Secuencia']}")

    chair = pc.pick_seat(detail, pref="middle")
    print(f"Picked seat: {chair['Fila']}{chair['Columna']} (zone GENERAL)")

    body = pc.build_reservation_body(showtime_id, chair, detail)
    print(f"Total: {body['total']} COP (~${body['total']/4000:.2f} USD)")

    print("\n--- Reserve ---")
    res = await pc.reserve(body)
    print(f"  reservation id: {res.get('data', {}).get('id')}")

    print("\n--- Charge card ---")
    try:
        card = CardData.from_settings()
    except RuntimeError as e:
        print(f"  ⚠️  {e}")
        print("  Set PROCINAL_CARD_* in .env to actually pay.")
        return

    result = await pc.pay_with_card(body, card)
    pay = result.get("pay", {}).get("data", {})
    print(json.dumps(pay, indent=2, ensure_ascii=False)[:1200])
    if pay.get("estado") == "Aceptada":
        print(f"\n✅ Ticket bought: {pay.get('factura')} — check {email} for QR.")
    else:
        print(f"\n❌ Rejected: {pay.get('respuesta')} (cod_error={pay.get('cod_error')})")


async def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "list":
        await cmd_list()
    elif args[0] == "buy" and len(args) == 2:
        await cmd_buy(int(args[1]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
