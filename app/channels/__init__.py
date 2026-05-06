"""
Channel adapters — pluggable I/O.

The concierge agent doesn't know which channel it's on. Add a new channel by
implementing the Channel protocol in `base.py`.
"""

from app.channels.base import Channel
from app.channels.kapso import KapsoChannel, get_default_channel

__all__ = ["Channel", "KapsoChannel", "get_default_channel"]
