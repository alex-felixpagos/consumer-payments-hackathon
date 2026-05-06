"""WhatsApp chat ingress.

`POST /chat/{agent_name}` — receives a user message (phone_number + text), immediately
returns ``200``, runs the agent in the background, and sends the reply back to WhatsApp
via Kapso once the LLM responds.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.agents.runner import run_agent_turn
from app.agents.store import get_agent_by_name
from app.services.kapso_client import KapsoClient

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatPayload(BaseModel):
    phone_number: str = Field(..., min_length=5, description="Recipient phone number (E.164)")
    message: str = Field(..., min_length=1, description="The user's message text")


async def _process_turn(agent_name: str, agent_id: str, phone_number: str, message: str) -> None:
    """Background task: run a full agent turn and send the reply to WhatsApp."""
    from app.agents.store import get_agent

    try:
        agent = get_agent(agent_id)
        if agent is None:
            logger.error("Agent %s disappeared before background run", agent_id)
            return

        result = await run_agent_turn(
            agent=agent,
            phone_number=phone_number,
            user_message=message,
        )

        reply_text = result.get("response") or ""
        if not reply_text.strip():
            logger.warning("Agent %s produced empty reply for phone=%s", agent_name, phone_number)
            return

        try:
            client = KapsoClient()
            await client.send_whatsapp_message(phone_number, reply_text)
            logger.info(
                "Chat reply sent via Kapso — agent=%s phone=%s delegated_to=%s",
                agent_name,
                phone_number,
                result.get("delegated_to"),
            )
        except Exception:
            logger.exception("Failed to send reply via Kapso for agent=%s phone=%s", agent_name, phone_number)

    except Exception:
        logger.exception("Background agent turn failed — agent=%s phone=%s", agent_name, phone_number)


@router.post("/{agent_name}")
async def chat(agent_name: str, payload: ChatPayload, bg: BackgroundTasks) -> dict[str, str]:
    """
    Fire a user turn through the named agent. Returns 200 immediately; the reply
    is delivered asynchronously via Kapso to ``payload.phone_number``.
    """
    agent = get_agent_by_name(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    bg.add_task(_process_turn, agent_name, agent.id, payload.phone_number, payload.message)

    return {"status": "accepted", "agent": agent.name, "agent_id": agent.id}
