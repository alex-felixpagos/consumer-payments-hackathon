"""Pydantic models for the dynamic agent registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Fallback Claude models used only if Anthropic's live model endpoint is unavailable.
# These are the strings expected by LiteLlm via google-adk (prefix "anthropic/" is added in the runner).
FALLBACK_MODELS: list[str] = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-opus-4-5-20251101",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-1-20250805",
]

DEFAULT_MODEL = "claude-sonnet-4-6"


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="Human-readable agent name")
    system_prompt: str = Field(default="", description="System / instruction prompt sent to the LLM")
    model: str = Field(default=DEFAULT_MODEL, description="Claude model id (no provider prefix)")
    tool_names: list[str] = Field(
        default_factory=list,
        description="Names of application tools this agent can call",
    )
    sub_agent_ids: list[str] = Field(
        default_factory=list,
        description="IDs of other agents that this agent can delegate the conversation to",
    )


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    system_prompt: str | None = None
    model: str | None = None
    tool_names: list[str] | None = None
    sub_agent_ids: list[str] | None = None


class Agent(AgentBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = Field(default="frontend-user")


class ChatResponse(BaseModel):
    agent_id: str
    session_id: str | None = None
    response: str
    delegated_to: str | None = None
    events: list[dict] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationHistory(BaseModel):
    agent_id: str
    phone_number: str
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessage] = Field(default_factory=list)


class ModelInfo(BaseModel):
    id: str
    display_name: str | None = None
    created_at: str | None = None
    provider: Literal["anthropic"] = "anthropic"
