"""LangGraph nodes for research integration into the story generation pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from ai.graph import StoryState
from ai.research import (
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
    """
    Perform web search asynchronously.

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
    """
    Scrape content from search results.

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


def node_perform_search(state: StoryState) -> StoryState:
    """LangGraph node: perform web search if brief warrants it."""
    if not _should_enable_research():
        logger.info("[research] Research disabled")
        return state

    # Check if research was already done or is needed
    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})

    if not should_research_brief(raw_brief, structured_brief):
        logger.debug("[research] Brief doesn't warrant research")
        return state

    # Build query and perform search
    query = state.get("research_query") or build_research_query(raw_brief, structured_brief)
    state["research_query"] = query

    # Run async search synchronously (LangGraph doesn't support async nodes directly in single-thread mode)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context (e.g., handlers.py)
            # Return state and let caller run async_perform_search
            logger.info("[research] Delegating async search to handler")
            return state
    except RuntimeError:
        # No event loop, create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(async_perform_search(query))
        state["search_results"] = results
        logger.info(f"[research] Found {len(results)} results")
    except Exception as e:
        logger.error(f"[research] Search failed: {e}")
        state["search_results"] = []
    finally:
        if not loop.is_running():
            loop.close()

    return state


def node_scrape_content(state: StoryState) -> StoryState:
    """LangGraph node: scrape content from search results."""
    if not _should_enable_research():
        return state

    results = state.get("search_results", [])
    if not results:
        logger.debug("[research] No search results to scrape")
        return state

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.info("[research] Delegating async scrape to handler")
            return state
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        scraped = loop.run_until_complete(async_scrape_results(results))
        state["scraped_content"] = scraped
        logger.info(f"[research] Scraped {len(scraped)} articles")
    except Exception as e:
        logger.error(f"[research] Scraping failed: {e}")
        state["scraped_content"] = []
    finally:
        if not loop.is_running():
            loop.close()

    return state


def node_enrich_context(state: StoryState) -> StoryState:
    """LangGraph node: prepare research context string for prompt injection."""
    if not _should_enable_research():
        return state

    search_results = state.get("search_results", [])
    scraped = state.get("scraped_content", [])

    if not search_results and not scraped:
        return state

    # Build research context markdown
    context_parts = ["## Research Context\n"]

    if search_results:
        context_parts.append("### Search Results\n")
        for i, result in enumerate(search_results[:3], 1):
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            body = result.get("body", "")[:200]
            context_parts.append(f"{i}. **{title}**\n   URL: {url}\n   {body}\n")

    if scraped:
        context_parts.append("\n### Full Articles\n")
        for article in scraped[:2]:
            title = article.get("title", "Untitled")
            content = article.get("content", "")[:500]
            context_parts.append(f"**{title}**\n{content}\n\n---\n\n")

    research_context = "\n".join(context_parts)
    state["research_context"] = research_context
    logger.debug(f"[research] Enriched context ({len(research_context)} chars)")

    return state


async def async_enrich_context_full(state: StoryState) -> StoryState:
    """Fully async version of enrich: search + scrape + context in parallel."""
    if not _should_enable_research():
        return state

    raw_brief = state.get("raw_brief", "")
    structured_brief = state.get("structured_brief", {})

    if not should_research_brief(raw_brief, structured_brief):
        return state

    query = state.get("research_query") or build_research_query(raw_brief, structured_brief)
    state["research_query"] = query

    try:
        # Parallel: search + news
        results = await async_perform_search(query)
        state["search_results"] = results

        # Serial: scrape top results
        scraped = await async_scrape_results(results)
        state["scraped_content"] = scraped

        # Enrich context
        return node_enrich_context(state)

    except Exception as e:
        logger.error(f"[research] Full enrichment failed: {e}")
        return state
