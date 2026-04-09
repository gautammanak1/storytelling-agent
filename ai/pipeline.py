"""Backward-compatible re-exports. Implementation lives in :mod:`ai.ai` (Instacart-style)."""

from __future__ import annotations

from .ai import ask, setup_ai_instance

setup_runtime = setup_ai_instance

__all__ = ["ask", "setup_runtime", "setup_ai_instance"]
