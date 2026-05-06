"""In-memory per-user conversation history. Process-local; resets on restart."""

from typing import Any

_HISTORY: dict[str, list[dict[str, Any]]] = {}


def get_history(user_id: str) -> list[dict[str, Any]]:
    return _HISTORY.setdefault(user_id, [])


def append(user_id: str, message: dict[str, Any]) -> None:
    get_history(user_id).append(message)


def reset(user_id: str) -> None:
    _HISTORY.pop(user_id, None)
