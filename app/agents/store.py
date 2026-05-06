"""JSON-file backed agent store.

Persists agents to `config/agents.json` at the repo root. Thread-safe writes via a process-wide lock.
This is intentionally simple — no real database — because the hackathon project keeps state minimal.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.schemas import Agent, AgentCreate, AgentUpdate

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_AGENTS_FILE = _CONFIG_DIR / "agents.json"

_LOCK = threading.Lock()


def _ensure_file() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _AGENTS_FILE.exists():
        _AGENTS_FILE.write_text(json.dumps({"agents": []}, indent=2), encoding="utf-8")


def _load_raw() -> dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(_AGENTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Self-heal a corrupted file rather than crashing the API.
        data = {"agents": []}
    if "agents" not in data or not isinstance(data["agents"], list):
        data = {"agents": []}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _ensure_file()
    _AGENTS_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _to_agent(raw: dict[str, Any]) -> Agent:
    return Agent(
        id=raw["id"],
        name=raw["name"],
        system_prompt=raw.get("system_prompt", ""),
        model=raw.get("model", "claude-3-5-sonnet-20241022"),
        sub_agent_ids=raw.get("sub_agent_ids", []),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
    )


def list_agents() -> list[Agent]:
    with _LOCK:
        data = _load_raw()
    return [_to_agent(a) for a in data["agents"]]


def get_agent(agent_id: str) -> Agent | None:
    with _LOCK:
        data = _load_raw()
    for raw in data["agents"]:
        if raw["id"] == agent_id:
            return _to_agent(raw)
    return None


def get_agent_by_name(name: str) -> Agent | None:
    """Case-insensitive lookup by human-readable agent name. Returns the first match."""
    needle = name.strip().lower()
    with _LOCK:
        data = _load_raw()
    for raw in data["agents"]:
        if raw["name"].strip().lower() == needle:
            return _to_agent(raw)
    return None


def get_agents_map() -> dict[str, Agent]:
    return {a.id: a for a in list_agents()}


def create_agent(payload: AgentCreate) -> Agent:
    now = datetime.now(UTC)
    new_id = f"agent_{uuid.uuid4().hex[:12]}"
    raw = {
        "id": new_id,
        "name": payload.name,
        "system_prompt": payload.system_prompt,
        "model": payload.model,
        "sub_agent_ids": payload.sub_agent_ids,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    with _LOCK:
        data = _load_raw()
        # Validate sub-agent ids actually exist.
        existing_ids = {a["id"] for a in data["agents"]}
        for sid in payload.sub_agent_ids:
            if sid not in existing_ids:
                raise ValueError(f"sub_agent_id '{sid}' does not exist")
        data["agents"].append(raw)
        _save_raw(data)
    return _to_agent(raw)


def update_agent(agent_id: str, payload: AgentUpdate) -> Agent | None:
    now = datetime.now(UTC)
    with _LOCK:
        data = _load_raw()
        existing_ids = {a["id"] for a in data["agents"]}
        for raw in data["agents"]:
            if raw["id"] != agent_id:
                continue
            if payload.name is not None:
                raw["name"] = payload.name
            if payload.system_prompt is not None:
                raw["system_prompt"] = payload.system_prompt
            if payload.model is not None:
                raw["model"] = payload.model
            if payload.sub_agent_ids is not None:
                for sid in payload.sub_agent_ids:
                    if sid == agent_id:
                        raise ValueError("An agent cannot reference itself as a sub-agent")
                    if sid not in existing_ids:
                        raise ValueError(f"sub_agent_id '{sid}' does not exist")
                raw["sub_agent_ids"] = payload.sub_agent_ids
            raw["updated_at"] = now.isoformat()
            _save_raw(data)
            return _to_agent(raw)
    return None


def delete_agent(agent_id: str) -> bool:
    with _LOCK:
        data = _load_raw()
        before = len(data["agents"])
        data["agents"] = [a for a in data["agents"] if a["id"] != agent_id]
        # Also strip references from any other agent's sub_agent_ids.
        for raw in data["agents"]:
            raw["sub_agent_ids"] = [sid for sid in raw.get("sub_agent_ids", []) if sid != agent_id]
        if len(data["agents"]) == before:
            return False
        _save_raw(data)
    return True
