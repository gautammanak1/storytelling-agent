"""Content extraction from URLs — pure, reusable functions using Trafilatura."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def extract_content_from_url(
    url: str,
    timeout: int = 10,
) -> dict[str, str] | None:
    """
    Extract main article content from a URL using Trafilatura.

    Args:
        url: Target URL.
        timeout: Request timeout in seconds (default 10).

    Returns:
        Dict with keys: 'title', 'url', 'content' (main text), or None if extraction fails.
    """
    try:
        import httpx
        import trafilatura

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html = response.text

        # Extract content with Trafilatura
        extracted = trafilatura.extract(
            html,
            include_tables=True,
            include_comments=False,
            output_format="txt",
        )

        if not extracted:
            logger.debug(f"[scraper] No extractable content from {url}")
            return None

        # Parse title from HTML if available
        title_match = None
        try:
            from html.parser import HTMLParser

            class TitleExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.title = ""
                    self.in_title = False

                def handle_starttag(self, tag, attrs):
                    if tag == "title":
                        self.in_title = True

                def handle_endtag(self, tag):
                    if tag == "title":
                        self.in_title = False

                def handle_data(self, data):
                    if self.in_title:
                        self.title += data

            parser = TitleExtractor()
            parser.feed(html)
            title_match = parser.title.strip()
        except Exception:
            pass

        return {
            "title": title_match or "Extracted Content",
            "url": url,
            "content": extracted[:2000],  # Truncate to 2000 chars
        }

    except asyncio.TimeoutError:
        logger.warning(f"[scraper] Timeout fetching {url}")
        return None
    except Exception as e:
        logger.debug(f"[scraper] Failed to extract from {url}: {e}")
        return None


async def extract_content_batch(
    urls: list[str],
    max_concurrent: int = 3,
    timeout: int = 10,
) -> list[dict[str, str]]:
    """
    Extract content from multiple URLs concurrently.

    Args:
        urls: List of URLs to extract.
        max_concurrent: Max concurrent requests (default 3).
        timeout: Request timeout per URL in seconds.

    Returns:
        List of extracted content dicts (skips failed URLs).
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_extract(url: str) -> dict[str, str] | None:
        async with semaphore:
            return await extract_content_from_url(url, timeout=timeout)

    tasks = [bounded_extract(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    return [r for r in results if r is not None]


async def summarize_content(
    content: str,
    max_length: int = 500,
) -> str:
    """
    Summarize extracted content (for now, truncate to max_length).

    Args:
        content: Full extracted content text.
        max_length: Maximum summary length.

    Returns:
        Truncated/summarized content.
    """
    # Future: integrate with LLM for actual summarization
    # For now, smart truncation at sentence boundary
    if len(content) <= max_length:
        return content

    truncated = content[:max_length]
    # Try to cut at sentence boundary
    last_period = truncated.rfind(".")
    if last_period > max_length * 0.8:
        return truncated[: last_period + 1]

    return truncated + "..."
