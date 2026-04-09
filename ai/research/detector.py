"""Heuristics to detect when a brief should trigger web research."""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def should_research_brief(
    brief: str,
    structured_brief: dict[str, Any] | None = None,
) -> bool:
    """
    Determine if a brief warrants web research.

    Heuristics:
    - Mentions company/product names (capitalized words, recognized brands)
    - Contains keywords: "latest", "recent", "2026", "news", "announcement", "update"
    - References specific entities, people, or events
    - Asks for fact-based narratives

    Args:
        brief: Raw brief text.
        structured_brief: Optional parsed brief dict (from LLM).

    Returns:
        True if research should be performed.
    """
    if not brief:
        return False

    brief_lower = brief.lower()

    # Strong signals for research
    research_keywords = [
        "latest",
        "recent",
        "2026",
        "2025",
        "2024",
        "news",
        "announcement",
        "update",
        "product launch",
        "company",
        "startup",
        "funding",
        "acquisition",
        "partnership",
        "collaboration",
        "event",
        "release",
        "about ",  # "tell me about X"
        "research",
        "fact",
        "real-world",
        "case study",
        "example",
    ]

    if any(kw in brief_lower for kw in research_keywords):
        return True

    # Detect capitalized words (potential company/product names)
    # Regex: word starting with capital letter, length > 2
    capitalized = re.findall(r"\b[A-Z][a-z]{2,}\b", brief)
    if len(capitalized) >= 2:  # Multiple capitalized entities
        return True

    # Check structured brief for entity/person mentions
    if structured_brief:
        audience = structured_brief.get("audience", "").lower()
        objective = structured_brief.get("objective", "").lower()
        context = structured_brief.get("context", "").lower()

        full_structured = f"{objective} {audience} {context}".lower()
        if any(kw in full_structured for kw in ["company", "product", "brand", "person", "leader"]):
            return True

    return False


def extract_research_entity(brief: str) -> str:
    """
    Extract the main entity (company, product, person, topic) from brief.

    Returns the entity to search for, or empty string if none found.
    """
    # Try to find capitalized words (likely entities)
    capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", brief)
    if capitalized:
        return capitalized[0]  # Return first entity found

    # Fallback: extract text after "about", "for", "regarding"
    match = re.search(
        r"\b(?:about|for|regarding|for the|about the)\s+([a-z\s]+?)(?:\.|,|$)",
        brief,
        re.I,
    )
    if match:
        return match.group(1).strip()

    # Last resort: use first 3-5 words
    words = brief.split()
    if words:
        return " ".join(words[:3])

    return ""


def build_research_query(
    brief: str,
    structured_brief: dict[str, Any] | None = None,
) -> str:
    """
    Build a focused search query from brief.

    Args:
        brief: Raw brief text.
        structured_brief: Optional parsed brief dict.

    Returns:
        Search query string optimized for web search.
    """
    entity = extract_research_entity(brief)
    if not entity:
        return brief[:100]

    # Enhance with context if available
    context = ""
    if structured_brief:
        if "context" in structured_brief and structured_brief["context"]:
            context = structured_brief["context"]

    # Build query: entity + context + recency
    query = entity
    if context:
        query = f"{entity} {context}"
    if "2026" not in brief and "2025" not in brief:
        query += " 2026"

    return query[:120].strip()
