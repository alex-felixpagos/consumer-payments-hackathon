"""
Tools the LLM can call. Deterministic Python, no LLM inside.

Each tool has:
- a JSON schema dict (Anthropic tool format) for the API payload
- a Python implementation that takes kwargs and returns a JSON-serializable result
"""

from typing import Any

from app.concierge.corridors import FELIX_CORRIDORS, resolve_country

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_supported_countries",
        "description": "List the LatAm countries Felix currently supports for remittance.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_corridor",
        "description": (
            "Get Felix corridor details for a destination country: local currency, "
            "available delivery methods, fee, current FX rate, typical speed per method."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "Destination country name, e.g. 'Mexico', 'Colombia'.",
                }
            },
            "required": ["country"],
        },
    },
    {
        "name": "calculate_payout",
        "description": (
            "Compute the estimated amount the recipient will receive in local currency, "
            "using Felix's current FX rate and corridor fee."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "amount_usd": {"type": "number"},
                "method": {
                    "type": "string",
                    "description": "cash_pickup, bank_deposit, or mobile_wallet.",
                },
            },
            "required": ["country", "amount_usd", "method"],
        },
    },
    {
        "name": "get_fx_trend",
        "description": (
            "Compare today's USD vs the destination currency against the past few days. "
            "Returns percent change and a simple direction (strengthening/weakening/stable) "
            "plus the dollar impact on the given transfer amount."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "amount_usd": {"type": "number"},
            },
            "required": ["country", "amount_usd"],
        },
    },
]


def list_supported_countries() -> dict[str, Any]:
    return {"countries": sorted(FELIX_CORRIDORS.keys())}


def get_corridor(country: str) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {
            "error": f"Felix does not currently support {country!r}. "
            f"Supported: {sorted(FELIX_CORRIDORS.keys())}."
        }
    return {
        "country": canonical,
        "currency": data["currency"],
        "fee_usd": data["fee_usd"],
        "fx_rate": data["fx_rate"],
        "methods": data["methods"],
        "typical_speed": data["typical_speed"],
    }


def calculate_payout(country: str, amount_usd: float, method: str) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {"error": f"Unknown country: {country!r}."}
    if method not in data["methods"]:
        return {
            "error": f"{method} not available in {canonical}. "
            f"Available: {data['methods']}.",
            "available_methods": data["methods"],
        }
    received = (amount_usd - data["fee_usd"]) * data["fx_rate"]
    return {
        "country": canonical,
        "currency": data["currency"],
        "amount_usd": amount_usd,
        "fee_usd": data["fee_usd"],
        "fx_rate": data["fx_rate"],
        "method": method,
        "estimated_received": round(received, 2),
        "estimated_speed": data["typical_speed"].get(method, "varies"),
    }


def get_fx_trend(country: str, amount_usd: float) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {"error": f"Unknown country: {country!r}."}
    history = data["fx_history"]
    start, end = history[0], history[-1]
    if start == 0:
        return {"error": "Bad FX history."}
    pct_change = (end - start) / start * 100
    if pct_change > 0.3:
        direction = "USD strengthening vs " + data["currency"]
        suggestion = "wait_could_help" if pct_change > 0.5 else "small_benefit_to_wait"
    elif pct_change < -0.3:
        direction = "USD weakening vs " + data["currency"]
        suggestion = "send_now"
    else:
        direction = "stable"
        suggestion = "no_strong_signal"
    fee_usd = data["fee_usd"]
    impact_local = (amount_usd - fee_usd) * (end - start)
    return {
        "country": canonical,
        "currency": data["currency"],
        "pct_change_5d": round(pct_change, 2),
        "direction": direction,
        "estimated_impact_local": round(impact_local, 2),
        "suggestion": suggestion,
    }


TOOL_IMPLEMENTATIONS = {
    "list_supported_countries": list_supported_countries,
    "get_corridor": get_corridor,
    "calculate_payout": calculate_payout,
    "get_fx_trend": get_fx_trend,
}


def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if not impl:
        return {"error": f"Unknown tool: {name}"}
    try:
        return impl(**arguments)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
