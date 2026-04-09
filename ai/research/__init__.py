"""Research module for web search and content extraction."""

from .detector import build_research_query, extract_research_entity, should_research_brief
from .scraper import extract_content_batch, extract_content_from_url, summarize_content
from .websearch import search_github_activity, search_recent_news, search_web

__all__ = [
    "search_web",
    "search_github_activity",
    "search_recent_news",
    "extract_content_from_url",
    "extract_content_batch",
    "summarize_content",
    "should_research_brief",
    "extract_research_entity",
    "build_research_query",
]
