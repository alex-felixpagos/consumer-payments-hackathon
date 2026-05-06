"""JSON-file backed conversation transcript store.

Keeps a durable copy of user/assistant turns for display and debugging. The ADK
runner still owns live model memory; this file is the persistent transcript.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.schemas import ConversationHistory, ConversationMessage

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_HISTORY_FILE = _CONFIG_DIR / "conversation_history.json"

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_file() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _HISTORY_FILE.exists():
        _HISTORY_FILE.write_text(json.dumps({"conversations": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"conversations": []}
    if "conversations" not in data or not isinstance(data["conversations"], list):
        data = {"conversations": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _HISTORY_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _normalize_phone(phone: str) -> str:
    return phone.strip().lstrip("+")


def _to_message(raw: dict[str, Any]) -> ConversationMessage:
    return ConversationMessage(
        id=raw["id"],
        role=raw["role"],
        content=raw.get("content", ""),
        created_at=raw["created_at"],
        metadata=raw.get("metadata", {}),
    )


def _to_history(raw: dict[str, Any]) -> ConversationHistory:
    return ConversationHistory(
        agent_id=raw["agent_id"],
        phone_number=raw["phone_number"],
        session_id=raw["session_id"],
        user_id=raw["user_id"],
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        messages=[_to_message(message) for message in raw.get("messages", [])],
    )


def list_conversations() -> list[ConversationHistory]:
    with _LOCK:
        data = _load_raw()
    conversations = [_to_history(raw) for raw in data["conversations"]]
    return sorted(conversations, key=lambda item: item.updated_at, reverse=True)


def get_conversation(agent_id: str, phone_number: str) -> ConversationHistory | None:
    phone = _normalize_phone(phone_number)
    with _LOCK:
        data = _load_raw()
    for raw in data["conversations"]:
        if raw["agent_id"] == agent_id and raw["phone_number"] == phone:
            return _to_history(raw)
    return None


def ensure_conversation(
    *,
    agent_id: str,
    phone_number: str,
    session_id: str,
    user_id: str,
) -> ConversationHistory:
    phone = _normalize_phone(phone_number)
    now = _now()

    with _LOCK:
        data = _load_raw()
        conversation = None
        for raw in data["conversations"]:
            if raw["agent_id"] == agent_id and raw["phone_number"] == phone:
                conversation = raw
                break

        if conversation is None:
            conversation = {
                "agent_id": agent_id,
                "phone_number": phone,
                "session_id": session_id,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            data["conversations"].append(conversation)
        else:
            conversation["session_id"] = session_id
            conversation["user_id"] = user_id

        _save_raw(data)
        return _to_history(conversation)


def append_turn(
    *,
    agent_id: str,
    phone_number: str,
    session_id: str,
    user_id: str,
    user_message: str,
    assistant_message: str,
    delegated_to: str | None = None,
    events: list[dict[str, Any]] | None = None,
) -> ConversationHistory:
    phone = _normalize_phone(phone_number)
    now = _now()
    assistant_metadata: dict[str, Any] = {}
    if delegated_to:
        assistant_metadata["delegated_to"] = delegated_to
    if events:
        assistant_metadata["events"] = events

    with _LOCK:
        data = _load_raw()
        conversation = None
        for raw in data["conversations"]:
            if raw["agent_id"] == agent_id and raw["phone_number"] == phone:
                conversation = raw
                break

        if conversation is None:
            conversation = {
                "agent_id": agent_id,
                "phone_number": phone,
                "session_id": session_id,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            data["conversations"].append(conversation)
        else:
            conversation["session_id"] = session_id
            conversation["user_id"] = user_id
            conversation["updated_at"] = now

        conversation["messages"].extend(
            [
                {
                    "id": f"msg_{uuid.uuid4().hex[:12]}",
                    "role": "user",
                    "content": user_message,
                    "created_at": now,
                    "metadata": {},
                },
                {
                    "id": f"msg_{uuid.uuid4().hex[:12]}",
                    "role": "assistant",
                    "content": assistant_message,
                    "created_at": now,
                    "metadata": assistant_metadata,
                },
            ]
        )
        _save_raw(data)
        return _to_history(conversation)
