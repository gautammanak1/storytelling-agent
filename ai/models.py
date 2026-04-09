"""Typed contracts for routing (mirrors ``instacart-agent/ai/models.py`` style)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UnifiedTurnDecision(BaseModel):
    """Single ASI1 JSON result for pre-graph routing (see ``PROMPT.md``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal["reply_only", "continue_pipeline"]
    message: str | None = Field(
        default=None,
        description="Full user-visible reply when action is reply_only; must be null for continue_pipeline",
    )


class PromptRoute(BaseModel):
    """Result of pre-graph intent routing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool = Field(description="True → continue to LangGraph story pipeline")
    prompt: str = Field(default="", description="Echo of user text when allowed")
    refusal_message: str | None = Field(
        default=None,
        description="Assistant reply when allowed is False",
    )
