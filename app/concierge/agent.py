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
import re
import unicodedata
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


def _idea_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    return " ".join(words)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if len(left_tokens) < 5 or len(right_tokens) < 5:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _dedupe_repeated_sections(text: str) -> str:
    sections = [section.strip() for section in re.split(r"\n{2,}", text.strip()) if section.strip()]
    kept: list[str] = []
    seen_keys: list[str] = []

    for section in sections:
        key = _idea_key(section)
        if not key:
            continue
        if key in seen_keys or any(_token_overlap(key, seen) >= 0.86 for seen in seen_keys):
            logger.info("dropping repeated reply section: %s", section)
            continue
        kept.append(section)
        seen_keys.append(key)

    return "\n\n".join(kept).strip()


def _dedupe_media(media: list[MediaAttachment]) -> list[MediaAttachment]:
    deduped: list[MediaAttachment] = []
    seen_urls: set[str] = set()
    seen_captions: set[str] = set()

    for attachment in media:
        caption_key = _idea_key(attachment.caption or "")
        if attachment.url in seen_urls or (caption_key and caption_key in seen_captions):
            logger.info("dropping repeated media attachment: %s", attachment.url)
            continue
        seen_urls.add(attachment.url)
        if caption_key:
            seen_captions.add(caption_key)
        # The text reply carries the advice; chart captions can otherwise repeat it
        # as a second WhatsApp message with the same idea.
        deduped.append(MediaAttachment(url=attachment.url, caption=None, kind=attachment.kind))

    return deduped


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

    final_text = _dedupe_repeated_sections(final_text)
    if not final_text:
        final_text = system_message(locale, "agent_empty")
    return AgentReply(text=final_text, media=_dedupe_media(media))
