"""
LangGraph runtime: compiled graph + Postgres (or in-memory) checkpointer, instacart-style.

``thread_id`` = ``story:{user_address}:{session_id}`` — persisted in checkpoint tables when
``DATABASE_URL`` is set; otherwise ``InMemorySaver`` (single-process only).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde import jsonplus as jsonplus_serde
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from .graph import (
    Event,
    StepResult,
    StoryState,
    build_compiled_story_graph,
    default_state,
)

_log = logging.getLogger(__name__)

_compiled: Any = None
_checkpointer: Any = None
_pool: AsyncConnectionPool | None = None
_init_lock = asyncio.Lock()


def thread_id_for(user_address: str, session_id: str) -> str:
    return f"story:{user_address}:{session_id}"


def _make_checkpoint_serde() -> jsonplus_serde.JsonPlusSerializer:
    return jsonplus_serde.JsonPlusSerializer()


async def ensure_compiled_fallback() -> None:
    """If startup did not finish graph init (exception, import order, etc.), build in-memory graph once.

    Safe to call from every entrypoint; uses a lock so concurrent first messages only init once.
    """
    global _compiled, _checkpointer, _pool

    if _compiled is not None:
        return
    async with _init_lock:
        if _compiled is not None:
            return
        if _pool is not None:
            try:
                await _pool.close()
            except Exception:
                pass
            _pool = None
        _checkpointer = InMemorySaver()
        try:
            _compiled = build_compiled_story_graph(_checkpointer)
        except Exception as exc:
            _log.exception("[ai] Lazy LangGraph build failed")
            raise RuntimeError("LangGraph could not be compiled; check dependencies and logs.") from exc
        _log.warning(
            "[ai] LangGraph initialized lazily (in-memory). Startup setup may have failed or not run — "
            "check earlier logs; set DATABASE_URL for Postgres in production."
        )


async def _run_setup_ddl(database_uri: str) -> None:
    serde = _make_checkpoint_serde()
    async with await AsyncConnection[DictRow].connect(
        database_uri,
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        checkpointer = AsyncPostgresSaver(conn, serde=serde)
        await checkpointer.setup()


async def setup_ai_instance(database_uri: str | None = None) -> bool:
    """Build checkpointer + compiled graph (call once at agent startup).

    Returns:
        True if ``AsyncPostgresSaver`` is active; False if using ``InMemorySaver``
        (unset ``DATABASE_URL``, or Postgres unreachable — dev-friendly fallback).
    """
    global _compiled, _checkpointer, _pool

    if _compiled is not None:
        return isinstance(_checkpointer, AsyncPostgresSaver)

    uri = (database_uri or "").strip()
    used_postgres = False

    if uri:
        pool: AsyncConnectionPool | None = None
        try:
            await _run_setup_ddl(uri)
            pool = AsyncConnectionPool(
                uri,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            await pool.open()
            serde = _make_checkpoint_serde()
            _checkpointer = AsyncPostgresSaver(pool, serde=serde)
            _pool = pool
            used_postgres = True
        except Exception as exc:
            if pool is not None:
                try:
                    await pool.close()
                except Exception:
                    pass
            _pool = None
            _checkpointer = InMemorySaver()
            _log.warning(
                "[ai] Postgres checkpointer unavailable (%s); using in-memory LangGraph state "
                "(single-process only). Fix DATABASE_URL or start Postgres — see README.",
                exc,
            )
    else:
        _checkpointer = InMemorySaver()

    try:
        _compiled = build_compiled_story_graph(_checkpointer)
    except Exception as exc:
        _log.warning("[ai] build_compiled_story_graph failed (%s); falling back to in-memory.", exc)
        if _pool is not None:
            try:
                await _pool.close()
            except Exception:
                pass
            _pool = None
        _checkpointer = InMemorySaver()
        used_postgres = False
        _compiled = build_compiled_story_graph(_checkpointer)
    return used_postgres


async def get_story_state(user_address: str, session_id: str) -> StoryState:
    await ensure_compiled_fallback()
    config = {"configurable": {"thread_id": thread_id_for(user_address, session_id)}}
    snap = await _compiled.aget_state(config)
    if snap.values:
        vals = dict(snap.values)
        vals.pop("event", None)
        return {**default_state(), **vals}
    return default_state()


async def persist_story_state(user_address: str, session_id: str, state: StoryState) -> None:
    """Merge ``state`` into the checkpoint (handlers after LLM side-effects)."""
    await ensure_compiled_fallback()
    config = {"configurable": {"thread_id": thread_id_for(user_address, session_id)}}
    clean = {k: v for k, v in dict(state).items() if k != "event"}
    await _compiled.aupdate_state(config, clean)


async def reset_story_thread(user_address: str, session_id: str) -> None:
    """New chat session: drop checkpoint for this thread."""
    await ensure_compiled_fallback()
    if _checkpointer is None:
        return
    tid = thread_id_for(user_address, session_id)
    await _checkpointer.adelete_thread(tid)


async def graph_step(
    *,
    ctx: Any = None,
    user_address: str,
    session_id: str,
    event: Event,
) -> StepResult:
    """One LangGraph ``ainvoke`` with persisted state (``ctx`` unused; kept for call-site compatibility)."""
    del ctx  # uAgents Context not needed for checkpointing
    await ensure_compiled_fallback()
    config = {"configurable": {"thread_id": thread_id_for(user_address, session_id)}}
    result = await _compiled.ainvoke({"event": event}, config)
    clean: dict[str, Any] = dict(result or {})
    clean.pop("event", None)
    out = list(clean.get("outbox") or [])
    return StepResult(state=clean, outbox=out)


__all__ = [
    "ensure_compiled_fallback",
    "graph_step",
    "get_story_state",
    "persist_story_state",
    "reset_story_thread",
    "setup_ai_instance",
    "thread_id_for",
]
