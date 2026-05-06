"""POST /webhooks/whatsapp with patched KapsoClient — end-to-end without real Kapso."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.receipts_memory import (
    clear_receipts_for_tests,
    get_receipt,
    list_receipt_ids_for_tests,
)
from app.bot import reset_felix_pay_state_for_tests

client = TestClient(app)


def _conversation(phone: str) -> dict:
    return {
        "id": "conv-1",
        "phone_number": phone,
        "status": "open",
        "last_active_at": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _webhook_body(phone: str, message: dict) -> dict:
    return {
        "message": message,
        "conversation": _conversation(phone),
        "is_new_conversation": False,
        "phone_number_id": "000000000000000",
    }


class _FakeKapso:
    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []
        self.interactives: list[tuple[str, str, list[dict[str, str]]]] = []
        self.lists: list[tuple[str, str, str, list[dict]]] = []

    async def send_whatsapp_message(self, to: str, text: str) -> dict:
        self.texts.append((to, text))
        return {"messages": [{"id": "x"}]}

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict[str, str]],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        self.interactives.append((to, body_text, buttons))
        return {"messages": [{"id": "y"}]}

    async def send_interactive_list(
        self,
        to: str,
        body_text: str,
        button_text: str,
        sections: list[dict],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        self.lists.append((to, body_text, button_text, sections))
        return {"messages": [{"id": "z"}]}


def _kapso_meta() -> dict:
    return {"direction": "inbound", "status": "received", "processing_status": "done"}


def test_webhook_image_confirm_creates_receipt(monkeypatch) -> None:
    monkeypatch.setattr("app.bot.PROCESSING_DELAY_SECONDS", 0.0)
    reset_felix_pay_state_for_tests()
    clear_receipts_for_tests()
    phone = "+15559998888"
    fake = _FakeKapso()

    def _msg(mid: str, mtype: str, **extra: object) -> dict:
        m: dict = {
            "id": mid,
            "type": mtype,
            "timestamp": "1700000000",
            "from": phone,
            "kapso": _kapso_meta(),
        }
        m.update(extra)
        return m

    with patch("app.routers.webhooks.KapsoClient", return_value=fake):
        r1 = client.post(
            "/webhooks/whatsapp",
            content=json.dumps(_webhook_body(phone, _msg("1", "image", image={"id": "m1"}))),
            headers={"content-type": "application/json"},
        )
        assert r1.status_code == 200
        assert any("How much" in t[1] for t in fake.texts)

        r2 = client.post(
            "/webhooks/whatsapp",
            content=json.dumps(
                _webhook_body(
                    phone,
                    _msg("2", "text", text={"body": "10"}),
                )
            ),
            headers={"content-type": "application/json"},
        )
        assert r2.status_code == 200
        assert len(fake.interactives) == 1

        r3 = client.post(
            "/webhooks/whatsapp",
            content=json.dumps(
                _webhook_body(
                    phone,
                    _msg(
                        "3",
                        "interactive",
                        interactive={"button_reply": {"id": "cur_usd", "title": "🇺🇸 USD"}},
                    ),
                )
            ),
            headers={"content-type": "application/json"},
        )
        assert r3.status_code == 200
        assert len(fake.lists) == 1

        r4 = client.post(
            "/webhooks/whatsapp",
            content=json.dumps(
                _webhook_body(
                    phone,
                    _msg(
                        "4",
                        "interactive",
                        interactive={"list_reply": {"id": "tip_0", "title": "No tip"}},
                    ),
                )
            ),
            headers={"content-type": "application/json"},
        )
        assert r4.status_code == 200

        r5 = client.post(
            "/webhooks/whatsapp",
            content=json.dumps(
                _webhook_body(
                    phone,
                    _msg(
                        "5",
                        "interactive",
                        interactive={"button_reply": {"id": "pay_confirm", "title": "Confirm ✓"}},
                    ),
                )
            ),
            headers={"content-type": "application/json"},
        )
        assert r5.status_code == 200

    assert any("Payment confirmed" in t[1] for t in fake.texts)
    ids = list_receipt_ids_for_tests()
    assert len(ids) == 1
    assert get_receipt(ids[0]) is not None
