# Web Search & Content Extraction Integration

## Overview

The storytelling agent now includes **automatic web research capabilities** that detect when a brief warrants research and inject real-world facts into story generation.

## Architecture

### Three Core Modules

#### 1. **Research Detection** (`ai/research/detector.py`)
- Heuristics-based: identifies briefs mentioning companies, products, dates (2026, 2025), keywords ("latest", "news", "announcement")
- Extracts entity names (company/product to search for)
- Builds optimized search queries with context and recency modifiers

#### 2. **Web Search** (`ai/research/websearch.py`)
Pure async functions:
- `search_web(query, max_results)` — DuckDuckGo search
- `search_recent_news(company_or_topic, max_results)` — News-specific search (adds "2026 news")
- `search_github_activity(company_or_repo, max_results)` — Filters GitHub repos

#### 3. **Content Extraction** (`ai/research/scraper.py`)
Trafilatura-based functions:
- `extract_content_from_url(url)` — Extracts main article text + title
- `extract_content_batch(urls)` — Concurrent extraction (max 3 parallel)
- `summarize_content(text)` — Truncates/summarizes at sentence boundaries

#### 4. **LangGraph Integration** (`ai/research_nodes.py`)
Async-first research pipeline:
- `node_perform_search()` — LangGraph node for web search
- `node_scrape_content()` — LangGraph node for content extraction
- `node_enrich_context()` — Prepares markdown-formatted research context
- `async_enrich_context_full()` — Orchestrates full pipeline (search + scrape + enrich)

### Data Flow

```
User Brief
    ↓
[detector.should_research_brief?] → NO → Generate Story (original path)
    ↓ YES
[async_perform_search] ← parallel search + news
    ↓
[async_scrape_results] ← extract top 3 URLs
    ↓
[node_enrich_context] ← format as markdown context
    ↓
[generate_story + research_context] → Prompt injection
    ↓
Fact-Grounded Story
```

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESEARCH_ENABLED` | `true` | Global enable/disable |
| `SEARCH_MAX_RESULTS` | `5` | Max results from DuckDuckGo |
| `SCRAPE_MAX_URLS` | `3` | Max URLs to extract (concurrency limited to 2) |

### .env Setup

```bash
# Copy example
cp .env.example .env

# Edit .env
RESEARCH_ENABLED=true
SEARCH_MAX_RESULTS=5
SCRAPE_MAX_URLS=3
```

## Usage

### Automatic Activation

Research is triggered automatically when:
- Brief mentions **company/product names** (capitalized words, recognized brands)
- Contains **keywords**: "latest", "recent", "2026", "news", "announcement", "update", "funding", "acquisition", etc.
- References **specific entities** (person, organization, event)
- Asks for **fact-based narratives** ("case study", "real-world example")

### Manual Control

```python
from ai.research import should_research_brief, build_research_query
from ai.research_nodes import async_enrich_context_full

# Check if brief warrants research
if should_research_brief(raw_brief):
    # Build optimized query
    query = build_research_query(raw_brief, structured_brief)
    
    # Run full research pipeline
    research_state = await async_enrich_context_full(state)
    research_context = research_state["research_context"]
```

## Integration Points

### 1. **handlers.py** — `iter_generate_full_story()`
```python
# Before story generation
research_state = await async_enrich_context_full(state)
research_context = research_state.get("research_context", "")

# Pass to story generator
story = await generate_story(
    brief, framework_id, 
    logger=logger,
    research_context=research_context  # NEW
)
```

### 2. **story_generator.py** — `generate_story()`
```python
async def generate_story(
    brief: dict[str, str],
    framework_id: str,
    *,
    logger: Any = None,
    research_context: str = "",  # NEW
) -> str:
    # If research_context provided, inject into prompt
    if research_context:
        prompt += f"\n\nREFERENCE RESEARCH:\n{research_context}\n"
```

### 3. **graph.py** — Extended `StoryState`
```python
class StoryState(TypedDict, total=False):
    # ... existing fields ...
    research_query: str                    # NEW
    search_results: list[dict[str, str]]  # NEW
    scraped_content: list[dict[str, str]] # NEW
    research_context: str                  # NEW
```

## Error Handling

Research gracefully degrades on failure:

```python
try:
    results = await async_perform_search(query)
    state["search_results"] = results
except Exception as e:
    logger.error(f"[research] Search failed: {e}")
    state["search_results"] = []  # Empty list, story proceeds
```

**Result:** If search or scrape fails, story generation continues with the original brief only. No blocking errors.

## Performance Notes

### Concurrency
- **Web Search**: DuckDuckGo (single async request per call)
- **Content Extraction**: Up to 2 concurrent URL fetches (semaphore limited)
- **Parallel Orchestration**: Search + news run in parallel via `asyncio.gather()`

### Timeouts
- URL fetch timeout: 10 seconds per URL
- Can be configured in `extract_content_batch(..., timeout=10)`

### Caching
- Search results cached in state (not persisted to DB)
- Re-run only per brief → framework → generate cycle

## Testing Research

### Quick Test

```python
import asyncio
from ai.research import search_web, extract_content_batch

async def test_research():
    # Test web search
    results = await search_web("OpenAI GPT-5 2026", max_results=3)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  - {r['title']}")
    
    # Test content extraction
    urls = [r["url"] for r in results[:2]]
    content = await extract_content_batch(urls)
    print(f"Extracted {len(content)} articles")

asyncio.run(test_research())
```

### Example Brief That Triggers Research

```
Write a pitch about Anthropic's latest AI capabilities for enterprise customers.
Audience: CTO, 10 min pitch
Format: Presentation
```

**Detection Result:**
- ✓ "Anthropic" (capitalized entity)
- ✓ "latest" (keyword)
- ✓ "AI capabilities" (domain-specific)
- → **Research Enabled** → Searches for "Anthropic latest 2026"

## Backward Compatibility

✓ **Fully backward compatible**
- Non-research briefs bypass research nodes entirely
- Existing API unchanged
- Research is opt-in via heuristics, not required

## Future Enhancements

Potential additions:
1. **LLM-based summarization** of scraped content (vs. truncation)
2. **Citation tracking** (mark which sentences came from research)
3. **GitHub API** for deep repo/org research
4. **Real-time validation** of facts in generated stories
5. **Custom search providers** (Bing, Google, Serpapi)
6. **Research result ranking** by relevance score

## Troubleshooting

### Research Not Triggering
- Check `RESEARCH_ENABLED=true` in `.env`
- Verify brief contains detectable keywords or entities
- Set `LOG_LEVEL=DEBUG` and check logs for `[research]` messages

### Slow Generation
- Research timeout: default 10s per URL
- Reduce `SEARCH_MAX_RESULTS` or `SCRAPE_MAX_URLS`
- Check network connectivity to DuckDuckGo / target sites

### Content Extraction Failures
- Some sites block automated scraping (trafilatura respects robots.txt)
- HTML structure may not be extractable
- Check logs: `[scraper] Failed to extract from {url}: ...`

## References

- **DuckDuckGo Search**: https://github.com/deedy5/duckduckgo_search
- **Trafilatura**: https://trafilatura.io/
- **LangGraph**: https://python.langchain.com/docs/langgraph/
- **httpx**: https://www.python-httpx.org/
