"""Re-exports for a stable ``from ai.intent import …`` surface."""

from __future__ import annotations

from .router import route_user_message, unified_turn_decision

__all__ = ["route_user_message", "unified_turn_decision"]
