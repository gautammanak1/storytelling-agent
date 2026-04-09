# Storytelling Agent

![tag](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag](https://img.shields.io/badge/chatprotocol-FF6B35)
![tag](https://img.shields.io/badge/storytelling-6A5ACD) ![tag](https://img.shields.io/badge/asi1-4285F4)
![tag](https://img.shields.io/badge/narrative-0EA5E9) ![tag](https://img.shields.io/badge/spotlight-22C55E)

> **Structured storytelling for business, change, and persuasive communication.**

Turn ideas into structured, persuasive stories using proven storytelling frameworks.

---

## About

This agent helps you draft, refine, and evaluate stories using proven storytelling frameworks. It is designed for business communication, change narratives, decision-focused messaging, and high-impact openings.

Whether you are preparing a pitch, presentation, campaign, leadership update, keynote, or brand story, the Storytelling Agent helps you build narratives that are clear, memorable, and persuasive.

---

## What This Agent Does

This agent helps you turn ideas into structured, persuasive stories.

You can use it to:

* Draft a story from a simple idea or brief
* Refine an existing narrative
* Evaluate clarity, relevance, and impact
* Improve messaging for leadership, teams, customers, or stakeholders
* Create stronger openings, hooks, and memorable endings
* Build business, change, and decision-focused narratives

---

## Key Features

### Core Capabilities

* **Framework-Led Storytelling**: Uses structured narrative frameworks based on your goal
* **Brief Interpretation**: Understands audience, tone, objective, and constraints from natural language
* **Framework Recommendation**: Suggests the best storytelling structure for your use case
* **Narrative Generation**: Creates complete stories, pitches, scripts, and message flows
* **Story Evaluation**: Reviews narratives for clarity, relevance, memorability, and impact
* **Iterative Refinement**: Improves stories based on feedback and audience needs

---

## Storytelling Frameworks

| Framework           | Best For                                | Description                                                               |
| ------------------- | --------------------------------------- | ------------------------------------------------------------------------- |
| **Business**        | Clear, practical business communication | Use when you need a clear, logical message with a practical outcome       |
| **4 C's**           | Problem to solution storytelling        | Use when the problem and solution are clear and you need structured proof |
| **Hero's Journey**  | Change, adoption, and buy-in            | Use when you want to move an audience from hesitation to commitment       |
| **Man in the Hole** | Setback, response, and recovery         | Use when you need to show challenge, resilience, and recovery             |
| **In Medias Res**   | Strong openings and fast attention      | Use when you need to capture attention immediately                        |

---

## Use Cases

* Campaign ideation and development
* Brand messaging and positioning
* Change management narratives
* Leadership communication
* Presentation and keynote storytelling
* Investor and startup pitches
* Short-form scripts and ad copy
* Stakeholder communication
* Product launches
* Executive updates
* Team communication

---

## Agent Guide

### Guided Flow

1. Describe your idea, audience, and goal
2. Review the recommended storytelling framework
3. Generate a structured story or narrative
4. Refine the tone, message, or structure
5. Evaluate the story for clarity and impact

### What You Can Do Next

* Draft a story
* Refine a story
* Evaluate a story
* Generate a new version
* Improve an opening or closing
* Change the tone for a different audience

---

## Example Prompts

```text
Pitch a sustainability initiative to the C-suite in 3 minutes
```

```text
Turn a strategy update into a sharper executive narrative
```

```text
Tell the story of a setback and recovery
```

```text
Open a talk with a strong hook
```

```text
Write a change story that builds buy-in
```

```text
Create a brand story for a luxury fashion company launching an ethical sourcing initiative
```

```text
Develop a narrative for a company moving to remote-first work
```

```text
Write an opening for a keynote about the future of retail technology
```

---

## Why Use This Agent

* Makes storytelling more structured and effective
* Helps communicate ideas with clarity and confidence
* Saves time when preparing presentations, campaigns, or pitches
* Adapts stories for different audiences and goals
* Encourages better narrative thinking instead of generic content generation

---

## Notes

* This agent supports collaboration and iteration
* It is designed to improve human storytelling, not replace it
* The best results come from providing a clear audience, goal, and context
* You can continue refining stories until the tone and message feel right

---

## Technical overview

A **uAgents** chat agent. Story generation uses the **ASI1** OpenAI-compatible API (`https://api.asi1.ai/v1`, `ASI_ONE_API_KEY`). Requests pass `extra_body.web_search` when `ASI_WEB_SEARCH` is enabled (default: on). Optional **PostgreSQL** (`DATABASE_URL`) enables session persistence and inbound `msg_id` deduplication.

### Quick start

```bash
cd innovation-lab-agents/agents/storytelling-agent
cp .env.example .env
# Set PRIVATE_KEY or AGENT_SEED, and ASI_ONE_API_KEY
uv sync
uv run python agent.py
```

### Required environment

| Variable | Description |
|----------|-------------|
| `PRIVATE_KEY` or `AGENT_SEED` | Agent identity |
| `ASI_ONE_API_KEY` | ASI1 API key (`api.asi1.ai`) |

Optional: `DATABASE_URL` for session state and chat idempotency (recommended for production), `SENTRY_*`, `HEALTH_PORT`, `REQUIRED_ENV_FOR_READY`.

Narrative length: generation/refine use a higher token budget (`STORY_NARRATIVE_MAX_TOKENS`, default derived from `STORY_MODEL_MAX_TOKENS` or **8192**) and prompts that ask for **substantial** drafts (`STORY_TARGET_MIN_WORDS`, `STORY_OUTPUT_DEPTH=comprehensive` by default). One chat message cannot safely return literally thousands of *lines* of prose; raise `STORY_NARRATIVE_MAX_TOKENS` (e.g. 16384) if your ASI1 quota allows and you need extremely long outputs.

### Docker

Build from the **repository root**:

```bash
docker build -f agents/storytelling-agent/Dockerfile -t storytelling-agent:local .
```

Or use **Docker Compose** from this agent directory (loads variables from `.env` in the same folder):

```bash
cd innovation-lab-agents/agents/storytelling-agent
docker compose up --build
```

### Layout

* `agent.py` — uAgent entry, health, DB init, Sentry, `setup_ai_instance` hook
* `knowledge_base.py` — Framework definitions
* `protocols/chat_proto.py` — Thin chat handler; delegates turns to `ai.ask` (instacart-style chunks)
* `ai/` — LangGraph + ASI1 (layout aligned with `instacart-agent/ai/`)
  * `ai/ai.py` — `StorytellingAI` + `StorytellingAIManager` + module-level `ask` / `setup_ai_instance` (same role as Instacart’s `ai/ai.py`; uses compiled `StateGraph` + checkpointer, not `create_agent`)
  * `ai/PROMPT.md` — Single behavioral spec for pre-graph turns (~200+ lines; greeting, help, meta vs brief)
  * `ai/defaults.py` — Temperature defaults for unified routing
  * `ai/models.py` — `PromptRoute`, `UnifiedTurnDecision` (Pydantic)
  * `ai/llm_client.py` — ASI1 `chat_completion` + `unified_turn_decision` (PROMPT + JSON)
  * `ai/router.py` — `route_user_message` → LangGraph or direct reply
  * `ai/intent.py` — Re-exports only (compat)
  * `ai/graph.py` — LangGraph `StateGraph` + `apply_story_event`
  * `ai/runtime.py` — Postgres or in-memory checkpointer
  * `ai/story_generator.py` — Brief, generate, evaluate, refine (ASI1)
  * `ai/handlers.py` — Graph outbox side-effects
  * `ai/pipeline.py` — `ask()` async generator
