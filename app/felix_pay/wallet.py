"""Felix Pay in-memory wallet store (hackathon demo, not persisted)."""

from __future__ import annotations

DEFAULT_WALLET_BALANCE_USD: float = 247.50


class WalletStore:
    """Phone-keyed USD wallet balance.

    Lazy: a phone number that has never been seen reports the default balance.
    Once any debit/reset happens the per-phone value is materialized.
    """

    def __init__(self) -> None:
        self._balances: dict[str, float] = {}

    def get_balance(self, phone: str) -> float:
        return self._balances.get(phone, DEFAULT_WALLET_BALANCE_USD)

    def debit(self, phone: str, amount_usd: float) -> float:
        if amount_usd < 0:
            msg = f"Cannot debit a negative amount: {amount_usd}"
            raise ValueError(msg)
        new_balance = self.get_balance(phone) - amount_usd
        self._balances[phone] = new_balance
        return new_balance

    def reset(self, phone: str) -> None:
        """Drop ``phone`` so the next read returns the default balance."""
        self._balances.pop(phone, None)

    def clear(self) -> None:
        """Drop all balances (tests only)."""
        self._balances.clear()
