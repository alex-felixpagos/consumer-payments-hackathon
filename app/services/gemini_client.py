"""Gemini integration for BioVibe — classifies messages and generates replies."""

import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "biovibe_system.txt"


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def _load_prompt(self) -> str:
        return _PROMPT_PATH.read_text(encoding="utf-8")

    async def process_message(
        self,
        user_message: str,
        message_type: str,
        brain: dict,
    ) -> dict:
        system_prompt = (
            self._load_prompt()
            .replace("{user_profile}", json.dumps(brain["profile"]))
            .replace("{health_summary}", brain["health_summary"] or "No summary yet.")
            .replace("{recent_logs}", json.dumps(brain["log_history"][-10:]))
            .replace("{message_type}", message_type)
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )

        raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Gemini returned non-JSON response: %s", raw)
            return {
                "intent": "query",
                "category": None,
                "structured": {},
                "reply": raw,
            }

    async def summarize_brain(self, brain: dict) -> str:
        prompt = (
            "You are a health assistant. Based on the following health log entries, "
            "write a concise 3-sentence narrative summary of the user's health patterns. "
            "Plain text only, no bullet points or markdown.\n\n"
            f"Log entries:\n{json.dumps(brain['log_history'], indent=2)}"
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return response.text.strip()
