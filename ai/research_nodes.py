"""LangGraph async nodes for research integration into the story generation pipeline.

Properly async-compatible nodes that integrate web search, content extraction,
and research context enrichment into the story generation flow.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .graph import StoryState
from .research import (
    build_research_query,
    extract_content_batch,
    search_recent_news,
    search_web,
    should_research_brief,
)

logger = logging.getLogger(__name__)


def _should_enable_research() -> bool:
    """Check if research is enabled via environment variable."""
    return os.getenv("RESEARCH_ENABLED", "true").lower() in {"true", "1", "yes"}


def _get_max_search_results() -> int:
    """Get max search results from env."""
    try:
        return int(os.getenv("SEARCH_MAX_RESULTS", "5"))
    except ValueError:
        return 5


def _get_max_scrape_urls() -> int:
    """Get max URLs to scrape from env."""
    try:
        return int(os.getenv("SCRAPE_MAX_URLS", "3"))
    except ValueError:
        return 3


async def async_perform_search(
    query: str,
    max_results: int | None = None,
) -> list[dict[str, str]]:
    """Perform web search asynchronously.

    Args:
        query: Search query.
        max_results: Max results (uses env default if None).

    Returns:
        List of search results.
    """
    max_results = max_results or _get_max_search_results()
    logger.info(f"[research] Searching: '{query}' (max {max_results})")

    # Run web search + news search in parallel
    web_task = search_web(query, max_results=max_results)
    news_task = search_recent_news(query, max_results=max_results // 2)

    web_results, news_results = await asyncio.gather(web_task, news_task, return_exceptions=False)

    # Combine and deduplicate by URL
    seen_urls = set()
    combined = []
    for result in web_results + news_results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            combined.append(result)
            seen_urls.add(url)
        if len(combined) >= max_results:
            break

    return combined[:max_results]


async def async_scrape_results(
    results: list[dict[str, str]],
    max_urls: int | None = None,
) -> list[dict[str, str]]:
    """Scrape content from search results.

    Args:
        results: List of search results with 'url' keys.
        max_urls: Max URLs to scrape (uses env default if None).

    Returns:
        List of scraped content dicts.
    """
    max_urls = max_urls or _get_max_scrape_urls()
    urls = [r.get("url") for r in results if r.get("url")][:max_urls]

    if not urls:
        logger.info("[research] No URLs to scrape")
        return []

    logger.info(f"[research] Scraping {len(urls)} URLs")
    scraped = await extract_content_batch(urls, max_concurrent=2)
    return scraped


# Async LangGraph Nodes - these are directly awaitable in LangGraph v0.1+

async def node_perform_search(state: StoryState) -> dict[str, Any]:
    """LangGraph async node: perform web search if brief warrants it."""
    if not _should_enable_research():
        logger.info("[research] Research disabled")
        return {}

    # Check if research was already done or is needed
    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})

    if not should_research_brief(raw_brief, structured_brief):
        logger.debug("[research] Brief doesn't warrant research")
        return {}

    # Build query and perform search
    query = state.get("research_query") or build_research_query(raw_brief, structured_brief)

    try:
        results = await async_perform_search(query)
        logger.info(f"[research] Found {len(results)} results")
        return {
            "research_query": query,
            "search_results": results,
        }
    except Exception as e:
        logger.error(f"[research] Search failed: {e}", exc_info=True)
        return {
            "research_query": query,
            "search_results": [],
        }


async def node_scrape_content(state: StoryState) -> dict[str, Any]:
    """LangGraph async node: scrape content from search results."""
    if not _should_enable_research():
        return {}

    results = state.get("search_results", [])
    if not results:
        logger.debug("[research] No search results to scrape")
        return {}

    try:
        scraped = await async_scrape_results(results)
        logger.info(f"[research] Scraped {len(scraped)} articles")
        return {"scraped_content": scraped}
    except Exception as e:
        logger.error(f"[research] Scraping failed: {e}", exc_info=True)
        return {"scraped_content": []}


async def node_enrich_context(state: StoryState) -> dict[str, Any]:
    """LangGraph async node: prepare research context string for prompt injection."""
    if not _should_enable_research():
        return {}

    search_results = state.get("search_results", [])
    scraped = state.get("scraped_content", [])

    if not search_results and not scraped:
        return {}

    # Build research context markdown
    context_parts = ["## Research Context\n"]

    if search_results:
        context_parts.append("### Search Results\n")
        for result in search_results[:5]:
            title = result.get("title", "No title")
            url = result.get("url", "")
            snippet = result.get("snippet", "")[:150]
            context_parts.append(f"- **{title}** ({url})\n  {snippet}\n")

    if scraped:
        context_parts.append("\n### Full Article Content\n")
        for article in scraped[:3]:
            source = article.get("url", "Unknown")
            content = article.get("content", "")[:500]
            summary = article.get("summary", "")
            context_parts.append(f"\n#### From {source}\n{summary}\n{content}\n")

    research_context = "\n".join(context_parts)
    logger.info(f"[research] Built context: {len(research_context)} chars")

    return {"research_context": research_context}


def router_should_research(state: StoryState) -> str:
    """Router: determine if we should enter research pipeline.
    
    Returns:
        "research" if brief warrants research, "skip" otherwise
    """
    if not _should_enable_research():
        return "skip"

    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})

    should_research = should_research_brief(raw_brief, structured_brief)
    logger.info(f"[research] Router: should_research={should_research}")

    return "research" if should_research else "skip"


def router_has_research_context(state: StoryState) -> str:
    """Router: check if we have sufficient research context.
    
    Returns:
        "proceed" if research_context exists and has content, "skip" otherwise
    """
    research_context = state.get("research_context", "")
    has_context = bool(research_context and len(research_context) > 100)

    logger.info(f"[research] Has research context: {has_context} ({len(research_context)} chars)")

    return "proceed" if has_context else "skip"


# High-level orchestration function for external use
async def async_enrich_context_full(state: StoryState) -> dict[str, Any]:
    """Orchestrate full research pipeline (search -> scrape -> enrich).
    
    This is the entry point for external handlers that need to run research
    without being part of the LangGraph.
    
    Args:
        state: Current story state
        
    Returns:
        Updated state dict with research results
    """
    logger.info("[research] Starting full research pipeline...")

    # Step 1: Check if research is needed
    if not _should_enable_research():
        logger.info("[research] Research disabled globally")
        return {}

    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})

    if not should_research_brief(raw_brief, structured_brief):
        logger.info("[research] Brief doesn't warrant research (skipping)")
        return {}

    # Step 2: Build query and search
    query = build_research_query(raw_brief, structured_brief)
    logger.info(f"[research] Pipeline: searching for '{query}'")

    try:
        search_results = await async_perform_search(query)
        logger.info(f"[research] Pipeline: got {len(search_results)} search results")

        if not search_results:
            return {
                "research_query": query,
                "search_results": [],
                "scraped_content": [],
                "research_context": "",
            }

        # Step 3: Scrape content
        scraped = await async_scrape_results(search_results)
        logger.info(f"[research] Pipeline: scraped {len(scraped)} articles")

        # Step 4: Enrich context (combine search + scraped into markdown)
        context_parts = ["## Research Context\n"]

        if search_results:
            context_parts.append("### Search Results\n")
            for result in search_results[:5]:
                title = result.get("title", "No title")
                url = result.get("url", "")
                snippet = result.get("snippet", "")[:150]
                context_parts.append(f"- **{title}**\n  {snippet}\n  URL: {url}\n")

        if scraped:
            context_parts.append("\n### Full Article Summaries\n")
            for article in scraped[:3]:
                source = article.get("url", "Unknown")
                content = article.get("content", "")[:500]
                summary = article.get("summary", "")
                context_parts.append(f"\n#### From {source}\n**Summary:** {summary}\n\n{content}\n")

        research_context = "\n".join(context_parts)
        logger.info(f"[research] Pipeline: enriched context to {len(research_context)} chars")

        return {
            "research_query": query,
            "search_results": search_results,
            "scraped_content": scraped,
            "research_context": research_context,
        }

    except Exception as e:
        logger.error(f"[research] Pipeline failed: {e}", exc_info=True)
        return {
            "research_context": "",
        }
