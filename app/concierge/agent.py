"""
Claude agent loop. Channel-agnostic.

Public surface:
    respond(user_id: str, user_text: str) -> AgentReply

The LLM owns extraction, decision-making, and phrasing. Tools own data and math.
Tools whose results carry an image URL (see tools.MEDIA_PRODUCING_TOOLS) are
collected as media attachments and returned alongside the text.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from app.concierge import i18n, state, tools
from app.concierge.prompts import system_message, system_prompt
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8
MAX_OUTPUT_TOKENS = 1024


@dataclass
class MediaAttachment:
    url: str
    caption: str | None = None
    kind: str = "image"


@dataclass
class AgentReply:
    text: str
    media: list[MediaAttachment] = field(default_factory=list)


_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY missing. Set it in .env (shared key in #cp-hackathon)."
            )
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _content_to_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(p for p in parts if p).strip()


def _maybe_collect_media(tool_name: str, result: dict[str, Any]) -> MediaAttachment | None:
    if tool_name not in tools.MEDIA_PRODUCING_TOOLS:
        return None
    url = result.get("url") if isinstance(result, dict) else None
    if not url:
        return None
    caption = result.get("caption") if isinstance(result, dict) else None
    return MediaAttachment(url=url, caption=caption, kind="image")


async def respond(user_id: str, user_text: str) -> AgentReply:
    """Run the agent for one user turn and return text + any media attachments."""
    settings = get_settings()
    client = _get_client()

    locale = i18n.resolve_locale(user_id, user_text)
    history = state.get_history(user_id)
    history.append({"role": "user", "content": user_text})

    media: list[MediaAttachment] = []
    final_text = ""

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system_prompt(locale),
            tools=tools.TOOL_SCHEMAS,
            messages=history,
        )

        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                result = tools.run_tool(block.name, block.input or {}, user_id=user_id)
                logger.info("tool %s -> %s", block.name, result)
                attachment = _maybe_collect_media(block.name, result)
                if attachment is not None:
                    media.append(attachment)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
            history.append({"role": "user", "content": tool_results})
            continue

        final_text = _content_to_text(response.content)
        break

    if not final_text:
        final_text = system_message(locale, "agent_empty")
    return AgentReply(text=final_text, media=media)
