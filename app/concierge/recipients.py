"""
Per-user recipient memory.

In-memory and process-local for the hackathon. Replace with a real store later.
The concierge uses this to recall past beneficiaries instead of asking the same
questions every conversation.
"""

import time
from dataclasses import dataclass, field


@dataclass
class Recipient:
    name: str
    country: str
    method: str | None = None
    note: str | None = None
    last_amount_usd: float | None = None
    last_used_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "country": self.country,
            "method": self.method,
            "note": self.note,
            "last_amount_usd": self.last_amount_usd,
        }


_RECIPIENTS: dict[str, list[Recipient]] = {}


def list_for(user_id: str) -> list[Recipient]:
    return sorted(
        _RECIPIENTS.get(user_id, []),
        key=lambda r: r.last_used_at,
        reverse=True,
    )


def find(user_id: str, name: str) -> Recipient | None:
    needle = name.strip().lower()
    for r in _RECIPIENTS.get(user_id, []):
        if r.name.lower() == needle:
            return r
    return None


def save(
    user_id: str,
    name: str,
    country: str,
    *,
    method: str | None = None,
    note: str | None = None,
    last_amount_usd: float | None = None,
) -> Recipient:
    existing = find(user_id, name)
    if existing:
        existing.country = country
        if method:
            existing.method = method
        if note:
            existing.note = note
        if last_amount_usd is not None:
            existing.last_amount_usd = last_amount_usd
        existing.last_used_at = time.time()
        return existing

    recipient = Recipient(
        name=name,
        country=country,
        method=method,
        note=note,
        last_amount_usd=last_amount_usd,
    )
    _RECIPIENTS.setdefault(user_id, []).append(recipient)
    return recipient


def reset() -> None:
    """Test helper."""
    _RECIPIENTS.clear()


def seed_demo(user_id: str) -> None:
    """Optional: prefill one recipient so the concierge has memory to demo on first run."""
    if _RECIPIENTS.get(user_id):
        return
    save(
        user_id,
        name="Maria",
        country="Mexico",
        method="cash_pickup",
        note="sister, Guadalajara",
        last_amount_usd=300,
    )
