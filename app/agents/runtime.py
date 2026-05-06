"""Process-wide ADK runner cache.

`InMemoryRunner` keeps conversation memory inside the runner's session service.
To preserve chat history across HTTP requests we must reuse the *same runner
instance* for the same agent. This module is that cache.

When an agent's config changes (its `updated_at` advances) we tear the cached
runner down so the next call rebuilds it with the new prompt/model/sub-agents,
and we drop any persisted session entries pointing at the stale runner.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from app.agents import sessions
from app.agents.schemas import Agent
from app.agents.store import get_agents_map

_RUNNERS: dict[str, Any] = {}
_VERSIONS: dict[str, str] = {}
_LOCK = threading.Lock()

APP_NAME = "hackathon-agents"


def _build_runner(agent: Agent) -> Any:
    """Create a fresh InMemoryRunner for `agent`. Imports are deferred so the API
    still boots if google-adk isn't installed yet."""
    from google.adk.runners import InMemoryRunner

    from app.agents.runner import build_llm_agent

    root = build_llm_agent(agent, get_agents_map(), set())
    return InMemoryRunner(agent=root, app_name=APP_NAME)


def get_runner(agent: Agent) -> Any:
    """Return a cached runner for `agent`, rebuilding if the agent has been edited."""
    version = str(agent.updated_at)
    with _LOCK:
        cached_version = _VERSIONS.get(agent.id)
        if cached_version != version:
            # Stale → drop runner + clear sessions so we don't reference a
            # session_id that lives in the now-discarded SessionService.
            _RUNNERS.pop(agent.id, None)
            _VERSIONS.pop(agent.id, None)
            sessions.drop_all_for_agent(agent.id)

        runner = _RUNNERS.get(agent.id)
        if runner is None:
            runner = _build_runner(agent)
            _RUNNERS[agent.id] = runner
            _VERSIONS[agent.id] = version
    return runner


def invalidate(agent_id: str) -> None:
    """Force-drop a cached runner. Used on agent delete/update."""
    with _LOCK:
        _RUNNERS.pop(agent_id, None)
        _VERSIONS.pop(agent_id, None)
    sessions.drop_all_for_agent(agent_id)


async def get_or_create_session_id(agent: Agent, phone_number: str, user_id: str) -> str:
    """Return the ADK session_id for (agent, phone), creating one if needed.

    Verifies the session still exists in the cached runner's session service —
    if the runner was rebuilt we transparently create a fresh session.
    """
    runner = get_runner(agent)

    existing = sessions.find_session(agent.id, phone_number)
    if existing:
        try:
            session = await runner.session_service.get_session(
                app_name=APP_NAME,
                user_id=existing["user_id"],
                session_id=existing["session_id"],
            )
            if session is not None:
                return existing["session_id"]
        except Exception:
            # Fall through and create a new one.
            pass

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
    )
    sessions.save_session(agent.id, phone_number, session.id, user_id)
    return session.id


# Lock for cross-task safety on shared runner state — used to avoid two concurrent
# turns clobbering ADK's session memory for the same (agent, phone) pair.
_TURN_LOCKS: dict[str, asyncio.Lock] = {}
_TURN_LOCKS_GUARD = threading.Lock()


def get_turn_lock(agent_id: str, phone_number: str) -> asyncio.Lock:
    key = f"{agent_id}::{phone_number}"
    with _TURN_LOCKS_GUARD:
        lock = _TURN_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _TURN_LOCKS[key] = lock
    return lock
