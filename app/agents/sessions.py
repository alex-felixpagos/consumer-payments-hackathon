"""JSON-file backed session map.

Maps `(agent_id, phone_number)` to the ADK session_id (and a `user_id` we use for
ADK's session service). Survives across requests so chat history persists for the
duration of the process. The underlying ADK conversation history lives in the
`InMemoryRunner` cached in `app.agents.runtime` — both must reset together when
the FastAPI process restarts.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_SESSIONS_FILE = _CONFIG_DIR / "sessions.json"

_LOCK = threading.Lock()


def _ensure_file() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _SESSIONS_FILE.exists():
        _SESSIONS_FILE.write_text(json.dumps({"sessions": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"sessions": []}
    if "sessions" not in data or not isinstance(data["sessions"], list):
        data = {"sessions": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _SESSIONS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _normalize_phone(phone: str) -> str:
    return phone.strip().lstrip("+")


def find_session(agent_id: str, phone_number: str) -> dict[str, Any] | None:
    phone = _normalize_phone(phone_number)
    with _LOCK:
        data = _load_raw()
    for entry in data["sessions"]:
        if entry["agent_id"] == agent_id and entry["phone_number"] == phone:
            return dict(entry)
    return None


def save_session(agent_id: str, phone_number: str, session_id: str, user_id: str) -> dict[str, Any]:
    """Insert (or overwrite if it already exists) a session entry."""
    phone = _normalize_phone(phone_number)
    now = datetime.now(UTC).isoformat()
    with _LOCK:
        data = _load_raw()
        for entry in data["sessions"]:
            if entry["agent_id"] == agent_id and entry["phone_number"] == phone:
                entry["session_id"] = session_id
                entry["user_id"] = user_id
                entry["updated_at"] = now
                _save_raw(data)
                return dict(entry)
        entry = {
            "agent_id": agent_id,
            "phone_number": phone,
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }
        data["sessions"].append(entry)
        _save_raw(data)
    return dict(entry)


def drop_session(agent_id: str, phone_number: str) -> bool:
    """Remove a session entry. Used when the cached ADK runner is invalidated."""
    phone = _normalize_phone(phone_number)
    with _LOCK:
        data = _load_raw()
        before = len(data["sessions"])
        data["sessions"] = [
            e for e in data["sessions"]
            if not (e["agent_id"] == agent_id and e["phone_number"] == phone)
        ]
        if len(data["sessions"]) == before:
            return False
        _save_raw(data)
    return True


def drop_all_for_agent(agent_id: str) -> int:
    """Wipe every session for a given agent — call this when the agent is rebuilt or deleted."""
    with _LOCK:
        data = _load_raw()
        before = len(data["sessions"])
        data["sessions"] = [e for e in data["sessions"] if e["agent_id"] != agent_id]
        removed = before - len(data["sessions"])
        if removed:
            _save_raw(data)
    return removed
