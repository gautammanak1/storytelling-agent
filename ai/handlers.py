"""Side-effect handlers driven by graph outbox actions (brief → framework → generate → evaluate → refine)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .llm_client import unified_turn_decision
from .graph import is_affirmation_only
from .runtime import get_story_state, graph_step, persist_story_state, reset_story_thread


def merge_outbox_texts(outbox: list[dict[str, Any]]) -> str | None:
    parts = [str(a.get("text", "")) for a in outbox if a.get("type") == "send_text" and a.get("text")]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return "\n\n---\n\n".join(parts)


async def iter_process_brief_and_generate(
    ctx: Any,
    sender: str,
    session_id: str,
    logger: Any,
) -> AsyncIterator[str]:
    from knowledge_base import (
        framework_confirmation_footer,
        get_framework_summary,
        rationale_is_user_pick_placeholder,
    )

    from .story_generator import interpret_brief, select_framework

    state = await get_story_state(sender, session_id)
    raw_brief = state.get("raw_brief", "")

    if not raw_brief:
        yield "I didn't catch your brief. Please describe what story you need."
        return

    rb = raw_brief.strip()
    if len(rb) < 120 and is_affirmation_only(rb):
        logger.info(f"[story] brief is affirmation-only, not a narrative request: '{rb!r}'")
        await reset_story_thread(sender, session_id)
        yield (
            "That looks like a confirmation, not a story brief. "
            "Paste your objective, audience, and format first — then say **yes** after I suggest a framework."
        )
        return

    brief_decision = await unified_turn_decision(user_text=raw_brief, logger=logger)
    if brief_decision.action == "reply_only":
        logger.info(f"[story] brief reclassified as meta/help: '{raw_brief[:80]}'")
        await reset_story_thread(sender, session_id)
        yield brief_decision.message or "When you're ready, share a concrete communication goal."
        return

    try:
        logger.info(f"[story] Interpreting brief: '{raw_brief[:80]}'")
        brief = await interpret_brief(raw_brief, logger=logger)
        state["structured_brief"] = brief

        fw_result = await select_framework(raw_brief, logger=logger)
        fid = fw_result["framework_id"]
        rationale = fw_result["rationale"]
        state["framework_id"] = fid
        state["framework_rationale"] = rationale
        state["stage"] = "confirm_framework"

        await persist_story_state(sender, session_id, state)

        brief_lines = []
        for k, v in brief.items():
            if v:
                brief_lines.append(f"• **{k.replace('_', ' ').title()}:** {v}")
        brief_summary = "\n".join(brief_lines) if brief_lines else "(basic brief captured)"

        summary = get_framework_summary(fid)
        why_block = ""
        if rationale and not rationale_is_user_pick_placeholder(rationale):
            why_block = f"**Why This Framework:** {rationale}\n\n"
        combined = (
            "📝 **Got Your Brief**\n\n"
            f"**Your Brief:**\n{brief_summary}\n\n"
            f"**Recommended Framework:**\n\n{summary}\n\n"
            f"{why_block}"
            f"{framework_confirmation_footer(fid)}"
        )
        yield combined
        logger.info("[story] Framework recommendation sent (single message)")

    except Exception as e:
        logger.error(f"[story] Brief processing failed: {e}", exc_info=True)
        state["stage"] = "idle"
        await persist_story_state(sender, session_id, state)
        yield (
            "⚠️ **Brief analysis failed.**\n\n"
            f"Error: {str(e)[:150]}\n\n"
            "Please try again — send your brief once more, or rephrase it with the objective, audience, and format."
        )


async def iter_generate_full_story(
    ctx: Any,
    sender: str,
    session_id: str,
    logger: Any,
) -> AsyncIterator[str]:
    from .story_generator import generate_story
    from .research_nodes import async_enrich_context_full

    state = await get_story_state(sender, session_id)
    brief = state.get("structured_brief", {})
    framework_id = state.get("framework_id", "business")
    rationale = state.get("framework_rationale", "")

    if not brief:
        brief = {"objective": state.get("raw_brief", "")}

    try:
        # Perform research if applicable
        logger.info("[research] Checking if brief warrants research...")
        research_state = await async_enrich_context_full(state)
        research_context = research_state.get("research_context", "")
        if research_context:
            logger.info(f"[research] Injecting {len(research_context)} chars of research")

        story = await generate_story(brief, framework_id, logger=logger, research_context=research_context)

        res = await graph_step(
            user_address=sender,
            session_id=session_id,
            event={
                "type": "generation_complete",
                "story": story,
                "framework_id": framework_id,
                "brief": brief,
                "rationale": rationale,
            },
        )

        merged = merge_outbox_texts(res.outbox or [])
        if merged:
            yield merged

    except Exception as e:
        logger.error(f"[story] Generation failed: {e}", exc_info=True)
        state = await get_story_state(sender, session_id)
        state["stage"] = "confirm_framework"
        await persist_story_state(sender, session_id, state)
        yield (
            "⚠️ **Story generation failed.**\n\n"
            f"Error: {str(e)[:150]}\n\n"
            "To retry, reply **yes** to generate again, or adjust your brief and framework."
        )


async def iter_evaluate_current_story(
    ctx: Any,
    sender: str,
    session_id: str,
    logger: Any,
    *,
    user_text: str = "",
) -> AsyncIterator[str]:
    from .story_generator import evaluate_story

    state = await get_story_state(sender, session_id)
    story = state.get("generated_story", "")
    framework_id = state.get("framework_id", "business")

    if not story:
        yield "No story to evaluate yet. Let's create one first."
        return

    try:
        evaluation = await evaluate_story(story, framework_id, logger=logger)

        res = await graph_step(
            user_address=sender,
            session_id=session_id,
            event={
                "type": "evaluation_complete",
                "evaluation": evaluation,
            },
        )

        merged = merge_outbox_texts(res.outbox or [])
        if merged:
            if user_text.strip():
                merged = f"**You:** {user_text.strip()}\n\n{merged}"
            yield merged

    except Exception as e:
        logger.error(f"[story] Evaluation failed: {e}", exc_info=True)
        yield (f"⚠️ **Evaluation failed.**\n\nError: {str(e)[:150]}\n\nReply **evaluate** to try again.")


async def iter_refine_current_story(
    ctx: Any,
    sender: str,
    session_id: str,
    logger: Any,
    feedback: str,
) -> AsyncIterator[str]:
    from .story_generator import refine_story

    state = await get_story_state(sender, session_id)
    story = state.get("generated_story", "")
    framework_id = state.get("framework_id", "business")

    if not story:
        if state.get("stage") == "refining":
            state["stage"] = "story_ready"
            await persist_story_state(sender, session_id, state)
        yield "No story to refine yet. Let's create one first."
        return

    fb = (feedback or "").strip()
    if len(fb) < 80 and is_affirmation_only(fb):
        state["stage"] = "story_ready"
        await persist_story_state(sender, session_id, state)
        yield (
            "Refine needs specific edits (e.g. shorten the opening, add metrics, more urgent tone). "
            "Or say evaluate for a score, new story to restart."
        )
        return

    try:
        refined = await refine_story(story, feedback, framework_id, logger=logger)

        res = await graph_step(
            user_address=sender,
            session_id=session_id,
            event={
                "type": "refinement_complete",
                "refined_story": refined,
            },
        )

        merged = merge_outbox_texts(res.outbox or [])
        if merged:
            if fb:
                merged = f"**You:** {fb}\n\n{merged}"
            yield merged

    except Exception as e:
        logger.error(f"[story] Refinement failed: {e}", exc_info=True)
        state = await get_story_state(sender, session_id)
        state["stage"] = "story_ready"
        await persist_story_state(sender, session_id, state)
        yield (
            "⚠️ **Refinement failed.**\n\n"
            f"Error: {str(e)[:150]}\n\n"
            "Reply with your feedback again to retry, or say **evaluate** to score the current version."
        )
