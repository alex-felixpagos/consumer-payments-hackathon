from __future__ import annotations

import importlib
import sys
import types
from datetime import UTC, datetime
from typing import Any

from app.agents.schemas import Agent
from app.skills import search_movie_showtimes


def _load_runner_with_adk_fakes(monkeypatch: Any) -> Any:
    async def acompletion(*args: Any, **kwargs: Any) -> None:
        return None

    litellm_module = types.ModuleType("litellm")
    litellm_module.acompletion = acompletion
    exceptions_module = types.ModuleType("litellm.exceptions")
    for name in (
        "APIConnectionError",
        "APIError",
        "AuthenticationError",
        "BadGatewayError",
        "BadRequestError",
        "InternalServerError",
        "NotFoundError",
        "PermissionDeniedError",
        "RateLimitError",
        "ServiceUnavailableError",
        "Timeout",
    ):
        setattr(exceptions_module, name, type(name, (Exception,), {}))

    class FakeLlmAgent:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeLiteLlm:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    google_module = types.ModuleType("google")
    adk_module = types.ModuleType("google.adk")
    agents_module = types.ModuleType("google.adk.agents")
    models_module = types.ModuleType("google.adk.models")
    lite_llm_module = types.ModuleType("google.adk.models.lite_llm")

    agents_module.LlmAgent = FakeLlmAgent
    lite_llm_module.LiteLlm = FakeLiteLlm
    google_module.adk = adk_module
    adk_module.agents = agents_module
    adk_module.models = models_module
    models_module.lite_llm = lite_llm_module

    for module_name, module in {
        "litellm": litellm_module,
        "litellm.exceptions": exceptions_module,
        "google": google_module,
        "google.adk": adk_module,
        "google.adk.agents": agents_module,
        "google.adk.models": models_module,
        "google.adk.models.lite_llm": lite_llm_module,
    }.items():
        monkeypatch.setitem(sys.modules, module_name, module)

    sys.modules.pop("app.agents.runner", None)
    return importlib.import_module("app.agents.runner")


def _agent(tool_names: list[str]) -> Agent:
    now = datetime.now(UTC)
    return Agent(
        id="agent_e73ab23d7907",
        name="hackaton-movie-agent",
        system_prompt="CineBot can answer movie showtime questions.",
        model="claude-sonnet-4-5-20250929",
        tool_names=tool_names,
        sub_agent_ids=[],
        created_at=now,
        updated_at=now,
    )


def test_movie_agent_gets_movieglu_showtimes_tool(monkeypatch: Any) -> None:
    runner = _load_runner_with_adk_fakes(monkeypatch)

    built = runner.build_llm_agent(_agent(["movie_showtimes"]), agents_map={}, visited=set())

    assert built.kwargs["tools"] == [search_movie_showtimes]


def test_agent_without_tool_names_gets_no_tools(monkeypatch: Any) -> None:
    runner = _load_runner_with_adk_fakes(monkeypatch)

    built = runner.build_llm_agent(_agent([]), agents_map={}, visited=set())

    assert built.kwargs["tools"] == []
