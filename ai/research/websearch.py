"""Web search integration using DuckDuckGo — pure, reusable functions."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def search_web(
    query: str,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        List of dicts with keys: 'title', 'url', 'body' (snippet).
    """
    try:
        # Use duckduckgo_search library — simpler async wrapper
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            results = await asyncio.to_thread(
                lambda: list(
                    ddgs.text(query, max_results=max_results, region="us")
                )
            )

        # Map DDGS keys to our schema
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"[research] Web search failed for query '{query}': {e}")
        return []


async def search_github_activity(
    company_or_repo: str,
    max_results: int = 3,
) -> list[dict[str, str]]:
    """
    Search for GitHub activity and repositories related to a company/topic.

    Args:
        company_or_repo: Company name or repository identifier.
        max_results: Maximum number of results.

    Returns:
        List of dicts with GitHub repo/activity info.
    """
    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            query = f"site:github.com {company_or_repo}"
            results = await asyncio.to_thread(
                lambda: list(
                    ddgs.text(query, max_results=max_results, region="us")
                )
            )

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"[research] GitHub search failed for '{company_or_repo}': {e}")
        return []


async def search_recent_news(
    company_or_topic: str,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """
    Search for recent news about a company or topic.

    Args:
        company_or_topic: Company or topic name.
        max_results: Maximum number of results.

    Returns:
        List of dicts with news headlines and links.
    """
    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            # Add year qualifier for recency
            query = f"{company_or_topic} 2026 news announcement"
            results = await asyncio.to_thread(
                lambda: list(
                    ddgs.text(query, max_results=max_results, region="us")
                )
            )

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"[research] News search failed for '{company_or_topic}': {e}")
        return []
