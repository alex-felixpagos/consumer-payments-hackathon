"""Tests for Kapso outbound message helpers."""

from __future__ import annotations

import pytest

from app.services.kapso_client import KapsoClient, WHATSAPP_TEXT_BODY_LIMIT, split_whatsapp_text


def test_split_whatsapp_text_keeps_chunks_under_limit() -> None:
    text = ("movie recommendation " * 500).strip()

    chunks = split_whatsapp_text(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= WHATSAPP_TEXT_BODY_LIMIT for chunk in chunks)
    assert " ".join(chunks) == text


@pytest.mark.asyncio
async def test_send_whatsapp_message_splits_long_text(monkeypatch) -> None:
    sent_payloads: list[dict] = []

    async def fake_post(_self, payload, label):  # noqa: ANN001
        sent_payloads.append(payload)
        return {"label": label}

    monkeypatch.setattr(KapsoClient, "_post_messages", fake_post)

    client = KapsoClient(api_key="test-key", phone_number_id="123")
    response = await client.send_whatsapp_message("5514998934361", "a" * (WHATSAPP_TEXT_BODY_LIMIT + 25))

    assert response["label"].endswith("part 2/2")
    assert len(sent_payloads) == 2
    assert all(len(payload["text"]["body"]) <= WHATSAPP_TEXT_BODY_LIMIT for payload in sent_payloads)
    assert "".join(payload["text"]["body"] for payload in sent_payloads) == "a" * (WHATSAPP_TEXT_BODY_LIMIT + 25)
