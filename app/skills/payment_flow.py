"""Agent-facing tool for starting the existing WhatsApp payment Flow."""

from __future__ import annotations

from typing import Any


def start_payment_flow(
    amount: float = 1.0,
    movie_title: str | None = None,
    order_summary: str | None = None,
) -> dict[str, Any]:
    """Trigger the same WhatsApp payment Flow that the user can start with "pay 1".

    Use this tool only when the user has selected the movie/order and the next
    step is payment. The server sends the actual WhatsApp Flow after the agent
    response, using the amount returned here.
    """
    if amount <= 0:
        amount = 1.0

    amount_cents = int(round(amount * 100))
    marker = f"[[PAYMENT_FLOW amount={amount:.2f}]]"
    return {
        "type": "payment_flow_trigger",
        "amount": amount,
        "amount_cents": amount_cents,
        "movie_title": movie_title,
        "order_summary": order_summary,
        "final_response_marker": marker,
        "instruction": (
            "Tell the user payment is ready and that they should tap the payment button. "
            f"Place this marker on its own final line so the server can open the Flow: {marker}"
        ),
    }
