"""Agent runner powered by Google ADK with the Anthropic Claude client (via LiteLlm).

Builds a recursive `LlmAgent` tree from JSON config and runs single user turns
through it, reusing per-(agent, phone_number) sessions from `app.agents.runtime`.

ADK gives us automatic agent-transfer (delegation) when `sub_agents` are wired in.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

try:
    from litellm import acompletion
    from litellm.exceptions import (
        APIConnectionError,
        APIError,
        AuthenticationError,
        BadGatewayError,
        BadRequestError,
        InternalServerError,
        NotFoundError,
        PermissionDeniedError,
        RateLimitError,
        ServiceUnavailableError,
        Timeout,
    )
except ModuleNotFoundError:
    class APIConnectionError(Exception):
        pass

    class APIError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class BadGatewayError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class InternalServerError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class ServiceUnavailableError(Exception):
        pass

    class Timeout(Exception):
        pass

    async def acompletion(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("litellm is not installed. Run `pip install -r requirements.txt`.")

from app.agents.schemas import Agent
from app.agents.store import get_agent
from app.agents.tools import resolve_agent_tools
from app.config import get_settings

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
_RETRYABLE_LLM_ERRORS = (
    APIConnectionError,
    BadGatewayError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
_GEMINI_FALLBACK_ERRORS = (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadGatewayError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
_PAYMENT_LINK_MARKER_RE = re.compile(
    r"\[\[PAYMENT_(?:FLOW|LINK)\s+amount=(?P<amount>\d+(?:\.\d{1,2})?)\]\]",
    re.IGNORECASE,
)
_PAYMENT_FLOW_TOOL_INSTRUCTION = """

Payment link tool
- When the user has selected the movie/order and the next step is payment, call `start_payment_flow`.
- Use amount 1.00 unless the exact payable total is known.
- After calling the tool, write a short confirmation or order summary and tell the user you are sending a secure payment link.
- Do not ask the user to type "pay 1".
- Put the tool's `final_response_marker` on its own final line. The server strips it and sends the payment link.
"""


class TransientAgentError(RuntimeError):
    """Raised when the LLM provider stays unavailable after retries."""


def _instruction_for_agent(agent: Agent) -> str:
    instruction = agent.system_prompt or "You are a helpful assistant."
    if "start_payment_flow" in agent.tool_names:
        instruction += _PAYMENT_FLOW_TOOL_INSTRUCTION
    return instruction


def _sanitize_identifier(name: str) -> str:
    """ADK requires agent names to be valid Python identifiers."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "agent"
    if cleaned[0].isdigit():
        cleaned = f"a_{cleaned}"
    return cleaned


def _extract_function_response(part: Any) -> tuple[str | None, Any]:
    function_response = getattr(part, "function_response", None)
    if not function_response:
        return None, None
    name = getattr(function_response, "name", None)
    response = getattr(function_response, "response", None)
    if isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
        response = response["result"]
    return name, response


def build_llm_agent(agent: Agent, agents_map: dict[str, Agent], visited: set[str]) -> Any:
    """Recursively build an ADK LlmAgent tree. Imports are deferred so the API still
    boots if google-adk isn't installed yet (e.g. fresh clone before `pip install`)."""
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm

    if agent.id in visited:
        sub_agents: list[Any] = []
    else:
        visited = visited | {agent.id}
        sub_agents = []
        for sid in agent.sub_agent_ids:
            sub = agents_map.get(sid)
            if sub is None:
                continue
            sub_agents.append(build_llm_agent(sub, agents_map, visited))

    description = (
        agent.system_prompt[:160].strip()
        if agent.system_prompt
        else f"Sub-agent {agent.name}"
    )

    return LlmAgent(
        name=_sanitize_identifier(agent.name) + f"_{agent.id[-6:]}",
        description=description,
        model=LiteLlm(model=f"anthropic/{agent.model}"),
        instruction=_instruction_for_agent(agent),
        tools=resolve_agent_tools(agent.tool_names),
        sub_agents=sub_agents,
    )


def _require_anthropic_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        settings_key = get_settings().anthropic_api_key.strip()
        if settings_key:
            os.environ["ANTHROPIC_API_KEY"] = settings_key
            return
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env so Claude calls can authenticate."
        )


def _require_gemini_key() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        settings_key = get_settings().gemini_api_key.strip()
        if settings_key:
            os.environ["GEMINI_API_KEY"] = settings_key
            return
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env so Gemini fallback can authenticate."
        )


def _gemini_model_id() -> str:
    configured = get_settings().gemini_fallback_model.strip() or "gemini/gemini-2.5-flash"
    if configured.startswith("gemini/"):
        return configured
    return f"gemini/{configured}"


def _normalize_payment_trigger(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    if (
        value.get("type") in {"payment_flow_trigger", "payment_link_trigger"}
        or value.get("trigger_payment_flow") is True
        or value.get("trigger_payment_link") is True
    ):
        amount_raw = value.get("amount")
        try:
            if amount_raw is None and value.get("amount_cents") is not None:
                amount_raw = float(value["amount_cents"]) / 100
            amount = float(amount_raw if amount_raw is not None else 1.0)
        except (TypeError, ValueError):
            amount = 1.0
        if amount <= 0:
            amount = 1.0
        return {
            "amount": amount,
            "amount_cents": int(round(amount * 100)),
            "movie_title": value.get("movie_title"),
            "order_summary": value.get("order_summary"),
        }

    for nested_key in ("result", "response", "content", "output"):
        nested = value.get(nested_key)
        trigger = _normalize_payment_trigger(nested)
        if trigger:
            return trigger
    return None


def _payment_trigger_from_part(part: Any) -> dict[str, Any] | None:
    function_response = getattr(part, "function_response", None)
    if not function_response:
        return None

    name = getattr(function_response, "name", None)
    response = getattr(function_response, "response", None)
    if isinstance(function_response, dict):
        name = function_response.get("name", name)
        response = function_response.get("response", response)

    if name and name != "start_payment_flow":
        return None
    return _normalize_payment_trigger(response)


def _extract_payment_marker(text: str) -> tuple[dict[str, Any] | None, str]:
    match = _PAYMENT_LINK_MARKER_RE.search(text)
    if not match:
        return None, text

    try:
        amount = float(match.group("amount"))
    except (TypeError, ValueError):
        amount = 1.0
    cleaned = _PAYMENT_LINK_MARKER_RE.sub("", text).strip()
    return {
        "amount": amount,
        "amount_cents": int(round(amount * 100)),
        "movie_title": None,
        "order_summary": None,
    }, cleaned


async def _drive_runner(runner: Any, user_id: str, session_id: str, user_message: str) -> dict[str, Any]:
    """Drive a single user turn through an already-built runner+session."""
    from google.genai import types as genai_types

    content = genai_types.Content(role="user", parts=[genai_types.Part(text=user_message)])

    final_text = ""
    delegated_to: str | None = None
    payment_trigger: dict[str, Any] | None = None
    events_summary: list[dict[str, Any]] = []
    showtime_results: list[dict[str, Any]] = []
    root_name = runner.agent.name

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        author = getattr(event, "author", None)
        if author and author != root_name:
            delegated_to = author

        actions = getattr(event, "actions", None)
        if actions and getattr(actions, "transfer_to_agent", None):
            events_summary.append({"type": "transfer", "to": actions.transfer_to_agent})

        event_content = getattr(event, "content", None)
        event_parts = getattr(event_content, "parts", None) if event_content else None
        if event.is_final_response() and event_parts:
            for part in event_parts:
                if getattr(part, "text", None):
                    final_text += part.text
        if event_parts:
            for part in event_parts:
                maybe_trigger = _payment_trigger_from_part(part)
                if maybe_trigger:
                    payment_trigger = maybe_trigger
                tool_name, tool_response = _extract_function_response(part)
                if tool_name == "movie_showtimes" and isinstance(tool_response, dict):
                    results = tool_response.get("results")
                    if isinstance(results, list):
                        showtime_results = [item for item in results if isinstance(item, dict)]

    marker_trigger, final_text = _extract_payment_marker(final_text)
    if marker_trigger:
        payment_trigger = payment_trigger or marker_trigger
    if payment_trigger:
        events_summary.append({"type": "payment_link_trigger", **payment_trigger})

    return {
        "response": final_text,
        "delegated_to": delegated_to,
        "events": events_summary,
        "payment_trigger": payment_trigger,
        "showtime_results": showtime_results,
    }


async def _drive_runner_with_retries(
    runner: Any,
    user_id: str,
    session_id: str,
    user_message: str,
) -> dict[str, Any]:
    for attempt in range(len(_RETRY_DELAYS_SECONDS) + 1):
        try:
            return await _drive_runner(runner, user_id, session_id, user_message)
        except _RETRYABLE_LLM_ERRORS as exc:
            if attempt == len(_RETRY_DELAYS_SECONDS):
                raise TransientAgentError(
                    "Claude is temporarily unavailable after several retries."
                ) from exc

            delay = _RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "LLM provider returned a retryable error on attempt %s/%s; retrying in %.1fs: %s",
                attempt + 1,
                len(_RETRY_DELAYS_SECONDS) + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    raise TransientAgentError("Claude is temporarily unavailable.")


async def _drive_gemini_fallback(agent: Agent, user_message: str) -> dict[str, Any]:
    """Run one fallback response through Gemini when Claude is temporarily overloaded."""
    _require_gemini_key()
    model = _gemini_model_id()
    try:
        response = await acompletion(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{agent.system_prompt or 'You are a helpful assistant.'}\n\n"
                        "Claude is temporarily overloaded, so you are the Gemini fallback. "
                        "Reply naturally and concisely for WhatsApp. Do not mention the fallback "
                        "unless the user asks."
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=800,
            temperature=0.7,
        )
    except _GEMINI_FALLBACK_ERRORS as exc:
        raise RuntimeError("Gemini fallback failed.") from exc

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("Gemini fallback returned no choices.")

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Gemini fallback returned an empty response.")

    return {
        "response": content,
        "delegated_to": None,
        "events": [{"type": "fallback", "to": model}],
        "fallback_model": model,
    }


async def run_agent_turn(
    agent: Agent,
    phone_number: str,
    user_message: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Run one user turn for `agent` on the (agent, phone_number) session.

    Reuses the cached `InMemoryRunner` so conversation history is preserved
    across calls. Serialises concurrent turns for the same conversation.
    """
    _require_anthropic_key()

    from app.agents import history, runtime

    effective_user_id = user_id or f"wa:{phone_number.lstrip('+')}"
    runner = runtime.get_runner(agent)
    session_id = await runtime.get_or_create_session_id(agent, phone_number, effective_user_id)

    lock = runtime.get_turn_lock(agent.id, phone_number)
    async with lock:
        try:
            result = await _drive_runner_with_retries(runner, effective_user_id, session_id, user_message)
        except TransientAgentError:
            logger.warning("Claude stayed unavailable; using Gemini fallback for agent=%s", agent.name)
            result = await _drive_gemini_fallback(agent, user_message)

    history.append_turn(
        agent_id=agent.id,
        phone_number=phone_number,
        session_id=session_id,
        user_id=effective_user_id,
        user_message=user_message,
        assistant_message=result.get("response") or "",
        delegated_to=result.get("delegated_to"),
        events=result.get("events") or [],
    )

    return {
        "agent_id": agent.id,
        "session_id": session_id,
        **result,
    }


async def run_agent(agent_id: str, user_message: str, user_id: str = "frontend-user") -> dict[str, Any]:
    """Backwards-compatible single-shot helper used by the optional /chat endpoint
    on the agents router. Uses the user_id itself as the conversation key."""
    agent = get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Agent '{agent_id}' not found")
    return await run_agent_turn(agent=agent, phone_number=user_id, user_message=user_message, user_id=user_id)
