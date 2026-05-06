"""Felix Pay bot flow: KapsoMessage in → mocked Kapso out (no network)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.bot import handle_inbound, reset_felix_pay_state_for_tests
from app.main import app
from app.receipts_memory import clear_receipts_for_tests, get_receipt
from app.schemas.kapso import KapsoMessage

client = TestClient(app)


class _FakeKapso:
    """Records outbound calls instead of hitting Kapso HTTP."""

    def __init__(self) -> None:
        self.texts: list[tuple[str, str]] = []
        self.interactives: list[tuple[str, str, list[dict[str, str]]]] = []

    async def send_whatsapp_message(self, to: str, text: str) -> dict:
        self.texts.append((to, text))
        return {"messages": [{"id": "fake"}]}

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict[str, str]],
        header: str | None = None,
        footer: str | None = None,
    ) -> dict:
        self.interactives.append((to, body_text, buttons))
        return {"messages": [{"id": "fake-int"}]}


def _kapso_meta(direction: str = "inbound") -> dict:
    return {
        "direction": direction,
        "status": "received",
        "processing_status": "done",
    }


def _msg(
    *,
    msg_id: str,
    msg_type: str,
    from_number: str,
    text: str | None = None,
    image: dict | None = None,
    interactive: dict | None = None,
) -> KapsoMessage:
    payload: dict = {
        "id": msg_id,
        "type": msg_type,
        "timestamp": "1700000000",
        "from": from_number,
        "kapso": _kapso_meta(),
    }
    if text is not None:
        payload["text"] = {"body": text}
    if image is not None:
        payload["image"] = image
    if interactive is not None:
        payload["interactive"] = interactive
    return KapsoMessage.model_validate(payload)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_felix_pay_state_for_tests()
    clear_receipts_for_tests()
    yield
    reset_felix_pay_state_for_tests()
    clear_receipts_for_tests()


def test_handle_inbound_happy_path_image_to_receipt() -> None:
    async def _run() -> None:
        fake = _FakeKapso()
        phone = "+15550001111"

        await handle_inbound(
            _msg(msg_id="1", msg_type="image", from_number=phone, image={"id": "mid"}),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.interactives) == 1
        assert "$5" in str(fake.interactives[0][2])

        await handle_inbound(
            _msg(
                msg_id="2",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "amt_10", "title": "$10"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.interactives) == 2
        assert "42,300" in fake.interactives[1][1] or "42300" in fake.interactives[1][1]

        await handle_inbound(
            _msg(
                msg_id="3",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "pay_confirm", "title": "Confirm ✓"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        assert any("http" in t[1] for t in fake.texts)
        receipt_line = next(t[1] for t in fake.texts if "/r/" in t[1])
        rid = receipt_line.split("/r/")[-1].strip().split()[0]
        row = get_receipt(rid)
        assert row is not None
        assert row.amount_usd == 10.0
        assert row.amount_cop == 42300.0

        html = client.get(f"/r/{rid}")
        assert html.status_code == 200
        assert b"Receipt" in html.content

    asyncio.run(_run())


def test_cold_start_text() -> None:
    async def _run() -> None:
        fake = _FakeKapso()
        await handle_inbound(
            _msg(msg_id="a", msg_type="text", from_number="+15550002222", text="hi"),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.texts) == 1
        assert "Felix Pay" in fake.texts[0][1]

    asyncio.run(_run())


def test_webhook_post_requires_valid_json() -> None:
    r = client.post("/webhooks/whatsapp", content=b"not-json")
    assert r.status_code == 422
