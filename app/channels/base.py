"""Channel protocol — the contract every adapter (Kapso, CLI, etc.) implements."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Channel(Protocol):
    name: str

    async def send_text(self, to: str, body: str) -> None: ...
