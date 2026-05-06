"""One-shot script: create + publish the payment Flow via Kapso API.

Run: ``python -m app.services.flow_setup``

Prints the resulting flow_id. Paste it into ``.env`` as ``KAPSO_FLOW_ID``.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

FLOW_NAME = "card-payment-demo"
FLOW_CATEGORIES = ["OTHER"]
FLOW_JSON_PATH = Path(__file__).resolve().parents[2] / "flows" / "payment_flow.json"


def _kapso_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def main() -> int:
    settings = get_settings()
    if not settings.kapso_api_key:
        print("ERROR: KAPSO_API_KEY missing", file=sys.stderr)
        return 1
    if not settings.kapso_phone_number_id:
        print("ERROR: KAPSO_PHONE_NUMBER_ID missing", file=sys.stderr)
        return 1
    if not FLOW_JSON_PATH.exists():
        print(f"ERROR: flow JSON not found at {FLOW_JSON_PATH}", file=sys.stderr)
        return 1

    flow_json = FLOW_JSON_PATH.read_text(encoding="utf-8")
    json.loads(flow_json)  # validate locally before sending

    base = settings.kapso_api_url.rstrip("/")
    # Phone-number-scoped variant — no WABA ID needed.
    url = f"{base}/meta/whatsapp/v24.0/{settings.kapso_phone_number_id}/flows"
    body = {
        "name": FLOW_NAME,
        "categories": FLOW_CATEGORIES,
        "flow_json": flow_json,
        "publish": True,
    }

    logger.info("POST %s", url)
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=_kapso_headers(settings.kapso_api_key), json=body)

    if resp.status_code >= 400:
        print(f"HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    if data.get("validation_errors"):
        print("Flow JSON validation errors:", file=sys.stderr)
        for err in data["validation_errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1

    flow_id = data.get("id")
    if not flow_id:
        print(f"unexpected response: {data}", file=sys.stderr)
        return 1

    print()
    print(f"  flow created and published")
    print(f"  flow_id = {flow_id}")
    print()
    print(f"  add to .env:  KAPSO_FLOW_ID={flow_id}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
