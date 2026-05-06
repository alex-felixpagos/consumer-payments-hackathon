"""Channel protocol — the contract every adapter (Kapso, CLI, etc.) implements."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Channel(Protocol):
    name: str

    async def send_text(self, to: str, body: str) -> None: ...

    async def send_image(self, to: str, url: str, caption: str | None = None) -> None: ...
