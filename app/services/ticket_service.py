"""Generate and send WhatsApp-friendly movie ticket images."""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ModuleNotFoundError:  # pragma: no cover - exercised only when deps are missing
    Image = ImageDraw = ImageFilter = ImageFont = None  # type: ignore[assignment]

try:
    import qrcode
except ModuleNotFoundError:  # pragma: no cover - fallback still renders a QR-like block
    qrcode = None  # type: ignore[assignment]

from app.config import get_settings
from app.schemas.tickets import TicketDetails
from app.services.kapso_client import KapsoClient

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = _REPO_ROOT / "media"
TICKET_MEDIA_DIR = MEDIA_DIR / "tickets"

TICKET_WIDTH = 1080
TICKET_HEIGHT = 1350


@dataclass(frozen=True)
class RenderedTicket:
    ticket_id: str
    path: Path
    media_path: str
    seats: list[str]
    booking_reference: str
    qr_payload: str


def _safe_ticket_id(ticket_id: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in ticket_id)
    return cleaned.strip("_") or f"ticket_{uuid.uuid4().hex[:12]}"


def _font(size: int, *, bold: bool = False):
    if ImageFont is None:
        raise RuntimeError("Pillow is required to render ticket images. Install requirements.txt.")

    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_height(draw: Any, text: str, font: Any) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _ellipsize(draw: Any, text: str, font: Any, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    suffix = "..."
    while text and draw.textlength(f"{text}{suffix}", font=font) > max_width:
        text = text[:-1].rstrip()
    return f"{text}{suffix}" if text else suffix


def _wrap_text(draw: Any, text: str, font: Any, max_width: int, max_lines: int | None = None) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(draw, lines[-1], font, max_width)
    return lines


def _format_datetime(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None

    date_label = f"{parsed.strftime('%a, %b')} {parsed.day}"
    hour = parsed.strftime("%I").lstrip("0") or "12"
    time_label = f"{hour}:{parsed.strftime('%M')} {parsed.strftime('%p')}"
    return date_label, time_label


def _showtime_labels(ticket: TicketDetails) -> tuple[str, str]:
    date_label, parsed_time = _format_datetime(ticket.start_time)
    time_label = ticket.display_time or parsed_time
    if date_label and time_label:
        return date_label, time_label
    if time_label:
        return "Showtime", time_label
    return "Showtime", "Selected"


def _amount_label(ticket: TicketDetails) -> str | None:
    if ticket.amount_cents is None:
        return None
    currency = (ticket.currency or "").upper()
    if currency == "COP":
        return f"COP {ticket.amount_cents / 100:,.0f}"
    suffix = f" {currency}" if currency else ""
    return f"${ticket.amount_cents / 100:,.2f}{suffix}"


def _mock_seat() -> str:
    return f"{secrets.choice('CDEFGH')}{secrets.choice(range(4, 15))}"


def _resolved_seats(ticket: TicketDetails) -> list[str]:
    return ticket.seats or [_mock_seat()]


def _draw_gradient(draw: Any) -> None:
    top = (19, 25, 50)
    bottom = (83, 39, 102)
    for y in range(TICKET_HEIGHT):
        ratio = y / max(TICKET_HEIGHT - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line((0, y, TICKET_WIDTH, y), fill=color)


def _draw_detail(draw: Any, x: int, y: int, label: str, value: str, width: int) -> int:
    label_font = _font(24, bold=True)
    value_font = _font(36, bold=True)
    muted = (117, 121, 137)
    ink = (28, 31, 42)

    draw.text((x, y), label.upper(), font=label_font, fill=muted)
    y += 34
    lines = _wrap_text(draw, value, value_font, width, max_lines=2)
    for line in lines:
        draw.text((x, y), line, font=value_font, fill=ink)
        y += _text_height(draw, line, value_font) + 8
    return y + 18


def _draw_finder(draw: Any, x: int, y: int, block: int) -> None:
    draw.rectangle((x, y, x + block * 7, y + block * 7), fill=(18, 24, 38))
    draw.rectangle((x + block, y + block, x + block * 6, y + block * 6), fill=(255, 255, 255))
    draw.rectangle((x + block * 2, y + block * 2, x + block * 5, y + block * 5), fill=(18, 24, 38))


def _mock_qr(payload: str, size: int):
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required to render ticket images. Install requirements.txt.")

    modules = 33
    block = size // modules
    qr_size = block * modules
    image = Image.new("RGB", (qr_size, qr_size), "white")
    draw = ImageDraw.Draw(image)
    seed = int.from_bytes(payload.encode("utf-8"), "little", signed=False)
    rng = secrets.SystemRandom(seed)

    _draw_finder(draw, block * 2, block * 2, block)
    _draw_finder(draw, block * 24, block * 2, block)
    _draw_finder(draw, block * 2, block * 24, block)
    for row in range(2, modules - 2):
        for col in range(2, modules - 2):
            in_finder = (col < 10 and row < 10) or (col > 22 and row < 10) or (col < 10 and row > 22)
            if in_finder:
                continue
            if rng.random() > 0.58:
                x = col * block
                y = row * block
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(18, 24, 38))
    return image.resize((size, size))


def _make_qr(payload: str, size: int):
    if Image is None:
        raise RuntimeError("Pillow is required to render ticket images. Install requirements.txt.")

    if qrcode is None:
        return _mock_qr(payload, size)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#121826", back_color="#ffffff").convert("RGB")
    return image.resize((size, size), Image.Resampling.NEAREST)


def generate_ticket_image(ticket: TicketDetails, *, ticket_id: str | None = None) -> RenderedTicket:
    """Render a 4:5 portrait PNG ticket and return its local media path."""

    if Image is None or ImageDraw is None or ImageFilter is None:
        raise RuntimeError("Pillow is required to render ticket images. Install requirements.txt.")

    TICKET_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    safe_id = _safe_ticket_id(ticket_id or f"ticket_{uuid.uuid4().hex[:12]}")
    seats = _resolved_seats(ticket)
    booking_reference = ticket.booking_reference or safe_id.replace("ticket_", "").upper()
    qr_payload = f"cinebot-ticket:{booking_reference}:{uuid.uuid4().hex}"

    image = Image.new("RGB", (TICKET_WIDTH, TICKET_HEIGHT), (19, 25, 50))
    draw = ImageDraw.Draw(image)
    _draw_gradient(draw)
    image = image.convert("RGBA")

    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((80, 78, 1000, 1290), radius=50, fill=(0, 0, 0, 118))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    image = Image.alpha_composite(image, shadow)

    draw = ImageDraw.Draw(image)
    card = (255, 250, 241, 255)
    ink = (28, 31, 42)
    muted = (117, 121, 137)
    navy = (18, 24, 47, 255)
    coral = (239, 82, 95, 255)
    gold = (249, 190, 89, 255)

    draw.rounded_rectangle((65, 55, 1015, 1288), radius=54, fill=card)
    draw.rounded_rectangle((65, 55, 1015, 430), radius=54, fill=navy)
    draw.rectangle((65, 280, 1015, 430), fill=navy)
    draw.rectangle((65, 412, 1015, 430), fill=coral)

    brand_font = _font(28, bold=True)
    eyebrow_font = _font(24, bold=True)
    title_font = _font(68, bold=True)
    sub_font = _font(32)

    draw.text((115, 105), "CINEBOT", font=brand_font, fill=gold)
    draw.rounded_rectangle((785, 98, 948, 142), radius=22, outline=gold, width=2)
    draw.text((814, 108), "ADMIT 1", font=eyebrow_font, fill=gold)

    title_y = 175
    title_lines = _wrap_text(draw, ticket.movie_title.upper(), title_font, 820, max_lines=3)
    for line in title_lines:
        draw.text((115, title_y), line, font=title_font, fill=(255, 255, 255))
        title_y += _text_height(draw, line, title_font) + 8

    format_label = ticket.format or "Standard"
    draw.text((115, 360), f"{format_label} screening", font=sub_font, fill=(220, 224, 236))

    y = 490
    y = _draw_detail(draw, 115, y, "Cinema", ticket.theater_name, 560)
    if ticket.theater_address:
        address_font = _font(28)
        address = _ellipsize(draw, ticket.theater_address, address_font, 560)
        draw.text((115, y - 12), address, font=address_font, fill=muted)
        y += 40

    date_label, time_label = _showtime_labels(ticket)
    draw.rounded_rectangle((710, 490, 950, 635), radius=28, fill=(250, 235, 211, 255))
    draw.text((745, 520), "SEATS", font=eyebrow_font, fill=muted)
    seat_font = _font(52, bold=True)
    draw.text((745, 555), ", ".join(seats), font=seat_font, fill=ink)

    y = max(y + 10, 680)
    y = _draw_detail(draw, 115, y, "Date", date_label, 330)
    _draw_detail(draw, 505, 690, "Time", time_label, 270)

    amount = _amount_label(ticket)
    if amount:
        _draw_detail(draw, 745, 690, "Paid", amount, 200)

    perforation_y = 858
    draw.line((125, perforation_y, 955, perforation_y), fill=(218, 210, 198), width=3)
    for x in range(145, 940, 36):
        draw.ellipse((x, perforation_y - 5, x + 10, perforation_y + 5), fill=card)
    draw.ellipse((35, perforation_y - 34, 103, perforation_y + 34), fill=(54, 32, 82, 255))
    draw.ellipse((977, perforation_y - 34, 1045, perforation_y + 34), fill=(54, 32, 82, 255))

    ref_font = _font(34, bold=True)
    small_font = _font(24, bold=True)
    body_font = _font(30)
    bottom_y = 930
    draw.text((115, bottom_y), "BOOKING REF", font=small_font, fill=muted)
    draw.text((115, bottom_y + 38), booking_reference, font=ref_font, fill=ink)

    payment_reference = ticket.payment_reference or "Confirmed"
    draw.text((115, bottom_y + 120), "PAYMENT", font=small_font, fill=muted)
    draw.text((115, bottom_y + 158), _ellipsize(draw, payment_reference, body_font, 430), font=body_font, fill=ink)

    draw.text((115, bottom_y + 215), "Arrive 15 minutes early. Show this QR at entry.", font=body_font, fill=muted)

    qr_frame = (630, 930, 950, 1250)
    draw.rounded_rectangle(qr_frame, radius=28, fill=(255, 255, 255, 255), outline=(230, 222, 210), width=3)
    qr_image = _make_qr(qr_payload, 250).convert("RGBA")
    image.paste(qr_image, (665, 952))
    draw = ImageDraw.Draw(image)
    draw.text((680, 1216), "SCAN AT CINEMA", font=small_font, fill=muted)

    draw.rounded_rectangle((115, 1198, 465, 1248), radius=25, fill=(18, 24, 47, 255))
    draw.text((152, 1210), "Enjoy the movie", font=small_font, fill=(255, 255, 255))

    path = TICKET_MEDIA_DIR / f"{safe_id}.png"
    image.convert("RGB").save(path, format="PNG", optimize=True)
    return RenderedTicket(
        ticket_id=safe_id,
        path=path,
        media_path=f"tickets/{path.name}",
        seats=seats,
        booking_reference=booking_reference,
        qr_payload=qr_payload,
    )


def build_media_url(media_path: str, *, public_base_url: str | None = None) -> str:
    base_url = (public_base_url or get_settings().public_base_url).strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "PUBLIC_BASE_URL must be set to your public HTTPS host before sending ticket images."
        )
    return f"{base_url}/media/{media_path.lstrip('/')}"


def ticket_caption(ticket: TicketDetails, rendered: RenderedTicket) -> str:
    date_label, time_label = _showtime_labels(ticket)
    return "\n".join(
        [
            f"Your ticket for {ticket.movie_title}",
            f"{ticket.theater_name}",
            f"{date_label} at {time_label}",
            f"Seats: {', '.join(rendered.seats)}",
            f"Ref: {rendered.booking_reference}",
        ]
    )


async def send_movie_ticket(
    *,
    to: str,
    ticket: TicketDetails,
    client: KapsoClient | None = None,
    public_base_url: str | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    """Generate a ticket image and send it to WhatsApp via Kapso."""

    rendered = generate_ticket_image(ticket, ticket_id=ticket_id)
    media_url = build_media_url(rendered.media_path, public_base_url=public_base_url)
    kapso = client or KapsoClient()
    response = await kapso.send_media_message(
        to=to,
        media_type="image",
        media_url=media_url,
        caption=ticket_caption(ticket, rendered),
    )
    logger.info("Sent movie ticket %s to %s", rendered.ticket_id, to)
    return {
        "success": True,
        "ticket_id": rendered.ticket_id,
        "booking_reference": rendered.booking_reference,
        "media_url": media_url,
        "media_path": str(rendered.path),
        "seats": rendered.seats,
        "kapso": response,
    }
