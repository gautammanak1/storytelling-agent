"""
LangGraph conversation stack — **same module role** as ``instacart-agent/ai/ai.py``.

**Instacart** uses LangChain ``create_agent`` (ReAct + tools + Postgres checkpointer).

**Storytelling** uses a **compiled ``langgraph.graph.StateGraph``** with the same **LangGraph checkpointing**
(``AsyncPostgresSaver`` / ``InMemorySaver`` in ``runtime.py``): the flow is a **deterministic workflow**
(outbox-driven brief → framework → generate) rather than an open-ended tool-calling loop. Both are
valid LangGraph patterns; the checkpoint / ``thread_id`` model matches production Instacart deploys.

This module exposes ``setup_ai_instance`` and ``ask`` behind a small manager class, mirroring Instacart’s
``AIManager`` + ``ask`` surface.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from . import handlers
from .graph import strip_mentions, user_intends_post_story_resume, _is_greeting
from .router import route_user_message
from .runtime import (
    get_story_state,
    graph_step,
    persist_story_state,
    reset_story_thread,
    setup_ai_instance as _setup_checkpoint_and_graph,
)


class StorytellingAI:
    """One user turn: intent router → LangGraph ``ainvoke`` → optional outbox handlers (ASI1 side-effects)."""

    async def ask(
        self,
        *,
        ctx: Any,
        user_id: str,
        session_id: str,
        question: str,
        logger: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            control_text = strip_mentions(question)
            graph_state = await get_story_state(user_id, session_id)
            stage = str(graph_state.get("stage") or "idle")
            story_snapshot = (graph_state.get("generated_story") or "").strip()
            if (
                control_text
                and story_snapshot
                and stage in ("idle", "collect_brief")
                and user_intends_post_story_resume(control_text)
            ):
                merged = {**graph_state, "stage": "story_ready"}
                await persist_story_state(user_id, session_id, merged)
                graph_state = await get_story_state(user_id, session_id)
                stage = str(graph_state.get("stage") or "idle")
            logger.info(f"[graph] pre-step stage={stage}")

            # Router at idle: classify everything (greetings get a warm reply_only welcome).
            # Router at collect_brief: skip greetings (graph nudge handles them mid-flow).
            needs_router = (
                control_text
                and stage in ("idle", "collect_brief")
                and not (_is_greeting(control_text) and stage != "idle")
            )
            if needs_router:
                route = await route_user_message(raw_text=control_text, logger=logger)
                if not route.allowed:
                    if stage == "idle":
                        try:
                            await reset_story_thread(user_id, session_id)
                        except Exception:
                            pass
                    yield {
                        "type": "response",
                        "text": route.refusal_message or "Please describe the story you need.",
                    }
                    return

            res = await graph_step(
                user_address=user_id,
                session_id=session_id,
                event={"type": "chat", "control_text": control_text},
            )

            out = res.outbox or []
            logger.info(
                f"[graph] post-step stage={str((res.state or {}).get('stage') or '')} "
                f"outbox={[str(a.get('type')) for a in out if isinstance(a, dict)]}"
            )

            merged_static = handlers.merge_outbox_texts(
                [a for a in out if isinstance(a, dict) and a.get("type") == "send_text"]
            )
            if merged_static:
                yield {"type": "response", "text": merged_static}

            for action in out:
                if not isinstance(action, dict):
                    continue
                at = action.get("type")
                if at == "send_text":
                    continue

                if at == "process_brief":
                    async for text in handlers.iter_process_brief_and_generate(ctx, user_id, session_id, logger):
                        yield {"type": "response", "text": text}
                    continue

                if at == "generate_story":
                    async for text in handlers.iter_generate_full_story(ctx, user_id, session_id, logger):
                        yield {"type": "response", "text": text}
                    continue

                if at == "evaluate_story":
                    async for text in handlers.iter_evaluate_current_story(
                        ctx,
                        user_id,
                        session_id,
                        logger,
                        user_text=str(action.get("user_text") or control_text or ""),
                    ):
                        yield {"type": "response", "text": text}
                    continue

                if at == "refine_story":
                    feedback = str(action.get("feedback") or control_text or "")
                    async for text in handlers.iter_refine_current_story(ctx, user_id, session_id, logger, feedback):
                        yield {"type": "response", "text": text}
                    continue

        except Exception as exc:
            logger.error(f"[story] ask() failed: {exc}", exc_info=True)
            yield {
                "type": "error",
                "text": "Something went wrong on my side. Please try again in a moment.",
            }


class StorytellingAIManager:
    """Singleton-style manager — same pattern as ``instacart-agent/ai/ai.py`` ``AIManager``."""

    def __init__(self) -> None:
        self._ai: StorytellingAI | None = None

    async def setup_ai_instance(self, database_uri: str | None = None) -> bool:
        return await _setup_checkpoint_and_graph(database_uri)

    def ask(
        self,
        *,
        ctx: Any,
        user_id: str,
        session_id: str,
        question: str,
        logger: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if self._ai is None:
            self._ai = StorytellingAI()
        return self._ai.ask(
            ctx=ctx,
            user_id=user_id,
            session_id=session_id,
            question=question,
            logger=logger,
        )


_ai_manager = StorytellingAIManager()


async def setup_ai_instance(database_uri: str | None = None) -> bool:
    """Initialize LangGraph checkpointer + compiled graph (call once at agent startup)."""
    return await _ai_manager.setup_ai_instance(database_uri)


def ask(
    *,
    ctx: Any,
    user_id: str,
    session_id: str,
    question: str,
    logger: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream response chunks for one user message (protocol-compatible with instacart ``ask``)."""
    return _ai_manager.ask(
        ctx=ctx,
        user_id=user_id,
        session_id=session_id,
        question=question,
        logger=logger,
    )


__all__ = ["StorytellingAI", "StorytellingAIManager", "ask", "setup_ai_instance"]
