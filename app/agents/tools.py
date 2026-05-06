"""Tool registry for dynamic agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.skills import search_movie_showtimes

AVAILABLE_TOOLS: dict[str, Callable[..., Any]] = {
    "movie_showtimes": search_movie_showtimes,
}


def available_tool_names() -> set[str]:
    return set(AVAILABLE_TOOLS)


def resolve_agent_tools(tool_names: list[str]) -> list[Callable[..., Any]]:
    return [AVAILABLE_TOOLS[name] for name in tool_names if name in AVAILABLE_TOOLS]
