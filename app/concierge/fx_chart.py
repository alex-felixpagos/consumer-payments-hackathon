"""
Build a quickchart.io URL for an FX history. No hosting needed — quickchart
renders the PNG from URL params, and WhatsApp/Kapso can fetch any public URL.
"""

import json
import urllib.parse


QUICKCHART_BASE = "https://quickchart.io/chart"


def build_url(
    *,
    title: str,
    currency: str,
    history: list[float],
    today_index: int | None = None,
    width: int = 600,
    height: int = 320,
) -> str:
    """Render a 30-day line chart with min/max highlighted and today marked."""
    n = len(history)
    labels = [f"D-{n - 1 - i}" if i < n - 1 else "Today" for i in range(n)]

    today_idx = today_index if today_index is not None else n - 1
    today_value = history[today_idx]
    avg = sum(history) / n
    lo = min(history)
    hi = max(history)

    config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": f"USD/{currency}",
                    "data": history,
                    "fill": False,
                    "borderColor": "rgba(34, 197, 94, 1)",
                    "backgroundColor": "rgba(34, 197, 94, 0.15)",
                    "tension": 0.25,
                    "pointRadius": 0,
                    "borderWidth": 2,
                },
                {
                    "label": "30d avg",
                    "data": [round(avg, 4)] * n,
                    "borderColor": "rgba(148, 163, 184, 0.9)",
                    "borderDash": [4, 4],
                    "borderWidth": 1,
                    "pointRadius": 0,
                    "fill": False,
                },
                {
                    "label": "Today",
                    "data": [None] * (today_idx) + [today_value] + [None] * (n - today_idx - 1),
                    "borderColor": "rgba(220, 38, 38, 1)",
                    "backgroundColor": "rgba(220, 38, 38, 1)",
                    "pointRadius": 5,
                    "pointStyle": "circle",
                    "showLine": False,
                },
            ],
        },
        "options": {
            "title": {"display": True, "text": title},
            "legend": {"position": "bottom"},
            "scales": {
                "yAxes": [
                    {
                        "ticks": {
                            "suggestedMin": lo - (hi - lo) * 0.1,
                            "suggestedMax": hi + (hi - lo) * 0.1,
                        }
                    }
                ]
            },
        },
    }

    encoded = urllib.parse.quote(json.dumps(config, separators=(",", ":")))
    return f"{QUICKCHART_BASE}?w={width}&h={height}&c={encoded}"
