"""LangGraph nodes for LLM-based decisions and research flow control.

These nodes integrate LLM functions into the story graph to enable intelligent
research intent detection and follow-up suggestions.
"""

import logging
from typing import Any

from .llm_research import (
    async_clarify_brief_intent,
    async_detect_research_intent,
    async_suggest_research_keywords,
)

logger = logging.getLogger(__name__)


async def node_detect_research_intent_llm(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Use LLM to detect if research is needed.
    
    Updates state with research intent classification and suggested keywords.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state dict with:
            - research_intent: "research_needed" | "clarification_needed" | "skip_research"
            - intent_confidence: float (0.0-1.0)
            - suggested_keywords: list[str]
            - intent_reason: str
    """
    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})
    message_history = state.get("message_history", [])

    logger.info("[llm_nodes] Detecting research intent via LLM...")

    result = await async_detect_research_intent(
        raw_brief=raw_brief,
        structured_brief=structured_brief,
        message_history=message_history,
        logger_instance=logger,
    )

    state["research_intent"] = "research_needed" if result["needs_research"] else "skip_research"
    state["intent_confidence"] = result["confidence"]
    state["suggested_keywords"] = result.get("suggested_keywords", [])
    state["intent_reason"] = result.get("reason", "")

    logger.info(
        f"[llm_nodes] Intent: {state['research_intent']}, "
        f"confidence: {state['intent_confidence']:.2f}"
    )

    return state


async def node_suggest_research_keywords(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Generate follow-up questions if research is needed.
    
    Uses LLM to suggest clarification questions based on initial research results.
    
    Args:
        state: Current story state with search results
        
    Returns:
        Updated state dict with:
            - follow_up_questions: list[str]
            - research_context_refined: str
            - refined_keywords: list[str]
    """
    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})
    search_results = state.get("search_results", [])

    logger.info("[llm_nodes] Suggesting research keywords via LLM...")

    result = await async_suggest_research_keywords(
        raw_brief=raw_brief,
        structured_brief=structured_brief,
        search_results=search_results,
        logger_instance=logger,
    )

    state["follow_up_questions"] = result.get("questions", [])
    state["research_context_refined"] = result.get("context", "")
    state["refined_keywords"] = result.get("keywords", [])

    logger.info(f"[llm_nodes] Generated {len(state['follow_up_questions'])} follow-up questions")

    return state


async def node_clarify_brief_intent_llm(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Ask LLM for brief clarification.
    
    Generates clarification questions if brief is ambiguous or incomplete.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state dict with:
            - clarification_questions: list[str]
            - missing_elements: list[str]
            - suggestions: list[str]
    """
    raw_brief = state.get("raw_brief", "")
    framework_id = state.get("framework_id", "")

    logger.info("[llm_nodes] Clarifying brief intent via LLM...")

    result = await async_clarify_brief_intent(
        raw_brief=raw_brief,
        framework_context=framework_id,
        logger_instance=logger,
    )

    state["clarification_questions"] = result.get("clarification_questions", [])
    state["missing_elements"] = result.get("missing_elements", [])
    state["llm_suggestions"] = result.get("suggestions", [])

    logger.info(f"[llm_nodes] Generated {len(state['clarification_questions'])} clarifications")

    return state


def router_research_intent(state: dict[str, Any]) -> str:
    """Router: Decide next node based on research intent.
    
    Routes to:
    - "research_pipeline" if research is needed and confidence is high (>0.6)
    - "clarification" if clarification is needed
    - "generate_story" otherwise
    """
    intent = state.get("research_intent", "skip_research")
    confidence = state.get("intent_confidence", 0.0)

    logger.info(f"[llm_nodes] Routing based on intent={intent}, confidence={confidence:.2f}")

    if intent == "research_needed" and confidence > 0.6:
        logger.info("[llm_nodes] → Routing to research_pipeline")
        return "research_pipeline"
    elif intent == "clarification_needed":
        logger.info("[llm_nodes] → Routing to clarification")
        return "clarification"
    else:
        logger.info("[llm_nodes] → Routing to generate_story (skip research)")
        return "generate_story"


def router_after_research(state: dict[str, Any]) -> str:
    """Router: Decide if we have enough research or should ask follow-ups.
    
    Routes to:
    - "generate_story" if we have good research context
    - "follow_up" if we need more specific information
    """
    research_context = state.get("research_context", "")
    scraped_content = state.get("scraped_content", [])

    logger.info(f"[llm_nodes] After research: context={len(research_context)} chars, "
                f"scraped={len(scraped_content)} URLs")

    # If we have decent research context, proceed to story generation
    if research_context and len(research_context) > 200:
        logger.info("[llm_nodes] → Routing to generate_story (sufficient research)")
        return "generate_story"

    # Otherwise, ask for clarification
    logger.info("[llm_nodes] → Routing to follow_up (need more details)")
    return "follow_up"
