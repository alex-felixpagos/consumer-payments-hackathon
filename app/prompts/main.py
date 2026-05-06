"""Tiny loader for markdown prompt templates living under ``ideas/prompts/``.

Usage::

    from ideas import prompts

    prompts.load("coach/router")     # -> ideas/prompts/coach/router.md
    prompts.load("coach/response")   # -> ideas/prompts/coach/response.md
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load(name: str) -> str:
    """Return the contents of ``ideas/prompts/<name>.md`` as a string."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
