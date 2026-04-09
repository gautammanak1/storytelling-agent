# Research Integration Dependencies

To enable web search and content extraction for the storytelling agent, install the following dependencies:

## Core Research Packages

```bash
pip install duckduckgo-search==3.9.5
pip install trafilatura==1.6.5
pip install httpx>=0.24.0
```

## Using uv (Recommended)

```bash
uv add duckduckgo-search trafilatura httpx
```

## Package Descriptions

| Package | Version | Purpose |
|---------|---------|---------|
| `duckduckgo-search` | 3.9.5+ | Async DuckDuckGo web search integration |
| `trafilatura` | 1.6.5+ | High-quality content extraction from HTML |
| `httpx` | 0.24.0+ | Async HTTP client for fetching web pages |

## Installation Notes

- All packages support Python 3.10+
- `duckduckgo-search` provides async context managers for concurrent requests
- `trafilatura` is production-ready and used by newsroom/research projects
- `httpx` is the modern async alternative to `requests`

## Optional: For Enhanced Performance

```bash
uv add asyncio-contextmanager  # Better async context handling
```

## Verification

To verify installation, run:

```python
from duckduckgo_search import AsyncDDGS
from trafilatura import extract
import httpx

print("✓ All research dependencies installed")
```

## Configuration

Set these environment variables in `.env` to control research behavior:

```env
RESEARCH_ENABLED=true
SEARCH_MAX_RESULTS=5
SCRAPE_MAX_URLS=3
```

See `.env.example` for all available options.
