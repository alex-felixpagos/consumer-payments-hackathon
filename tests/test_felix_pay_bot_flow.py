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
        self.lists: list[tuple[str, str, str, list[dict]]] = []

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
        return {"messages": [{"id": "fake-list"}]}


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


def test_handle_inbound_happy_path_image_to_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.PROCESSING_DELAY_SECONDS", 0.0)

    async def _run() -> None:
        fake = _FakeKapso()
        phone = "+15550001111"

        await handle_inbound(
            _msg(msg_id="1", msg_type="image", from_number=phone, image={"id": "mid"}),
            fake,  # type: ignore[arg-type]
        )
        assert any("Felix Wallet" in t[1] for t in fake.texts)
        assert any("$247.50" in t[1] for t in fake.texts)
        assert any("Vendor found" in t[1] and "Café El Tiempo" in t[1] for t in fake.texts)
        assert any("How much" in t[1] for t in fake.texts)

        await handle_inbound(
            _msg(msg_id="2", msg_type="text", from_number=phone, text="10"),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.interactives) == 1
        currency_buttons = fake.interactives[0][2]
        assert any(btn["id"] == "cur_usd" for btn in currency_buttons)

        await handle_inbound(
            _msg(
                msg_id="3",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "cur_usd", "title": "🇺🇸 USD"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.lists) == 1
        tip_section = fake.lists[0][3][0]
        tip_ids = {row["id"] for row in tip_section["rows"]}
        assert {"tip_0", "tip_15", "tip_20", "tip_25"} <= tip_ids

        await handle_inbound(
            _msg(
                msg_id="4",
                msg_type="interactive",
                from_number=phone,
                interactive={"list_reply": {"id": "tip_20", "title": "20%"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.interactives) == 2
        preview_body = fake.interactives[1][1]
        assert "Subtotal: $10.00 USD" in preview_body
        assert "Tip (20%)" in preview_body
        assert "Total: $12.00 USD" in preview_body
        assert "50,760 COP" in preview_body
        assert "Locked for 60s" in preview_body

        await handle_inbound(
            _msg(
                msg_id="5",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "pay_confirm", "title": "Confirm ✓"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        assert any("Processing payment" in t[1] for t in fake.texts)

        receipt_line = next(t[1] for t in fake.texts if "/r/" in t[1])
        assert "Payment confirmed" in receipt_line
        assert "Total: *$12.00 USD*" in receipt_line
        assert "Tip (20%)" in receipt_line
        assert "Rail: Bre-B" in receipt_line
        assert "$235.50 USD" in receipt_line  # 247.50 - 12.00
        rid = receipt_line.split("/r/")[-1].strip().split()[0]
        row = get_receipt(rid)
        assert row is not None
        assert row.amount_usd == 10.0
        assert row.tip_pct == 0.20
        assert row.tip_usd == 2.0
        assert row.total_usd == 12.0
        assert row.total_cop == 50760.0
        assert row.payment_rail == "Bre-B"
        assert row.new_balance_usd == pytest.approx(235.5)

        html = client.get(f"/r/{rid}")
        assert html.status_code == 200
        body = html.text
        assert "Payment Receipt" in body
        assert "$12.00" in body
        assert "50,760" in body
        assert "Café El Tiempo" in body
        assert "Bre-B" in body
        assert "Confirmed" in body
        assert "$235.50" in body
        assert "20%" in body  # tip row label

    asyncio.run(_run())


def test_no_tip_skips_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.PROCESSING_DELAY_SECONDS", 0.0)

    async def _run() -> None:
        fake = _FakeKapso()
        phone = "+15550001112"
        await handle_inbound(
            _msg(msg_id="1", msg_type="image", from_number=phone, image={"id": "m"}),
            fake,  # type: ignore[arg-type]
        )
        await handle_inbound(
            _msg(msg_id="2", msg_type="text", from_number=phone, text="10"),
            fake,  # type: ignore[arg-type]
        )
        await handle_inbound(
            _msg(
                msg_id="3",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "cur_usd", "title": "🇺🇸 USD"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        await handle_inbound(
            _msg(
                msg_id="4",
                msg_type="interactive",
                from_number=phone,
                interactive={"list_reply": {"id": "tip_0", "title": "No tip"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        preview_body = fake.interactives[-1][1]
        assert "Subtotal" not in preview_body
        assert "Tip" not in preview_body
        assert "$10.00 USD → 42,300 COP" in preview_body

        await handle_inbound(
            _msg(
                msg_id="5",
                msg_type="interactive",
                from_number=phone,
                interactive={"button_reply": {"id": "pay_confirm", "title": "Confirm ✓"}},
            ),
            fake,  # type: ignore[arg-type]
        )
        receipt_msg = next(t[1] for t in fake.texts if "Payment confirmed" in t[1])
        assert "Subtotal" not in receipt_msg
        assert "Tip" not in receipt_msg
        assert "$237.50 USD" in receipt_msg  # 247.50 - 10.00

    asyncio.run(_run())


def test_invalid_amount_text_reprompts() -> None:
    async def _run() -> None:
        fake = _FakeKapso()
        phone = "+15550005555"
        await handle_inbound(
            _msg(msg_id="1", msg_type="image", from_number=phone, image={"id": "x"}),
            fake,  # type: ignore[arg-type]
        )
        await handle_inbound(
            _msg(msg_id="2", msg_type="text", from_number=phone, text="abc"),
            fake,  # type: ignore[arg-type]
        )
        assert any("couldn't read" in t[1] for t in fake.texts)
        assert len(fake.interactives) == 0

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


def test_hola_resets_mid_flow() -> None:
    async def _run() -> None:
        fake = _FakeKapso()
        phone = "+15550003333"

        await handle_inbound(
            _msg(msg_id="1", msg_type="image", from_number=phone, image={"id": "mid"}),
            fake,  # type: ignore[arg-type]
        )
        await handle_inbound(
            _msg(msg_id="2", msg_type="text", from_number=phone, text="10"),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.interactives) == 1

        await handle_inbound(
            _msg(msg_id="3", msg_type="text", from_number=phone, text="Hola!"),
            fake,  # type: ignore[arg-type]
        )
        assert any("Felix Pay" in t[1] for t in fake.texts)

        await handle_inbound(
            _msg(msg_id="4", msg_type="text", from_number=phone, text="anything"),
            fake,  # type: ignore[arg-type]
        )
        assert fake.texts[-1][1].startswith("Welcome to Felix Pay") or "Felix Pay" in fake.texts[-1][1]

    asyncio.run(_run())


def test_hola_cold_start_text() -> None:
    async def _run() -> None:
        fake = _FakeKapso()
        await handle_inbound(
            _msg(msg_id="a", msg_type="text", from_number="+15550004444", text="hola"),
            fake,  # type: ignore[arg-type]
        )
        assert len(fake.texts) == 1
        assert "Felix Pay" in fake.texts[0][1]

    asyncio.run(_run())


def test_webhook_post_requires_valid_json() -> None:
    r = client.post("/webhooks/whatsapp", content=b"not-json")
    assert r.status_code == 422
