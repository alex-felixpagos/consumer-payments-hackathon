from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.schemas.tickets import TicketDetails
from app.services import ticket_service


def _ticket() -> TicketDetails:
    return TicketDetails(
        movie_title="Spider-Man: Into the Spider-Verse",
        theater_name="AMC Highland Village 12",
        theater_address="4090 Barton Creek, Highland Village, 75077",
        start_time="2026-05-06T19:05:00",
        display_time="7:05 PM",
        format="Standard",
        amount_cents=1250,
        currency="usd",
        payment_reference="pi_test_123",
    )


def test_generate_ticket_image_creates_whatsapp_portrait_png(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ticket_service, "TICKET_MEDIA_DIR", tmp_path / "tickets")

    rendered = ticket_service.generate_ticket_image(_ticket(), ticket_id="ticket_ratio")

    assert rendered.media_path == "tickets/ticket_ratio.png"
    assert rendered.path.exists()
    assert rendered.seats

    with Image.open(rendered.path) as image:
        assert image.format == "PNG"
        assert image.size == (ticket_service.TICKET_WIDTH, ticket_service.TICKET_HEIGHT)
        assert image.width / image.height == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_send_movie_ticket_sends_image_media(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ticket_service, "TICKET_MEDIA_DIR", tmp_path / "tickets")
    client = AsyncMock()
    client.send_media_message = AsyncMock(return_value={"messages": [{"id": "wamid.ticket"}]})

    result = await ticket_service.send_movie_ticket(
        to="+573001112233",
        ticket=_ticket(),
        client=client,
        public_base_url="https://tickets.example",
        ticket_id="ticket_send",
    )

    assert result["success"] is True
    assert result["media_url"] == "https://tickets.example/media/tickets/ticket_send.png"
    assert Path(result["media_path"]).exists()

    client.send_media_message.assert_awaited_once()
    kwargs = client.send_media_message.await_args.kwargs
    assert kwargs["to"] == "+573001112233"
    assert kwargs["media_type"] == "image"
    assert kwargs["media_url"] == result["media_url"]
    assert "Spider-Man" in kwargs["caption"]
