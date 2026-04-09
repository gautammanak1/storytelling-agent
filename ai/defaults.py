"""Constants for ASI1 unified router (mirrors ``instacart-agent/ai/defaults.py`` style)."""

from __future__ import annotations

from typing import Final

# --- Unified turn (PROMPT.md + JSON) ---
UNIFIED_TEMPERATURE: Final[float] = 0.15
UNIFIED_MAX_OUTPUT_TOKENS: Final[int] = 4096

# Fallback replies when ASI1 is unavailable (no key / HTTP error).
GREETING_FALLBACK_REPLY: Final[str] = (
    "Hi — I'm your Storytelling agent. I help turn goals into clear business narratives "
    "(pitches, updates, change stories) using frameworks like Business, 4 C's, or Hero's Journey. "
    "Share your objective and audience when you're ready."
)
HELP_FALLBACK_REPLY: Final[str] = (
    "I help you structure and write persuasive stories for work: briefs, frameworks, drafts, "
    "and refinements. Describe what you're trying to communicate and who it's for."
)
