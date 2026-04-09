"""LLM-based research intent detection and keyword suggestion.

Uses LLM to classify whether a brief needs research, generate follow-up questions,
and suggest research keywords for web search.
"""

import json
import logging
from typing import Any

from .llm_client import call_asi

logger = logging.getLogger(__name__)


RESEARCH_INTENT_SYSTEM = """You are a research assistant. Analyze user briefs and determine if research would improve the story.

Respond with JSON only (no other text):
{
  "needs_research": true/false,
  "confidence": 0.0-1.0,
  "reason": "explanation",
  "suggested_keywords": ["keyword1", "keyword2", "keyword3"]
}"""

RESEARCH_CLARIFICATION_SYSTEM = """You are a research clarification assistant. Generate 2-3 brief follow-up questions to help refine a story brief.

Respond with JSON only:
{
  "questions": ["question1?", "question2?", "question3?"],
  "context": "brief explanation of what you're asking for"
}"""


async def async_detect_research_intent(
    raw_brief: str,
    structured_brief: dict[str, str],
    message_history: list[str] | None = None,
    logger_instance: Any = None,
) -> dict[str, Any]:
    """Detect if brief should trigger research using LLM.
    
    Args:
        raw_brief: Original user input brief
        structured_brief: Structured brief dict (objective, audience, tone, etc.)
        message_history: Previous messages in conversation
        logger_instance: Logger instance
        
    Returns:
        {
            "needs_research": bool,
            "confidence": float,
            "reason": str,
            "suggested_keywords": list[str]
        }
    """
    logger_inst = logger_instance or logger

    brief_text = raw_brief
    if structured_brief:
        brief_lines = [f"{k}: {v}" for k, v in structured_brief.items() if v]
        brief_text = "\n".join(brief_lines)

    history_context = ""
    if message_history:
        history_context = f"\n\nConversation history:\n" + "\n".join(message_history[-3:])

    prompt = f"""Analyze this story brief and determine if research would help:

{brief_text}{history_context}

Should this brief trigger web research to ground the narrative in facts? Consider:
- Does it mention companies, products, people, or organizations?
- Does it reference recent events or current news (2025, 2026, "latest", "recent")?
- Would real-world facts improve the story?
- Are there specific claims that should be verified?"""

    try:
        response = await call_asi(
            prompt,
            system_instruction=RESEARCH_INTENT_SYSTEM,
            max_tokens=200,
        )
        logger_inst.info(f"[llm_research] Intent detection response: {response[:100]}")

        result = json.loads(response)
        return {
            "needs_research": result.get("needs_research", False),
            "confidence": result.get("confidence", 0.5),
            "reason": result.get("reason", ""),
            "suggested_keywords": result.get("suggested_keywords", []),
        }
    except json.JSONDecodeError as e:
        logger_inst.warning(f"[llm_research] Failed to parse intent response: {e}")
        return {
            "needs_research": False,
            "confidence": 0.0,
            "reason": "LLM response parsing failed",
            "suggested_keywords": [],
        }
    except Exception as e:
        logger_inst.error(f"[llm_research] Intent detection error: {e}", exc_info=True)
        return {
            "needs_research": False,
            "confidence": 0.0,
            "reason": f"Error: {str(e)[:100]}",
            "suggested_keywords": [],
        }


async def async_suggest_research_keywords(
    raw_brief: str,
    structured_brief: dict[str, str],
    search_results: list[dict[str, str]] | None = None,
    logger_instance: Any = None,
) -> dict[str, Any]:
    """Generate suggested research keywords for follow-up questions.
    
    Args:
        raw_brief: Original brief
        structured_brief: Structured brief
        search_results: Previous search results (if available)
        logger_instance: Logger instance
        
    Returns:
        {
            "questions": list[str],
            "context": str,
            "keywords": list[str]
        }
    """
    logger_inst = logger_instance or logger

    brief_text = raw_brief
    if structured_brief:
        brief_lines = [f"{k}: {v}" for k, v in structured_brief.items() if v]
        brief_text = "\n".join(brief_lines)

    results_context = ""
    if search_results:
        results_context = f"\n\nInitial search found {len(search_results)} results:\n"
        for r in search_results[:3]:
            results_context += f"- {r.get('title', 'N/A')}: {r.get('url', 'N/A')}\n"

    prompt = f"""Given this brief, generate 2-3 clarification questions to refine research:

{brief_text}{results_context}

Ask questions that would help narrow down the story focus and improve research accuracy."""

    try:
        response = await call_asi(
            prompt,
            system_instruction=RESEARCH_CLARIFICATION_SYSTEM,
            max_tokens=250,
        )
        logger_inst.info(f"[llm_research] Keyword suggestion response: {response[:100]}")

        result = json.loads(response)
        return {
            "questions": result.get("questions", []),
            "context": result.get("context", ""),
            "keywords": result.get("keywords", []),
        }
    except json.JSONDecodeError as e:
        logger_inst.warning(f"[llm_research] Failed to parse keyword response: {e}")
        return {
            "questions": [],
            "context": "Keyword parsing failed",
            "keywords": [],
        }
    except Exception as e:
        logger_inst.error(f"[llm_research] Keyword suggestion error: {e}", exc_info=True)
        return {
            "questions": [],
            "context": f"Error: {str(e)[:100]}",
            "keywords": [],
        }


async def async_clarify_brief_intent(
    raw_brief: str,
    framework_context: str = "",
    logger_instance: Any = None,
) -> dict[str, Any]:
    """Ask LLM for clarification on brief intent.
    
    Args:
        raw_brief: User's raw brief
        framework_context: Selected framework details
        logger_instance: Logger instance
        
    Returns:
        {
            "clarification_questions": list[str],
            "missing_elements": list[str],
            "suggestions": list[str]
        }
    """
    logger_inst = logger_instance or logger

    framework_info = f"\nSelected framework: {framework_context}" if framework_context else ""

    prompt = f"""Review this brief for clarity and completeness:

Brief: {raw_brief}{framework_info}

Generate 2-3 questions to clarify intent and fill gaps. Focus on:
- Who is the target audience?
- What is the core message or objective?
- What tone or style is desired?"""

    clarification_system = """Generate clarification questions as JSON:
{
  "clarification_questions": ["Q1?", "Q2?"],
  "missing_elements": ["element1", "element2"],
  "suggestions": ["suggestion1", "suggestion2"]
}"""

    try:
        response = await call_asi(
            prompt,
            system_instruction=clarification_system,
            max_tokens=250,
        )
        logger_inst.info(f"[llm_research] Clarification response: {response[:100]}")

        result = json.loads(response)
        return {
            "clarification_questions": result.get("clarification_questions", []),
            "missing_elements": result.get("missing_elements", []),
            "suggestions": result.get("suggestions", []),
        }
    except json.JSONDecodeError as e:
        logger_inst.warning(f"[llm_research] Failed to parse clarification: {e}")
        return {
            "clarification_questions": [],
            "missing_elements": [],
            "suggestions": [],
        }
    except Exception as e:
        logger_inst.error(f"[llm_research] Clarification error: {e}", exc_info=True)
        return {
            "clarification_questions": [],
            "missing_elements": [],
            "suggestions": [],
        }
