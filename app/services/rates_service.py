"""
FX rates lookup for remittance flows.

Two-turn conversation:

1. User asks for rates → bot prompts for *country* and *amount*.
2. User replies with both (or sends them in the original message) →
   bot returns a conversion using the live USD-base rate.

Rates come from the free, key-less ``open.er-api.com`` endpoint.
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RATES_URL = "https://open.er-api.com/v6/latest/USD"

# Currencies surfaced as featured corridors. Order matters for the prompt.
# (code, display_name, flag)
_FEATURED_CORRIDORS: list[tuple[str, str, str]] = [
    ("MXN", "Mexico", "🇲🇽"),
    ("COP", "Colombia", "🇨🇴"),
    ("GTQ", "Guatemala", "🇬🇹"),
    ("HNL", "Honduras", "🇭🇳"),
    ("DOP", "Dominican Republic", "🇩🇴"),
    ("BRL", "Brazil", "🇧🇷"),
]

# Triggers in English + Spanish that route a message to this service.
_RATE_KEYWORDS: tuple[str, ...] = (
    "rate",
    "rates",
    "fx",
    "exchange",
    "tasa",
    "tasas",
    "cambio",
    "tipo de cambio",
    "cotizacion",
    "cotización",
)

# Country / currency aliases → ISO 4217 currency code + display name.
# Keep keys lowercase. Hand-rolled (no `pycountry`) to stay dependency-light
# and to cover the LatAm corridors we actually care about.
_COUNTRY_ALIASES: dict[str, tuple[str, str]] = {
    # Mexico
    "mexico": ("MXN", "Mexico"),
    "méxico": ("MXN", "Mexico"),
    "mx": ("MXN", "Mexico"),
    "mxn": ("MXN", "Mexico"),
    # Colombia
    "colombia": ("COP", "Colombia"),
    "co": ("COP", "Colombia"),
    "cop": ("COP", "Colombia"),
    # Guatemala
    "guatemala": ("GTQ", "Guatemala"),
    "gt": ("GTQ", "Guatemala"),
    "gtq": ("GTQ", "Guatemala"),
    # Honduras
    "honduras": ("HNL", "Honduras"),
    "hn": ("HNL", "Honduras"),
    "hnl": ("HNL", "Honduras"),
    # Dominican Republic
    "dominican": ("DOP", "Dominican Republic"),
    "dominicana": ("DOP", "Dominican Republic"),
    "republica dominicana": ("DOP", "Dominican Republic"),
    "república dominicana": ("DOP", "Dominican Republic"),
    "dr": ("DOP", "Dominican Republic"),
    "do": ("DOP", "Dominican Republic"),
    "dop": ("DOP", "Dominican Republic"),
    # Brazil
    "brazil": ("BRL", "Brazil"),
    "brasil": ("BRL", "Brazil"),
    "br": ("BRL", "Brazil"),
    "brl": ("BRL", "Brazil"),
}

# Per-phone-number flag: the user asked for rates and we're waiting on
# country + amount. In-process only — fine for the hackathon's single
# Uvicorn worker; swap for Redis/a state store if we ever scale out.
_pending_rates: dict[str, bool] = {}


def is_rates_request(text: str | None) -> bool:
    """True if the inbound text looks like a request for FX rates."""
    if not text:
        return False
    lowered = text.lower().strip()
    return any(kw in lowered for kw in _RATE_KEYWORDS)


def is_awaiting_rates_input(phone: str) -> bool:
    """True if we previously prompted this phone for country + amount."""
    return _pending_rates.get(phone, False)


def _mark_pending(phone: str) -> None:
    _pending_rates[phone] = True


def _clear_pending(phone: str) -> None:
    _pending_rates.pop(phone, None)


def parse_country_and_amount(
    text: str | None,
) -> tuple[tuple[str, str] | None, float | None]:
    """
    Extract ``((currency_code, display_name), amount)`` from free-form text.

    Either side can be ``None`` if not found. Examples that parse:
    ``"Mexico 250"``, ``"$100 to Brazil"``, ``"send 1500 cop"``,
    ``"BRL 50.5"``, ``"100,5 mxn"``.
    """
    if not text:
        return None, None

    lowered = text.lower()

    country: tuple[str, str] | None = None
    # Longer aliases first so "republica dominicana" wins over "do".
    for alias in sorted(_COUNTRY_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            country = _COUNTRY_ALIASES[alias]
            break

    amount: float | None = None
    # Match the first number, allowing thousands separators and either
    # ``.`` or ``,`` as decimal separator (Spanish-speakers often use ``,``).
    number_match = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d+)([.,]\d+)?", lowered)
    if number_match:
        whole = number_match.group(1).replace(".", "").replace(",", "")
        decimal = number_match.group(2)
        try:
            if decimal:
                amount = float(f"{whole}.{decimal[1:]}")
            else:
                amount = float(whole)
        except ValueError:
            amount = None

    return country, amount


async def fetch_usd_rates(client: httpx.AsyncClient | None = None) -> dict[str, float]:
    """
    Fetch latest USD-base rates. Returns a mapping like ``{"MXN": 17.05, ...}``.

    Raises ``httpx.HTTPError`` on network/HTTP failure or ``ValueError`` if the
    upstream payload is malformed.
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        response = await client.get(RATES_URL)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    finally:
        if owns_client:
            await client.aclose()

    if data.get("result") != "success" or "rates" not in data:
        raise ValueError(f"Unexpected rates payload: {data!r}")

    rates = data["rates"]
    if not isinstance(rates, dict):
        raise ValueError("rates payload is not a dict")
    return {code: float(value) for code, value in rates.items()}


def get_rates_prompt() -> str:
    """Reply asking the user for the destination country and the USD amount."""
    countries = ", ".join(country for _, country, _ in _FEATURED_CORRIDORS[:4])
    return (
        "💱 Sure! To quote an exchange rate I need two things:\n"
        "1️⃣ The destination *country* (e.g. " + countries + ")\n"
        "2️⃣ The *amount* in USD (e.g. 250)\n\n"
        '_Example: "Mexico 250"_'
    )


def format_quote_message(country: str, code: str, amount: float, rate: float) -> str:
    """Render a single-corridor conversion reply."""
    converted = amount * rate
    return (
        f"💱 *Quote — {country}*\n"
        f"{amount:,.2f} USD ≈ {converted:,.2f} {code}\n"
        f"_Rate: 1 USD = {rate:,.4f} {code}_"
    )


def format_missing_input_message(
    has_country: bool, has_amount: bool, original_text: str | None = None
) -> str:
    """Reply that lists which piece(s) are still missing."""
    if not has_country and not has_amount:
        return get_rates_prompt()
    if not has_country:
        return (
            "Got the amount 👍 — which *country* should I convert to?\n"
            "_Example: Mexico, Colombia, Brazil…_"
        )
    return (
        "Got the country 👍 — how much in *USD* would you like to send?\n"
        '_Example: "250"_'
    )


async def handle_rates_message(phone: str, text: str | None) -> str:
    """
    Drive the two-turn rates conversation.

    Call this whenever ``is_rates_request(text)`` matches OR the phone is
    already in ``is_awaiting_rates_input``. The handler is responsible for
    flipping the pending flag on/off.
    """
    country, amount = parse_country_and_amount(text)

    if country and amount is not None:
        _clear_pending(phone)
        try:
            rates = await fetch_usd_rates()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Failed to fetch FX rates: %s", exc)
            return (
                "Sorry — I couldn't fetch live exchange rates right now. "
                "Please try again in a moment."
            )
        code, display = country
        rate = rates.get(code)
        if rate is None:
            return (
                f"I couldn't find a live rate for {display} ({code}) right now. "
                "Try a different country?"
            )
        return format_quote_message(display, code, amount, rate)

    _mark_pending(phone)
    return format_missing_input_message(
        has_country=country is not None,
        has_amount=amount is not None,
        original_text=text,
    )
