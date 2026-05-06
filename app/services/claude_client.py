"""
Two-step coach pipeline for the WhatsApp debt-coach demo.

1. :func:`get_intent` classifies the user's message into one intent label using
   ``coach/router`` (Haiku — fast and cheap).
2. :func:`format_response` writes the actual user-facing reply using
   ``coach/response`` (Sonnet — better wording), conditioned on the intent.

Reads ``ANTHROPIC_API_KEY`` from ``.env`` via :mod:`app.config`.

Run from repo root::

    python -m ideas.main --message "I can't cover principal this month"
    python -m ideas.main --message "show my envelope"
"""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app.config import get_settings
from ideas import prompts

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 1024

INTENT_MODEL = "claude-haiku-4-5"
RESPONSE_MODEL = "claude-sonnet-4-6"

ROUTER_PROMPT = "coach/router"
RESPONSE_PROMPT = "coach/response"

DEFAULT_MESSAGE = "I can't cover principal this month, what should I do?"


async def _ask(
    user_message: str,
    system_prompt: str,
    model: str,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Single Anthropic ``messages`` call. Returns the concatenated text reply."""
    api_key = get_settings().anthropic_api_key.strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is missing. Add it to .env (see .env.example)."
        )

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ANTHROPIC_URL, headers=headers, json=payload, timeout=60.0
        )
        response.raise_for_status()
        data = response.json()

    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


async def get_intent(user_message: str) -> str:
    """Classify ``user_message`` into a single intent label using Haiku."""
    system_prompt = prompts.load(ROUTER_PROMPT)
    # Router is intentionally tight: tiny output, plenty of headroom anyway.
    label = await _ask(
        user_message,
        system_prompt,
        model=INTENT_MODEL,
        max_tokens=32,
    )
    # Defensive: keep only the first non-empty line, lowercase, no punctuation.
    first_line = next((line for line in label.splitlines() if line.strip()), "")
    return first_line.strip().strip(".\"' ").lower()


async def format_response(user_message: str, intent: str) -> str:
    """Write the user-facing reply using Sonnet, conditioned on ``intent``."""
    system_prompt = prompts.load(RESPONSE_PROMPT)
    composed = (
        f"intent: {intent}\n"
        f"user message: {user_message}\n\n"
        "Write the WhatsApp reply for this user, following the routing rules "
        "for the given intent."
    )
    return await _ask(composed, system_prompt, model=RESPONSE_MODEL)


async def run(user_message: str) -> tuple[str, str]:
    """Run the two-step pipeline and return ``(intent, reply)``."""
    intent = await get_intent(user_message)
    reply = await format_response(user_message, intent)
    return intent, reply


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the debt-coach pipeline: classify intent, then format a reply."
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help="User message to classify and respond to.",
    )
    args = parser.parse_args()

    intent, reply = await run(args.message)
    print(f"intent: {intent}\n")
    print(reply)


if __name__ == "__main__":
    asyncio.run(_main())
