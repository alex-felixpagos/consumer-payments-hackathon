"""Kapso WhatsApp adapter — wraps the existing KapsoClient as a Channel."""

from app.services.kapso_client import KapsoClient


class KapsoChannel:
    name = "kapso"

    def __init__(self, client: KapsoClient | None = None) -> None:
        self._client = client or KapsoClient()

    async def send_text(self, to: str, body: str) -> None:
        await self._client.send_whatsapp_message(to, body)

    async def send_image(self, to: str, url: str, caption: str | None = None) -> None:
        await self._client.send_media_message(to, "image", url, caption=caption)


def get_default_channel() -> KapsoChannel:
    """Build the default channel from app settings. Raises if Kapso is unconfigured."""
    return KapsoChannel()
