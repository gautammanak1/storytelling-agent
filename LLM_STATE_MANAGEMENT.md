# LLM-Based State Management & LangGraph Integration

## Overview

The storytelling agent now has **LLM-powered state management** with **LangGraph async node integration**. This document explains the architecture, state flow, and how to use the new LLM decision nodes.

## Architecture

### State Flow Diagram

```
User Input
    ↓
[Router: classify intent]
    ↓
apply_story_event (pure state transition)
    ↓
    ├─→ [LLM: detect_research_intent] → research_intent classification
    │
    ├─→ [Conditional: should_research?]
    │   │
    │   ├─→ YES: research_pipeline
    │   │   ├─→ [Async: perform_search]
    │   │   ├─→ [Async: scrape_content]
    │   │   └─→ [Async: enrich_context]
    │   │
    │   └─→ NO: skip_research → proceed_to_generation
    │
    ├─→ [LLM: suggest_keywords] (if initial research insufficient)
    │
    └─→ [Async: generate_story] (with research_context injection)
        ↓
    Output
```

## LLM-Based Modules

### 1. `ai/llm_research.py` - Research Intent Detection

Provides three main async functions:

#### `async_detect_research_intent()`
**Purpose:** Classify if a brief needs web research via LLM judgment.

```python
result = await async_detect_research_intent(
    raw_brief="Apple's latest AI announcement for enterprise customers",
    structured_brief={"objective": "...", "audience": "..."},
    message_history=["previous message 1", "previous message 2"],
)

# Returns:
{
    "needs_research": True,
    "confidence": 0.87,
    "reason": "Brief mentions Apple's specific announcement, which requires current facts",
    "suggested_keywords": ["Apple AI announcement 2025", "enterprise AI products", "Apple's latest tech"]
}
```

**When Used:**
- Before entering research pipeline (in `node_detect_research_intent_llm`)
- Takes into account conversation history for multi-turn follow-ups

#### `async_suggest_research_keywords()`
**Purpose:** Generate clarification questions to refine research.

```python
result = await async_suggest_research_keywords(
    raw_brief="Tell customers about our new AI feature",
    structured_brief={"objective": "..."},
    search_results=[...],  # From initial web search
)

# Returns:
{
    "questions": [
        "Which specific AI feature are you launching?",
        "What's the target market for this feature?",
        "Are there recent competitors we should address?"
    ],
    "context": "Clarification would help target the right audience and positioning",
    "keywords": ["AI feature launch", "market positioning", "competitive analysis"]
}
```

**When Used:**
- After initial search if results are insufficient
- Guides user toward more specific briefs

#### `async_clarify_brief_intent()`
**Purpose:** Ask LLM for clarifications on ambiguous or incomplete briefs.

```python
result = await async_clarify_brief_intent(
    raw_brief="Write a story about our product",
    framework_context="business_hero_journey"
)

# Returns:
{
    "clarification_questions": [
        "What problem does your product solve?",
        "Who is the target audience?",
        "What's the key differentiator vs competitors?"
    ],
    "missing_elements": ["target audience", "product differentiation", "use case"],
    "suggestions": [
        "Include customer success metrics",
        "Mention competitive positioning",
        "Define the customer journey stage"
    ]
}
```

**When Used:**
- During brief collection if initial input is too vague
- Helps guide users toward actionable briefs

### 2. `ai/llm_nodes.py` - LangGraph Nodes

Async LangGraph nodes that integrate LLM functions into the state graph.

#### `node_detect_research_intent_llm(state) → dict`
Updates state with LLM-based research classification.

**State Updates:**
- `research_intent`: "research_needed" | "skip_research" | "clarification_needed"
- `intent_confidence`: 0.0-1.0 score
- `suggested_keywords`: List of keywords for search
- `intent_reason`: Explanation for the classification

#### `node_suggest_research_keywords(state) → dict`
Generates follow-up questions based on search results.

**State Updates:**
- `follow_up_questions`: List of clarification questions
- `research_context_refined`: Explanation of what questions target
- `refined_keywords`: Refined search keywords

#### `node_clarify_brief_intent_llm(state) → dict`
Clarifies ambiguous briefs through LLM-generated questions.

**State Updates:**
- `clarification_questions`: Questions for the user
- `missing_elements`: Identified missing brief elements
- `llm_suggestions`: Improvement suggestions

### 3. Router Functions

#### `router_research_intent(state) → str`
Routes based on LLM research classification.

```
Returns: "research_pipeline" | "clarification" | "generate_story"
```

#### `router_after_research(state) → str`
Routes based on research result quality.

```
Returns: "generate_story" | "follow_up"
```

## Enhanced StoryState

New fields added to support LLM-based decisions:

```python
class StoryState(TypedDict, total=False):
    # ... existing fields ...
    
    # LLM research decision making
    research_intent: str  # Classification result
    intent_confidence: float  # 0.0-1.0
    intent_reason: str  # Why this decision
    suggested_keywords: list[str]  # LLM suggestions
    
    # Conversation context
    message_history: list[str]  # Previous messages
    follow_up_questions: list[str]  # Follow-up for user
    research_context_refined: str  # Refined context
    refined_keywords: list[str]  # Refined keywords
    
    # Brief clarification
    clarification_questions: list[str]
    missing_elements: list[str]
    llm_suggestions: list[str]
```

## Async Research Nodes

All research nodes are now **truly async** and integrate with LangGraph's async execution:

### `node_perform_search(state) → dict[str, Any]`
Async web search with DuckDuckGo.

```python
result = await node_perform_search(state)
# Returns: {"research_query": "...", "search_results": [...]}
```

### `node_scrape_content(state) → dict[str, Any]`
Async content extraction from URLs with Trafilatura.

```python
result = await node_scrape_content(state)
# Returns: {"scraped_content": [...]}
```

### `node_enrich_context(state) → dict[str, Any]`
Build research context markdown for prompt injection.

```python
result = await node_enrich_context(state)
# Returns: {"research_context": "## Research Context\n..."}
```

## Integrated Handlers

### `async_enrich_context_full(state) → dict`

High-level orchestration for external handlers (e.g., `handlers.py`):

```python
from ai.research_nodes import async_enrich_context_full

# In handler:
research_state = await async_enrich_context_full(state)
research_context = research_state.get("research_context", "")

# Pass to story generation
story = await generate_story(brief, framework_id, research_context=research_context)
```

This runs the full pipeline: search → scrape → enrich, with graceful fallback.

## Router Functions in Graph

```python
from .research_nodes import router_should_research, router_has_research_context
from .llm_nodes import router_research_intent, router_after_research

# In StateGraph:
graph.add_conditional_edges(
    "detect_research_intent",
    router_research_intent,
    {
        "research_pipeline": "perform_search",
        "clarification": "clarify_brief",
        "generate_story": "generate_story"
    }
)

graph.add_conditional_edges(
    "enrich_context",
    router_after_research,
    {
        "generate_story": "generate_story",
        "follow_up": "suggest_keywords"
    }
)
```

## Enhanced Greeting Flow

The agent now mentions research capabilities in greetings:

**Idle Stage (initial message):**
```
"Please describe what story or narrative you need — include the objective, audience, and format.

💡 Research Bonus: Mention specific companies, products, or recent events (e.g. 'Apple's latest announcement' 
or '2026 AI trends') and I'll automatically research and ground your narrative in real facts."
```

**Collect Brief Stage:**
```
"I'm here! Share your story brief — objective, audience, and format.

💡 Tip: Mention specific companies, products, or recent events for research-enhanced narratives 
(e.g., 'Apple's latest AI announcement' or 'emerging AI regulations 2026')"
```

**Generating Stage:**
```
"Still drafting your narrative — hang tight!

(I'm researching recent facts and events to ground the story, if your brief mentions them.)"
```

## Usage Example: Full Flow

```python
# 1. User sends brief mentioning specific company
user_input = "Write a pitch for Apple's latest AI announcement to enterprise customers"

# 2. Router processes and calls apply_story_event
state = await apply_story_event(prior_state, {"type": "chat", "control_text": user_input})
state["raw_brief"] = user_input
state["stage"] = "collect_brief"

# 3. Brief processing triggers:
state = await handlers.process_brief_and_generate(state)

# 4. LLM detects research need:
state = await node_detect_research_intent_llm(state)
# → state["research_intent"] = "research_needed"
# → state["intent_confidence"] = 0.92

# 5. Router sends to research pipeline:
if router_research_intent(state) == "research_pipeline":
    state = await node_perform_search(state)
    state = await node_scrape_content(state)
    state = await node_enrich_context(state)

# 6. Story generation uses research context:
story = await generate_story(
    brief=state["structured_brief"],
    framework_id=state["framework_id"],
    research_context=state["research_context"]  # Injected into prompt
)

# Result: Narrative grounded in real Apple announcement facts
```

## Configuration

### Environment Variables

```bash
# Research pipeline
RESEARCH_ENABLED=true              # Enable/disable all research
SEARCH_MAX_RESULTS=5               # DuckDuckGo results per query
SCRAPE_MAX_URLS=3                  # Max URLs to extract content from

# LLM model (already configured in llm_client.py)
ASI_ONE_API_KEY=...
```

## Best Practices

1. **Always await async nodes** - Research and LLM nodes return awaitable coroutines
2. **Pass message history** - Include conversation context for multi-turn follow-ups
3. **Handle research gracefully** - Always fallback to brief-only generation if research fails
4. **Monitor confidence scores** - Use `intent_confidence` to decide whether to ask for clarification
5. **Cache research context** - Store `research_context` in state to avoid repeated searches

## Debugging

Enable detailed logging in research and LLM flows:

```python
import logging
logging.basicConfig(level=logging.INFO)

# Look for these log prefixes:
# [llm_research] - LLM-based decisions
# [llm_nodes] - Router and node decisions  
# [research] - Web search and scraping
```

## Summary

The updated system provides:
- **LLM-powered research classification** with confidence scores
- **Async LangGraph nodes** for search, scrape, and enrich
- **Smart routing** based on research need and result quality
- **Enhanced user guidance** mentioning research capabilities
- **Backward compatibility** - non-research briefs unaffected
- **Graceful failure** - fallback if any step fails

The agent now intelligently decides when research will improve narratives and automatically grounds stories in real facts.
