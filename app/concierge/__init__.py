"""
Felix Remittance Concierge — AI-first conversational layer.

Channel-agnostic. The agent owns the conversation; tools own the data and math.
Plug it behind any channel adapter (Kapso, CLI, Streamlit, etc.).
"""

from app.concierge.agent import respond

__all__ = ["respond"]
