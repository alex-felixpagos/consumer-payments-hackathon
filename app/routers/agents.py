"""REST endpoints for the dynamic agent registry."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.agents.models import list_anthropic_models, model_ids
from app.agents import schemas, store
from app.agents.runner import run_agent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=list[schemas.ModelInfo])
async def list_models() -> list[schemas.ModelInfo]:
    """Available Claude models for the dropdown."""
    return await list_anthropic_models()


@router.get("", response_model=list[schemas.Agent])
async def list_agents() -> list[schemas.Agent]:
    return store.list_agents()


@router.post("", response_model=schemas.Agent, status_code=201)
async def create_agent(payload: schemas.AgentCreate) -> schemas.Agent:
    if payload.model not in await model_ids():
        raise HTTPException(status_code=400, detail=f"Unknown model: {payload.model}")
    try:
        agent = store.create_agent(payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    logger.info("Agent created id=%s name=%s", agent.id, agent.name)
    return agent


@router.get("/{agent_id}", response_model=schemas.Agent)
async def get_agent(agent_id: str) -> schemas.Agent:
    agent = store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=schemas.Agent)
async def update_agent(agent_id: str, payload: schemas.AgentUpdate) -> schemas.Agent:
    if payload.model is not None and payload.model not in await model_ids():
        raise HTTPException(status_code=400, detail=f"Unknown model: {payload.model}")
    try:
        agent = store.update_agent(agent_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str) -> None:
    if not store.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/{agent_id}/chat", response_model=schemas.ChatResponse)
async def chat(agent_id: str, payload: schemas.ChatRequest) -> schemas.ChatResponse:
    """Optional helper endpoint — fire one user turn through the agent."""
    try:
        result = await run_agent(agent_id=agent_id, user_message=payload.message, user_id=payload.user_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except RuntimeError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err
    return schemas.ChatResponse(**result)
