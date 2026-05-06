"""
Tools the LLM can call. Deterministic Python, no LLM inside.

Each tool has:
- a JSON schema dict (Anthropic tool format) for the API payload
- a Python implementation that takes kwargs and returns a JSON-serializable result
"""

from typing import Any

from app.concierge import fx_chart
from app.concierge import recipients as recipients_store
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
    {
        "name": "assess_fx_window",
        "description": (
            "30-day FX intelligence. Returns where today's rate sits in the 30-day "
            "range (percentile, vs avg, vs low/high), 7-day direction, and a verdict: "
            "great_time / decent / neutral / low_end / wait_if_possible. Use this to "
            "tell the user whether today is a good moment to send."
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
    {
        "name": "render_fx_chart",
        "description": (
            "Generate a public PNG URL of the 30-day USD-vs-local-currency chart for "
            "a corridor. Call this when you give FX advice so the user can SEE the "
            "trend in WhatsApp. Returns {url, caption}; the bot will attach the image."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "caption": {
                    "type": "string",
                    "description": "Short caption for the chart (1 sentence).",
                },
            },
            "required": ["country"],
        },
    },
    {
        "name": "compare_options",
        "description": (
            "Return the full advisory grid for a transfer: every available delivery "
            "method × send-now vs wait-2-days. Use this to advise the user on tradeoffs "
            "instead of computing a single payout."
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
    {
        "name": "list_recipients",
        "description": (
            "List previously-used recipients for the current user. Call this near the "
            "start of a conversation to recall who the user has sent to before so you "
            "can offer 'same as last time' shortcuts. No arguments needed — the user "
            "context is bound automatically."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_recipient",
        "description": (
            "Persist a recipient the user mentioned so future conversations can recall "
            "them. Save name + country at minimum; include method/note/amount when known. "
            "User context is bound automatically — do not pass user_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "country": {"type": "string"},
                "method": {"type": "string"},
                "note": {"type": "string", "description": "Short context, e.g. 'sister, Guadalajara'."},
                "last_amount_usd": {"type": "number"},
            },
            "required": ["name", "country"],
        },
    },
]

# Tools that need the caller's user_id injected by the agent (not exposed to the LLM).
USER_SCOPED_TOOLS = {"list_recipients", "save_recipient"}


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


def _verdict_for_percentile(pct: float) -> str:
    """Map 0..1 percentile (1 = top of 30d range, best for sender) to a verdict."""
    if pct >= 0.80:
        return "great_time"
    if pct >= 0.60:
        return "decent"
    if pct >= 0.40:
        return "neutral"
    if pct >= 0.20:
        return "low_end"
    return "wait_if_possible"


def assess_fx_window(country: str, amount_usd: float) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {"error": f"Unknown country: {country!r}."}
    history = data["fx_history"]
    today = history[-1]
    lo = min(history)
    hi = max(history)
    avg = sum(history) / len(history)
    rng = hi - lo
    percentile = 0.5 if rng == 0 else (today - lo) / rng
    verdict = _verdict_for_percentile(percentile)

    last_week = history[-7:] if len(history) >= 7 else history
    week_change_pct = (
        ((last_week[-1] - last_week[0]) / last_week[0] * 100) if last_week[0] else 0.0
    )
    week_direction = (
        "up" if week_change_pct > 0.2 else "down" if week_change_pct < -0.2 else "flat"
    )

    fee = data["fee_usd"]
    net = max(0.0, amount_usd - fee)
    impact_vs_avg = round(net * (today - avg), 2)
    impact_vs_low = round(net * (today - lo), 2)
    impact_vs_high = round(net * (today - hi), 2)

    return {
        "country": canonical,
        "currency": data["currency"],
        "today_rate": today,
        "thirty_day_low": lo,
        "thirty_day_high": hi,
        "thirty_day_avg": round(avg, 4),
        "percentile_in_30d": round(percentile, 3),
        "verdict": verdict,
        "week_change_pct": round(week_change_pct, 2),
        "week_direction": week_direction,
        "amount_usd": amount_usd,
        "impact_local_vs_30d_avg": impact_vs_avg,
        "impact_local_vs_30d_low": impact_vs_low,
        "impact_local_vs_30d_high": impact_vs_high,
    }


def render_fx_chart(country: str, caption: str | None = None) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {"error": f"Unknown country: {country!r}."}
    url = fx_chart.build_url(
        title=f"USD / {data['currency']} — last {len(data['fx_history'])} days",
        currency=data["currency"],
        history=data["fx_history"],
    )
    return {
        "url": url,
        "caption": caption or f"USD/{data['currency']} — last {len(data['fx_history'])} days",
        "country": canonical,
        "currency": data["currency"],
    }


def compare_options(country: str, amount_usd: float) -> dict[str, Any]:
    """Method × time grid. Lets the agent advise across tradeoffs in one shot."""
    canonical = resolve_country(country) or country
    data = FELIX_CORRIDORS.get(canonical)
    if not data:
        return {"error": f"Unknown country: {country!r}."}

    history = data["fx_history"]
    today_rate = history[-1]
    if len(history) >= 2:
        avg_daily_delta = (history[-1] - history[0]) / max(1, len(history) - 1)
    else:
        avg_daily_delta = 0.0
    projected_rate_in_2d = today_rate + 2 * avg_daily_delta

    fee = data["fee_usd"]
    net = max(0.0, amount_usd - fee)

    options = []
    for method in data["methods"]:
        options.append(
            {
                "method": method,
                "speed": data["typical_speed"].get(method, "varies"),
                "send_today": round(net * today_rate, 2),
                "send_in_2_days": round(net * projected_rate_in_2d, 2),
                "delta_if_wait": round(net * (projected_rate_in_2d - today_rate), 2),
            }
        )

    return {
        "country": canonical,
        "currency": data["currency"],
        "amount_usd": amount_usd,
        "fee_usd": fee,
        "today_rate": today_rate,
        "projected_rate_in_2_days": round(projected_rate_in_2d, 4),
        "options": options,
    }


def list_recipients(user_id: str) -> dict[str, Any]:
    return {"recipients": [r.to_dict() for r in recipients_store.list_for(user_id)]}


def save_recipient(
    user_id: str,
    name: str,
    country: str,
    method: str | None = None,
    note: str | None = None,
    last_amount_usd: float | None = None,
) -> dict[str, Any]:
    canonical = resolve_country(country) or country
    if canonical not in FELIX_CORRIDORS:
        return {"error": f"Felix does not support {country!r}; not saving recipient."}
    saved = recipients_store.save(
        user_id,
        name=name,
        country=canonical,
        method=method,
        note=note,
        last_amount_usd=last_amount_usd,
    )
    return {"saved": True, "recipient": saved.to_dict()}


TOOL_IMPLEMENTATIONS = {
    "list_supported_countries": list_supported_countries,
    "get_corridor": get_corridor,
    "calculate_payout": calculate_payout,
    "get_fx_trend": get_fx_trend,
    "assess_fx_window": assess_fx_window,
    "render_fx_chart": render_fx_chart,
    "compare_options": compare_options,
    "list_recipients": list_recipients,
    "save_recipient": save_recipient,
}

# Tools whose results the agent should treat as media attachments to send to the channel.
MEDIA_PRODUCING_TOOLS = {"render_fx_chart"}


def run_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if not impl:
        return {"error": f"Unknown tool: {name}"}
    args = dict(arguments)
    if name in USER_SCOPED_TOOLS:
        if not user_id:
            return {"error": f"{name} requires a bound user_id (agent must inject it)."}
        args["user_id"] = user_id
    try:
        return impl(**args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
