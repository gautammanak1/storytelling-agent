# LangGraph Nodes Quick Reference

## Node Registry

All async nodes that integrate into the StateGraph:

### LLM Decision Nodes

| Node | Input | Output | Purpose |
|------|-------|--------|---------|
| `node_detect_research_intent_llm` | `StoryState` | `dict` with research_intent, intent_confidence, suggested_keywords, intent_reason | Classify if brief needs research |
| `node_suggest_research_keywords` | `StoryState` (with search_results) | `dict` with follow_up_questions, research_context_refined, refined_keywords | Generate follow-up questions |
| `node_clarify_brief_intent_llm` | `StoryState` | `dict` with clarification_questions, missing_elements, llm_suggestions | Clarify ambiguous briefs |

### Research Nodes

| Node | Input | Output | Purpose |
|------|-------|--------|---------|
| `node_perform_search` | `StoryState` (with raw_brief) | `dict` with research_query, search_results | Web search via DuckDuckGo |
| `node_scrape_content` | `StoryState` (with search_results) | `dict` with scraped_content | Extract article content |
| `node_enrich_context` | `StoryState` (with search_results, scraped_content) | `dict` with research_context | Build context markdown |

### Router Functions

| Router | Input | Output | Purpose |
|--------|-------|--------|---------|
| `router_research_intent` | `StoryState` | "research_pipeline" \| "clarification" \| "generate_story" | Route based on LLM classification |
| `router_after_research` | `StoryState` | "generate_story" \| "follow_up" | Route based on research quality |
| `router_should_research` | `StoryState` | "research" \| "skip" | Check if brief warrants research |
| `router_has_research_context` | `StoryState` | "proceed" \| "skip" | Check research context sufficiency |

## Usage in StateGraph

### Add Async Nodes

```python
from langgraph.graph import StateGraph
from ai.llm_nodes import (
    node_detect_research_intent_llm,
    node_suggest_research_keywords,
    router_research_intent,
)
from ai.research_nodes import (
    node_perform_search,
    node_scrape_content,
    node_enrich_context,
    router_should_research,
)

graph = StateGraph(StoryState)

# Add nodes
graph.add_node("detect_research_intent", node_detect_research_intent_llm)
graph.add_node("perform_search", node_perform_search)
graph.add_node("scrape_content", node_scrape_content)
graph.add_node("enrich_context", node_enrich_context)
graph.add_node("suggest_keywords", node_suggest_research_keywords)
graph.add_node("generate_story", story_generation_node)
```

### Add Conditional Edges (Routers)

```python
# After detection, route based on LLM decision
graph.add_conditional_edges(
    "detect_research_intent",
    router_research_intent,
    {
        "research_pipeline": "perform_search",
        "clarification": "clarify_brief",
        "generate_story": "generate_story",
    }
)

# After search, check if we have enough context
graph.add_conditional_edges(
    "enrich_context",
    router_after_research,
    {
        "generate_story": "generate_story",
        "follow_up": "suggest_keywords",
    }
)
```

### Full Research Pipeline Chain

```python
# Research nodes execute sequentially
graph.add_edge("perform_search", "scrape_content")
graph.add_edge("scrape_content", "enrich_context")
```

## Async Execution

All nodes are truly async and support LangGraph's async execution:

```python
# In handlers or AI runtime:
async def handler():
    from ai.research_nodes import async_enrich_context_full
    
    # Run full research pipeline
    research_update = await async_enrich_context_full(state)
    state.update(research_update)
    
    # Or run individual nodes
    state_update = await node_perform_search(state)
    state.update(state_update)
```

## State Flow Examples

### Example 1: Research-Enabled Brief

```
Input: "Write about Apple's latest AI announcement"
    ↓
apply_story_event (brief → "collect_brief")
    ↓
node_detect_research_intent_llm
    → research_intent = "research_needed"
    → intent_confidence = 0.92
    → suggested_keywords = ["Apple AI announcement 2025", ...]
    ↓
router_research_intent → "research_pipeline"
    ↓
node_perform_search
    → search_results = [{"title": "...", "url": "...", "snippet": "..."}, ...]
    ↓
node_scrape_content
    → scraped_content = [{"url": "...", "content": "..."}, ...]
    ↓
node_enrich_context
    → research_context = "## Research Context\n..."
    ↓
node_generate_story (with research_context injected)
    → generated_story = "..."
```

### Example 2: Non-Research Brief

```
Input: "Help me write about my product's value"
    ↓
apply_story_event (brief → "collect_brief")
    ↓
node_detect_research_intent_llm
    → research_intent = "skip_research"
    → intent_confidence = 0.75
    ↓
router_research_intent → "generate_story"
    ↓
node_generate_story (without research context)
    → generated_story = "..."
```

### Example 3: Research with Follow-Up

```
Input: "Story about new tech"
    ↓
node_detect_research_intent_llm
    → research_intent = "clarification_needed"
    ↓
router_research_intent → "clarification"
    ↓
node_clarify_brief_intent_llm
    → clarification_questions = ["What specific tech?", ...]
    ↓
[User provides clarification]
    ↓
node_perform_search + pipeline
    → research_context = "..."
    ↓
node_generate_story
```

## Error Handling

All async nodes have try/except and return empty dicts on failure:

```python
async def node_perform_search(state):
    try:
        results = await async_perform_search(query)
        return {"search_results": results}
    except Exception as e:
        logger.error(f"[research] Search failed: {e}")
        return {"search_results": []}  # Graceful fallback
```

Generation still proceeds even if research fails (using brief only).

## Testing

```python
import asyncio
from ai.llm_nodes import node_detect_research_intent_llm
from ai.research_nodes import node_perform_search

async def test():
    state = {
        "raw_brief": "Apple's latest AI announcement",
        "structured_brief": {},
        "message_history": [],
    }
    
    # Test LLM node
    result = await node_detect_research_intent_llm(state)
    print(f"Intent: {result.get('research_intent')}")
    
    # Test research node  
    result2 = await node_perform_search(state)
    print(f"Found {len(result2.get('search_results', []))} results")

asyncio.run(test())
```

## Performance Notes

- **LLM nodes** take 2-5 seconds (LLM inference)
- **Search node** takes 3-8 seconds (DuckDuckGo API)
- **Scrape node** takes 5-15 seconds (2 concurrent URLs)
- **Enrich node** takes <1 second (markdown building)
- **Total research pipeline**: ~15-30 seconds for full flow

Tip: Use async execution in production to avoid blocking on wait times.

## Common Mistakes

1. ❌ Not awaiting async nodes
   ```python
   result = node_perform_search(state)  # Wrong
   result = await node_perform_search(state)  # Correct
   ```

2. ❌ Updating state in place instead of returning dict
   ```python
   state["research_intent"] = "..."  # Wrong
   return {"research_intent": "..."}  # Correct
   ```

3. ❌ Not handling missing state fields
   ```python
   query = state["research_query"]  # Wrong (KeyError if missing)
   query = state.get("research_query", "")  # Correct
   ```

4. ❌ Not awaiting message_history for multi-turn
   ```python
   await node_detect_research_intent_llm(state)  # No history
   
   state["message_history"] = ["prev message 1", "prev message 2"]
   await node_detect_research_intent_llm(state)  # With history
   ```
