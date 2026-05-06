"""HTTP client for Kapso’s WhatsApp Cloud API-compatible endpoints."""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class KapsoClient:
    """
    Kapso (Meta Tech Provider) — docs: https://docs.kapso.ai/docs/introduction

    Uses ``X-API-Key`` and ``POST .../meta/whatsapp/v21.0/{phone_number_id}/messages``.
    """

    def __init__(self, api_key: str | None = None, phone_number_id: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.kapso_api_key
        self.phone_number_id = phone_number_id or settings.kapso_phone_number_id
        self.base_url = settings.kapso_api_url.rstrip("/")

        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "KAPSO_API_KEY is missing. Copy .env.example to .env and add your key from the Kapso dashboard."
            )
        if not self.phone_number_id or not self.phone_number_id.strip():
            raise ValueError(
                "KAPSO_PHONE_NUMBER_ID is missing. Use the WhatsApp phone number ID from Kapso (WhatsApp config)."
            )

        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _messages_url(self) -> str:
        return f"{self.base_url}/meta/whatsapp/v21.0/{self.phone_number_id}/messages"

    def _platform_v1_base(self) -> str:
        """Kapso Platform API root — https://docs.kapso.ai/api/platform/v1/platform-api-overview"""
        return f"{self.base_url}/platform/v1"

    @staticmethod
    def _normalize_to(to: str) -> str:
        return to.lstrip("+")

    async def send_whatsapp_message(self, to: str, text: str) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "text",
            "text": {"body": text},
        }
        return await self._post_messages(payload, f"text to {to}")

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        return await self._post_messages(payload, f"template {template_name} to {to}")

    async def send_media_message(
        self,
        to: str,
        media_type: str,
        media_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": media_type,
            media_type: {"link": media_url},
        }
        if caption:
            payload[media_type]["caption"] = caption
        return await self._post_messages(payload, f"{media_type} to {to}")

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict[str, str]],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": btn["id"], "title": btn["title"]},
                        }
                        for btn in buttons[:3]
                    ]
                },
            },
        }
        if header:
            payload["interactive"]["header"] = {"type": "text", "text": header}
        if footer:
            payload["interactive"]["footer"] = {"text": footer}
        return await self._post_messages(payload, f"interactive buttons to {to}")

    async def send_cta_url_button(
        self,
        to: str,
        body_text: str,
        button_text: str,
        url: str,
        header: str | None = None,
        footer: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {"text": body_text},
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": button_text,
                        "url": url,
                    },
                },
            },
        }
        if header:
            payload["interactive"]["header"] = {"type": "text", "text": header}
        if footer:
            payload["interactive"]["footer"] = {"text": footer}
        return await self._post_messages(payload, f"cta_url to {to}")

    async def send_flow_message(
        self,
        to: str,
        flow_id: str,
        flow_cta: str,
        body_text: str,
        screen: str,
        initial_data: dict[str, Any] | None = None,
        flow_token: str | None = None,
        header: str | None = None,
        footer: str | None = None,
    ) -> dict[str, Any]:
        parameters: dict[str, Any] = {
            "flow_message_version": "3",
            "flow_id": flow_id,
            "flow_cta": flow_cta,
            "flow_action": "navigate",
            "flow_action_payload": {
                "screen": screen,
                "data": initial_data or {},
            },
        }
        if flow_token:
            parameters["flow_token"] = flow_token
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "body": {"text": body_text},
                "action": {"name": "flow", "parameters": parameters},
            },
        }
        if header:
            payload["interactive"]["header"] = {"type": "text", "text": header}
        if footer:
            payload["interactive"]["footer"] = {"text": footer}
        return await self._post_messages(payload, f"flow {flow_id} to {to}")

    async def send_location_request(self, to: str, body_text: str) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": self._normalize_to(to),
            "type": "interactive",
            "interactive": {
                "type": "location_request_message",
                "body": {"text": body_text},
                "action": {"name": "send_location"},
            },
        }
        return await self._post_messages(payload, f"location_request to {to}")

    async def get_account_info(self) -> dict[str, Any]:
        """
        Smoke-test the project API key via the Kapso Platform API.

        Calls ``GET /platform/v1/integrations`` (not ``/account``, which is not used by Kapso).
        """
        url = f"{self._platform_v1_base()}/integrations"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("Kapso platform GET %s failed: %s", url, e)
            raise

    async def _post_messages(self, payload: dict[str, Any], label: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._messages_url(),
                    headers=self.headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Kapso send OK: %s", label)
                return result
        except httpx.HTTPError as e:
            logger.error("Kapso send failed (%s): %s", label, e)
            if hasattr(e, "response") and e.response is not None:
                logger.error("Response body: %s", e.response.text)
            raise
