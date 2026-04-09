# Web Search & Content Extraction Integration - Implementation Summary

## What Was Built

You now have a **production-ready web research system** integrated into your storytelling agent using LangGraph. The system automatically detects research-worthy briefs, performs parallel web searches, extracts article content, and injects findings into story generation.

---

## New Files Created

### Core Research Modules (`ai/research/`)

1. **`websearch.py`** - Async web search using DuckDuckGo
   - `search_web(query, max_results)` - General web search
   - `search_recent_news(company, max_results)` - News-specific search with year modifier
   - `search_github_activity(company_or_repo, max_results)` - GitHub-filtered search

2. **`scraper.py`** - Content extraction using Trafilatura
   - `extract_content_from_url(url)` - Extract article text and metadata
   - `extract_content_batch(urls)` - Concurrent extraction with concurrency limit
   - `summarize_content(text)` - Intelligently truncate at sentence boundaries

3. **`detector.py`** - Research heuristics
   - `should_research_brief(brief_text)` - Detect if brief mentions companies/products/dates
   - `extract_research_entity(brief_text)` - Find what to search for
   - `build_research_query(entity, context)` - Construct optimized search query

4. **`__init__.py`** - Module exports for clean imports

### Integration & Orchestration

5. **`ai/research_nodes.py`** - LangGraph research pipeline
   - `async_perform_search()` - Async web search node
   - `async_scrape_results()` - Async content extraction node
   - `node_enrich_context()` - Format research as markdown context
   - `async_enrich_context_full()` - Full pipeline orchestrator (detects → searches → scrapes → formats)

### Core Agent Extensions

6. **`ai/graph.py`** - Extended `StoryState` with research fields
   - `research_query: str` - Query that was searched
   - `search_results: list[dict[str, str]]` - Web search results
   - `scraped_content: list[dict[str, str]]` - Extracted article content
   - `research_context: str` - Formatted markdown for prompt injection

7. **`ai/handlers.py`** - Updated story generation handler
   - Now calls `async_enrich_context_full()` before generation
   - Passes `research_context` to `generate_story()`
   - Graceful fallback if research fails

8. **`ai/story_generator.py`** - Enhanced prompt generation
   - Accepts optional `research_context` parameter
   - Injects research as "REFERENCE RESEARCH" section in prompt
   - Adds instruction to use research for grounding narrative

---

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
RESEARCH_ENABLED=true              # Enable/disable research
SEARCH_MAX_RESULTS=5               # Max DuckDuckGo results per query
SCRAPE_MAX_URLS=3                  # Max URLs to extract (concurrent limit: 2)
```

See `.env.example` for full template.

---

## How It Works

### Research Detection Flow

```
Brief from User
    ↓
[detector.should_research_brief()] 
    ├─ NO → Skip research, generate story normally
    └─ YES
       ├─ Extract entity (company/product name)
       ├─ Build optimized search query
       └─ Perform parallel search + scrape
           ├─ search_web() - General results
           ├─ search_recent_news() - News-specific
           └─ extract_content_batch() - Get full articles
       ↓
       [Format as markdown context]
       ↓
       [Inject into story generation prompt]
       ↓
       [Fact-grounded narrative]
```

### Example: Research-Triggered Brief

**User Brief:**
```
"Create a pitch about OpenAI's latest announcements for investors"
```

**Auto-Detection:**
- ✓ Contains company name: "OpenAI"
- ✓ Contains recency keyword: "latest"
- → **Research triggered**

**What Happens:**
1. Searches for "OpenAI 2026 announcements" + "OpenAI latest news"
2. Extracts top 3 URLs for full article content
3. Formats findings:
   ```
   REFERENCE RESEARCH:
   - OpenAI Announces... (source)
   - OpenAI Releases... (source)
   ```
4. Injects into prompt with instruction: "Use the research provided to ground your narrative in facts."
5. Story generation creates fact-based investor pitch

### Graceful Degradation

If research fails:
- Logs error but continues
- Falls back to brief-only generation
- User still gets a story, just without research enhancement

---

## Dependencies

The research modules require:

```
aiohttp>=3.9.0        # Async HTTP requests
duckduckgo-search     # DuckDuckGo API
trafilatura>=1.6.0    # Article extraction
```

Install with:
```bash
pip install aiohttp duckduckgo-search trafilatura>=1.6.0
```

See `RESEARCH_REQUIREMENTS.md` for details.

---

## Integration Points

### In `handlers.py`
```python
# Story generation now includes research
research_state = await async_enrich_context_full(state)
research_context = research_state.get("research_context", "")
story = await generate_story(brief, framework_id, research_context=research_context)
```

### In `story_generator.py`
```python
async def generate_story(
    brief: dict[str, str],
    framework_id: str,
    *,
    logger: Any = None,
    research_context: str = "",  # NEW PARAMETER
) -> str:
    # Injects research into prompt if provided
```

---

## Features Added

✓ **Automatic research detection** - Smart heuristics identify research-worthy briefs  
✓ **Parallel async operations** - Search + scrape run concurrently for speed  
✓ **Concurrent content extraction** - Max 2 parallel URL extractions to avoid overload  
✓ **Markdown formatting** - Research output formats nicely for LLM consumption  
✓ **Environment control** - Enable/disable and configure via env vars  
✓ **Graceful fallback** - Story generates even if research fails  
✓ **Full backward compatibility** - Non-research briefs skip nodes entirely  
✓ **Logging & debugging** - Info logs for research actions (search, scrape, enrich)  

---

## Testing the Integration

### Trigger Research
```
"Tell me about Anthropic's recent breakthroughs"
→ Searches "Anthropic 2026 breakthroughs" + "Anthropic latest news"
→ Extracts full articles
→ Injects into story
```

### Skip Research
```
"Create a fictional story about a startup"
→ No company names or recency keywords
→ No research performed
→ Story generates normally
```

---

## Next Steps (Optional Enhancements)

1. **Add search result caching** - Cache results for 24h to reduce API calls
2. **Web UI for research visibility** - Show which sources were used
3. **Custom entity dictionary** - Pre-defined list of important companies to always research
4. **Result ranking** - Score results by relevance before scraping
5. **Rate limiting** - Throttle searches if hitting API limits

---

## Documentation

- **`RESEARCH_INTEGRATION.md`** - Detailed architecture & usage guide
- **`RESEARCH_REQUIREMENTS.md`** - Dependency list & install instructions  
- **`README.md`** - Updated with research features section
- **`.env.example`** - Full environment variable template

---

## Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Install dependencies:**
   ```bash
   pip install aiohttp duckduckgo-search trafilatura>=1.6.0
   ```

3. **Test with research-worthy brief:**
   ```
   "Create a press release about Stripe's Q1 2026 announcements"
   ```

4. **Check logs for research activity:**
   ```
   [research] Checking if brief warrants research...
   [research] Research triggered for entity: Stripe
   [research] Injecting X chars of research
   ```

That's it! Your storytelling agent now has full web research capabilities integrated with LangGraph. Research happens automatically when briefs mention companies, products, or current events — with graceful fallback if anything fails.
