"""
Chat protocol for the storytelling agent.

Structured like ``instacart-agent/protocols/chat_proto.py``: user text is streamed through
``ai.ask`` (LangGraph pipeline + intent layer). One outbound ``create_text_chat`` per chunk
with ``type == "response"`` so the chat UI stays predictable.

Inbound optional DB idempotency when DATABASE_URL is set (same pattern as instacart).
"""

from __future__ import annotations

import json
from typing import Any
from datetime import datetime, timezone

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents_shared.chat import create_metadata, create_text_chat

from ai.runtime import get_story_state, reset_story_thread


story_chat_proto = Protocol(spec=chat_protocol_spec)

# If the UI sends StartSessionContent on every turn, resetting LangGraph would drop
# confirm_framework / story_ready state before "yes" or "Refine" is processed (brief becomes "yes").
_MID_FLOW_STAGES = frozenset(
    {
        "collect_brief",
        "confirm_framework",
        "generating",
        "story_ready",
        "refining",
    }
)


async def _reset_story_thread_on_session_start(sender: str, session_id: str, logger: Any) -> None:
    try:
        st = await get_story_state(sender, session_id)
        stage = str(st.get("stage") or "idle")
        if stage in _MID_FLOW_STAGES:
            logger.info(f"[chat] StartSession: skip checkpoint reset (stage={stage}) session_id={session_id}")
            return
    except Exception as exc:
        logger.warning(f"[chat] StartSession: could not read graph state ({exc}); resetting thread")
    await reset_story_thread(sender, session_id)


# ---------------------------------------------------------------------------
# Helpers (instacart-style)
# ---------------------------------------------------------------------------


async def _ack(ctx: Context, sender: str, msg: ChatMessage) -> None:
    try:
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    except Exception:
        pass


def _compact_payload(msg: ChatMessage) -> dict:
    texts: list[str] = []
    for item in getattr(msg, "content", []) or []:
        t = getattr(item, "text", None)
        if isinstance(t, str) and t.strip():
            texts.append(t.strip())
    return {"texts": texts[:8], "content_count": len(getattr(msg, "content", []) or [])}


async def _db_record_inbound(ctx: Context, *, session_id: str, sender: str, msg: ChatMessage) -> bool:
    """Instacart-style: when DATABASE_URL is set, fail closed on duplicate or DB error."""
    msg_id_val = getattr(msg, "msg_id", None)
    msg_id_str = str(msg_id_val).strip() if msg_id_val else ""
    try:
        from agents_shared.db import get_db

        db = get_db()
        if not db:
            return True
        if not msg_id_str:
            ctx.logger.warning("[db] missing msg_id; inbound dedup disabled for this message")
            return True
        await db.ensure_session(session_id=session_id, user_address=sender)
        inserted = await db.insert_chat_message(
            session_id=session_id,
            user_address=sender,
            peer_address=sender,
            direction="inbound",
            kind="chat",
            msg_id=msg_id_str,
            payload=_compact_payload(msg),
        )
        if inserted:
            await db.insert_chat_message(
                session_id=session_id,
                user_address=sender,
                peer_address=sender,
                direction="outbound",
                kind="system",
                msg_id=None,
                payload={"type": "ChatAcknowledgement", "acknowledged_msg_id": msg_id_str},
            )
        return bool(inserted)
    except Exception as exc:
        ctx.logger.warning(f"[db] inbound persist failed: {exc}; fail closed")
        return False


async def _db_record_outbound(ctx: Context, *, session_id: str, user_address: str, text: str) -> None:
    try:
        from agents_shared.db import get_db

        db = get_db()
        if not db:
            return
        await db.insert_chat_message(
            session_id=session_id,
            user_address=user_address,
            peer_address=user_address,
            direction="outbound",
            kind="chat",
            msg_id=None,
            payload={"texts": [text[:8000]]},
        )
    except Exception as exc:
        ctx.logger.warning(f"[db] outbound persist failed: {exc}")


async def _send_text(ctx: Context, *, recipient: str, session_id: str, text: str) -> None:
    """Single chat bubble — same pattern as instacart-agent ``_send_text``."""
    await ctx.send(recipient, create_text_chat(text))
    await _db_record_outbound(ctx, session_id=session_id, user_address=recipient, text=text)


@story_chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    session_id = str(ctx.session)
    msg_id = getattr(msg, "msg_id", None)
    ctx.logger.info(f"[chat] ChatMessage session_id={session_id} msg_id={msg_id} sender={sender}")
    await _ack(ctx, sender, msg)

    try:
        from agents_shared.sentry import set_user_context

        set_user_context(sender, session_id)
    except Exception:
        pass

    if not await _db_record_inbound(ctx, session_id=session_id, sender=sender, msg=msg):
        ctx.logger.info(f"[idempotency] duplicate inbound ignored session_id={session_id} msg_id={msg_id}")
        return

    text_content = None
    for item in msg.content or []:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Session started from {sender}, session: {session_id}")
            ctx.storage.set(
                f"session_{session_id}_{sender}",
                json.dumps(
                    {
                        "session_id": session_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )
            try:
                from agents_shared.db import get_db

                db = get_db()
                if db:
                    await db.ensure_session(session_id=session_id, user_address=sender)
            except Exception:
                pass
            await ctx.send(sender, create_metadata({"attachments": "false"}))
            try:
                ctx.storage.remove(f"story:graph_state:{sender}:{session_id}")
            except Exception:
                pass
            try:
                await _reset_story_thread_on_session_start(sender, session_id, ctx.logger)
            except Exception:
                pass
            continue

        if isinstance(item, TextContent):
            text_content = item
            break

    for item in msg.content or []:
        if isinstance(item, StartSessionContent):
            continue

        if isinstance(item, TextContent) and text_content and item is text_content:
            raw_text = (getattr(text_content, "text", "") or "").strip()
            ctx.logger.info(f"📨 Message from {sender}: '{raw_text[:80]}' (session: {session_id})")

            from ai import ask

            try:
                async for chunk in ask(
                    ctx=ctx,
                    user_id=sender,
                    session_id=session_id,
                    question=raw_text,
                    logger=ctx.logger,
                ):
                    chunk_type = chunk.get("type")

                    if chunk_type == "update":
                        update_text = chunk.get("text", "")
                        if update_text:
                            ctx.logger.info(f"[story] update: {update_text}")

                    elif chunk_type == "response":
                        items = chunk.get("items")
                        if items:
                            await _send_text(
                                ctx,
                                recipient=sender,
                                session_id=session_id,
                                text=items,
                            )
                            continue
                        reply = chunk.get("text") or "Something went wrong on my side. Please try again in a moment."
                        await _send_text(
                            ctx,
                            recipient=sender,
                            session_id=session_id,
                            text=reply,
                        )

                    elif chunk_type == "error":
                        error_text = chunk.get("text", "")
                        if not error_text:
                            error_text = "Something went wrong on my side. Please try again in a moment."
                        await _send_text(
                            ctx,
                            recipient=sender,
                            session_id=session_id,
                            text=error_text,
                        )

                    else:
                        ctx.logger.warning(
                            f"[story] unknown chunk type session_id={session_id} msg_id={msg_id}: {chunk_type}"
                        )

            except Exception as exc:
                ctx.logger.warning(
                    f"[story] Error while processing message session_id={session_id} msg_id={msg_id}: {exc}"
                )
                try:
                    from agents_shared.sentry import capture_agent_error

                    capture_agent_error(
                        exc,
                        extra_context={
                            "chat": {
                                "session_id": session_id,
                                "msg_id": str(msg_id),
                                "sender": sender,
                            }
                        },
                    )
                except Exception:
                    pass
                await _send_text(
                    ctx,
                    recipient=sender,
                    session_id=session_id,
                    text="Something went wrong on my side. Please try again in a moment.",
                )

            return

        if isinstance(item, EndSessionContent):
            ctx.logger.info(f"Session ended from {sender}")
            try:
                ctx.storage.remove(f"story:graph_state:{sender}:{session_id}")
            except Exception:
                pass


@story_chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(f"Ack from {sender} for {msg.acknowledged_msg_id}")
