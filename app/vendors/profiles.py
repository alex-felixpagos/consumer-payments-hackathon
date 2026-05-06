"""Static vendor data for the public landing pages.

Hackathon scope: a single vendor (`cafe-el-tiempo`). New vendors can be added
by appending entries to ``VENDORS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VendorProfile:
    slug: str
    name: str
    city: str
    country: str
    country_flag: str
    tagline: str
    avatar_emoji: str
    rating: str
    badges: list[str] = field(default_factory=list)
    breb_label: str = "Bre-B · Bancolombia"
    breb_phone: str = ""
    accepts: list[str] = field(default_factory=list)


VENDORS: dict[str, VendorProfile] = {
    "cafe-el-tiempo": VendorProfile(
        slug="cafe-el-tiempo",
        name="Café El Tiempo",
        city="Bogotá",
        country="Colombia",
        country_flag="🇨🇴",
        tagline="Desde 1987 · Candelaria, Bogotá",
        avatar_emoji="☕",
        rating="4.8",
        badges=["⭐ 4.8", "☕ Tinto · Pasteles", "✓ Verificado"],
        breb_label="Bre-B · Bancolombia",
        breb_phone="+57 300 123 4567",
        accepts=["Bre-B", "Bancolombia", "Nequi", "Daviplata"],
    ),
}


def get_vendor(slug: str) -> VendorProfile | None:
    """Return the vendor profile for ``slug`` or ``None`` if unknown."""
    return VENDORS.get(slug)
