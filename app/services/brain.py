"""Persistent memory layer for BioVibe — pure file I/O, no network calls."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _default_brain(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "profile": {
            "name": None,
            "traits": [],
        },
        "health_summary": "",
        "log_history": [],
    }


def load_brain(user_id: str) -> dict:
    _DATA_DIR.mkdir(exist_ok=True)
    path = _DATA_DIR / f"{user_id}.json"
    if not path.exists():
        brain = _default_brain(user_id)
        save_brain(user_id, brain)
        return brain
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Corrupted brain file for %s — resetting to default", user_id)
        return _default_brain(user_id)


def save_brain(user_id: str, brain: dict) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    path = _DATA_DIR / f"{user_id}.json"
    path.write_text(json.dumps(brain, indent=2, ensure_ascii=False), encoding="utf-8")


def append_log(user_id: str, entry: dict) -> dict:
    brain = load_brain(user_id)
    brain["log_history"].append({
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": entry["category"],
        "raw_input": entry["raw_input"],
        "media_type": entry["media_type"],
        "structured": entry.get("structured", {}),
    })
    save_brain(user_id, brain)
    return brain


def should_refresh_summary(brain: dict) -> bool:
    n = len(brain["log_history"])
    return n > 0 and n % 5 == 0


def update_summary(user_id: str, new_summary: str) -> None:
    brain = load_brain(user_id)
    brain["health_summary"] = new_summary
    save_brain(user_id, brain)


def update_profile(user_id: str, name: str | None, traits: list[str]) -> dict:
    brain = load_brain(user_id)
    if name:
        brain["profile"]["name"] = name
    existing_lower = {t.lower() for t in brain["profile"]["traits"]}
    for trait in traits:
        if trait.lower() not in existing_lower:
            brain["profile"]["traits"].append(trait)
            existing_lower.add(trait.lower())
    save_brain(user_id, brain)
    return brain
