from app.concierge.agent import (
    MediaAttachment,
    _dedupe_media,
    _dedupe_repeated_sections,
)


def test_dedupe_repeated_sections_drops_duplicate_summary_block() -> None:
    text = """Buen momento para enviar.
El tipo de cambio está por encima del promedio.

Buen momento para enviar.
El tipo de cambio está por encima del promedio.

¿Quieres enviarlo por billetera móvil?"""

    cleaned = _dedupe_repeated_sections(text)

    assert cleaned.count("Buen momento para enviar.") == 1
    assert "¿Quieres enviarlo por billetera móvil?" in cleaned


def test_dedupe_media_drops_duplicate_charts_and_captions() -> None:
    media = [
        MediaAttachment(url="https://example.com/chart.png", caption="Buen momento para enviar."),
        MediaAttachment(url="https://example.com/chart.png", caption="Buen momento para enviar."),
        MediaAttachment(url="https://example.com/other.png", caption="Buen momento para enviar."),
    ]

    cleaned = _dedupe_media(media)

    assert len(cleaned) == 1
    assert cleaned[0].url == "https://example.com/chart.png"
    assert cleaned[0].caption is None
