"""Agent-facing tool for creating a Stripe payment link."""

from __future__ import annotations

from typing import Any


def start_payment_flow(
    amount: float = 1.0,
    movie_title: str | None = None,
    order_summary: str | None = None,
) -> dict[str, Any]:
    """Trigger the same Stripe payment link that the user can start with "pay 1".

    Use this tool only when the user has selected the movie/order and the next
    step is payment. The server creates the payment record and sends the link
    after the agent response, using the amount returned here.
    """
    if amount <= 0:
        amount = 1.0

    amount_cents = int(round(amount * 100))
    marker = f"[[PAYMENT_LINK amount={amount:.2f}]]"
    return {
        "type": "payment_link_trigger",
        "amount": amount,
        "amount_cents": amount_cents,
        "movie_title": movie_title,
        "order_summary": order_summary,
        "final_response_marker": marker,
        "instruction": (
            "Tell the user payment is ready and that you will send a secure payment link. "
            f"Place this marker on its own final line so the server can create the link: {marker}"
        ),
    }
