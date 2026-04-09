"""
Pre-LangGraph router: one ASI1 call per ``PROMPT.md`` (no separate heuristics).
"""

from __future__ import annotations

from typing import Any

from .llm_client import unified_turn_decision
from .models import PromptRoute

__all__ = ["route_user_message", "unified_turn_decision"]


async def route_user_message(
    *,
    raw_text: str,
    logger: Any | None = None,
) -> PromptRoute:
    text = raw_text if raw_text is not None else ""
    decision = await unified_turn_decision(user_text=text, logger=logger)

    if decision.action == "reply_only":
        msg = decision.message or ""
        if logger:
            kind = "empty" if not text.strip() else "reply_only"
            logger.info(f"[router] unified {kind} len_reply={len(msg)}")
        return PromptRoute(allowed=False, refusal_message=msg)

    if logger:
        logger.info(f"[router] unified continue_pipeline text='{text[:80]}'")
    return PromptRoute(allowed=True, prompt=text.strip())
