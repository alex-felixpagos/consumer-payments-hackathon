"""
Felix transfer quotes with enforced competitor price match.

If a mocked competitor delivers more local currency for the same send amount,
Felix's quoted receive amount is raised to match that best competitor outcome.
The implied FX rate (given Felix's own fee) is computed so payout tools stay
consistent — the model must not promise a match unless `match_applied` is true.
"""

from typing import Any

from app.concierge.competitors import COMPETITORS
from app.concierge.corridors import FELIX_CORRIDORS


def _net(amount_usd: float, fee_usd: float) -> float:
    return max(0.0, amount_usd - fee_usd)


def quote_felix_with_match(
    canonical: str,
    amount_usd: float,
    *,
    corridor_rate: float | None = None,
) -> dict[str, Any]:
    """
    Compute Felix receive in local currency, applying competitor match when needed.

    `corridor_rate` defaults to Felix's published corridor rate; pass an override
    when using a point from fx_history (e.g. projected rate).
    """
    data = FELIX_CORRIDORS[canonical]
    fee = data["fee_usd"]
    base_rate = float(data["fx_rate"] if corridor_rate is None else corridor_rate)
    net = _net(amount_usd, fee)
    currency = data["currency"]

    felix_base_receive = net * base_rate

    competitor_rows: list[dict[str, Any]] = []
    best_receive = 0.0
    best_name: str | None = None
    for c in COMPETITORS.get(canonical, []):
        c_net = _net(amount_usd, c["fee_usd"])
        recv = c_net * c["fx_rate"]
        competitor_rows.append(
            {
                "name": c["name"],
                "fee_usd": c["fee_usd"],
                "fx_rate": c["fx_rate"],
                "estimated_received": round(recv, 2),
            }
        )
        if recv > best_receive:
            best_receive = recv
            best_name = c["name"]

    target_receive = max(felix_base_receive, best_receive)
    match_applied = target_receive > felix_base_receive + 1e-12
    matched_to = best_name if match_applied else None
    applied_rate = (target_receive / net) if net > 0 else base_rate

    return {
        "country": canonical,
        "currency": currency,
        "amount_usd": amount_usd,
        "felix_fee_usd": fee,
        "felix_base_rate": base_rate,
        "felix_base_receive": round(felix_base_receive, 2),
        "applied_fx_rate": round(applied_rate, 6 if currency == "COP" else 4),
        "felix_receive_after_match": round(target_receive, 2),
        "match_applied": match_applied,
        "matched_to": matched_to,
        "competitors": competitor_rows,
    }
