"""
Story generation engine using ASI1 (OpenAI-compatible API at ``api.asi1.ai``).

Handles:
- Framework selection (LLM-assisted)
- Brief interpretation and structuring
- Full narrative generation
- Story evaluation and refinement
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from knowledge_base import (
    ALL_FRAMEWORKS,
    EVALUATION_RUBRIC,
    FRAMEWORK_SELECTOR_GUIDE,
    VALIDATION_CHECKLIST,
    build_framework_prompt_context,
)

from .llm_client import chat_completion


def _get_temperature() -> float:
    try:
        return float(os.getenv("STORY_MODEL_TEMPERATURE", "0.8"))
    except (ValueError, TypeError):
        return 0.8


def _get_max_tokens() -> int:
    """Default budget for short JSON / classify-style calls."""
    try:
        return int(os.getenv("STORY_MODEL_MAX_TOKENS", "4096"))
    except (ValueError, TypeError):
        return 4096


def _get_narrative_max_tokens() -> int:
    """Larger budget for full narrative + refine (env overrides)."""
    raw = (os.getenv("STORY_NARRATIVE_MAX_TOKENS") or "").strip()
    if raw:
        try:
            return max(256, int(raw))
        except ValueError:
            pass
    try:
        base = int(os.getenv("STORY_MODEL_MAX_TOKENS", "8192"))
    except (ValueError, TypeError):
        base = 8192
    # JSON-style calls may use a lower STORY_MODEL_MAX_TOKENS; narratives still get a generous floor.
    return max(8192, base)


def _depth_prompt_block() -> str:
    """Instructions for long-form, high-quality output (tunable via env)."""
    min_words = (os.getenv("STORY_TARGET_MIN_WORDS") or "1200").strip()
    depth = (os.getenv("STORY_OUTPUT_DEPTH") or "comprehensive").strip().lower()
    try:
        mw = max(400, int(min_words))
    except ValueError:
        mw = 1200
    if depth in ("brief", "short", "compact"):
        return "LENGTH: Keep the narrative tight and scannable unless the brief explicitly asks for more.\n"
    return (
        "LENGTH & DEPTH (critical):\n"
        f"- Default to a **substantial, professional deliverable** — not a short outline. Unless the brief "
        f"explicitly caps length (e.g. '30 seconds', 'one paragraph', 'tweet'), aim for **at least ~{mw} words** "
        "of developed prose where the format allows.\n"
        "- **Fully develop** each framework section: multiple paragraphs, concrete examples, proof points, "
        "transitions, and audience-specific language — quality over filler, but do not stop at a thin sketch.\n"
        "- For pitches, keynotes, and memos: include enough material that someone could rehearse or edit from it "
        "without asking you to 'expand this' again.\n"
    )


async def _call_asi(
    prompt: str,
    *,
    system_instruction: str = "",
    logger: Any = None,
    max_tokens: int | None = None,
) -> str:
    return await chat_completion(
        user_prompt=prompt,
        system_instruction=system_instruction,
        temperature=_get_temperature(),
        max_tokens=max_tokens if max_tokens is not None else _get_max_tokens(),
        logger=logger,
        log_label="story_gen",
    )


SYSTEM_INSTRUCTION = """You are an expert AI storytelling partner. You help users create structured, persuasive narratives for business, brand, and communication use cases.

You are framework-led, audience-aware, and evaluation-oriented. You always expose the structural logic you are using. You generate, compare, evaluate, and refine — but never present yourself as a substitute for human taste, judgment, or authorship.

You are a collaborator, not a fully autonomous creative director. Your job is to turn a structured brief into a clear, persuasive, audience-aware narrative.

Core principles:
- Always respond in English regardless of the language the user writes in
- Always use an explicit storytelling framework
- Every story must be audience-specific
- Validate against clarity, relevance, feasibility, impact, coherence, and memorability
- Show your structural thinking
- Provide actionable, ready-to-use output
- When generating or refining full narratives, prefer **depth and completeness** over thin summaries,
  unless the user explicitly requests brevity"""


async def select_framework(
    brief_text: str,
    *,
    logger: Any = None,
) -> dict[str, str]:
    """Use LLM to recommend the best framework for a given brief."""
    prompt = f"""{FRAMEWORK_SELECTOR_GUIDE}

Based on the user's brief below, recommend the BEST storytelling framework. Return a JSON object with:
- "framework_id": one of "business", "4cs", "heros_journey", "man_in_hole", "in_medias_res"
- "rationale": 1-2 sentences explaining why this framework fits

USER BRIEF:
{brief_text}

Return ONLY the JSON object, no markdown fences."""

    raw = await _call_asi(prompt, system_instruction=SYSTEM_INSTRUCTION, logger=logger)

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    try:
        result = json.loads(cleaned)
        fid = result.get("framework_id", "business")
        if fid not in ALL_FRAMEWORKS:
            fid = "business"
        return {"framework_id": fid, "rationale": result.get("rationale", "")}
    except (json.JSONDecodeError, KeyError):
        if logger:
            logger.warning(f"[story_gen] Failed to parse framework selection: {raw[:200]}")
        return {"framework_id": "business", "rationale": "Defaulting to Business framework."}


async def interpret_brief(
    raw_brief: str,
    *,
    logger: Any = None,
) -> dict[str, str]:
    """Extract structured brief fields from freeform user input."""
    prompt = f"""Analyze the user's storytelling request and extract a structured brief. Return a JSON object with these fields (use empty string if not mentioned):
- "objective": What the story should achieve
- "audience": Who the story is for
- "stakes": What's at stake or why it matters
- "format": The desired output format (pitch, script, campaign, presentation, ad copy, etc.)
- "tone": The desired tone (professional, inspiring, urgent, conversational, etc.)
- "industry": The industry or sector
- "constraints": Any constraints or requirements mentioned

USER REQUEST:
{raw_brief}

Return ONLY the JSON object, no markdown fences."""

    raw = await _call_asi(prompt, system_instruction=SYSTEM_INSTRUCTION, logger=logger)

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, KeyError):
        if logger:
            logger.warning(f"[story_gen] Failed to parse brief: {raw[:200]}")
        return {
            "objective": raw_brief,
            "audience": "",
            "stakes": "",
            "format": "",
            "tone": "",
            "industry": "",
            "constraints": "",
        }


async def generate_story(
    brief: dict[str, str],
    framework_id: str,
    *,
    logger: Any = None,
) -> str:
    """Generate a full narrative using the selected framework and brief."""
    framework_context = build_framework_prompt_context(framework_id)

    brief_block = "\n".join(f"- {k}: {v}" for k, v in brief.items() if v)

    depth = _depth_prompt_block()

    prompt = f"""Generate a complete, polished narrative using the framework and brief below.

{framework_context}

STORY BRIEF:
{brief_block}

{depth}
INSTRUCTIONS:
1. Follow the framework structure precisely — use each element as a **fully developed** section (not bullet stubs).
2. **Formatting (scan-friendly):** Use **clear section headings** that name each framework beat in order (numbered or labeled, e.g. 1. Context, 2. …). Within each section, use **short paragraphs** and **bullet lists** where they improve clarity (facts, proof, actions) — avoid an unstructured wall of text.
3. Write in the tone and style appropriate for the audience
4. Make it audience-specific: address their concerns, motivations, and decision context
5. Include concrete details, examples, and proof points — not vague generalities
6. End with a strong, memorable key message
7. If the format is a script, write it as a script. If a presentation, write slide-by-slide with enough speaker-ready material. If ad copy, write punchy and concise (ignore high word-count targets for that format only).
8. After the narrative, include a concise "Framework Notes" section (roughly half a page max) explaining why this framework fits and how each element maps — do not let Framework Notes dwarf the narrative.

Generate the full narrative now:"""

    return await _call_asi(
        prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        logger=logger,
        max_tokens=_get_narrative_max_tokens(),
    )


async def evaluate_story(
    story_text: str,
    framework_id: str,
    *,
    logger: Any = None,
) -> str:
    """Evaluate a generated or user-provided story against the rubric."""
    rubric_lines = "\n".join(f"- {k}: {v}" for k, v in EVALUATION_RUBRIC.items())
    checklist_lines = "\n".join(f"- {item}" for item in VALIDATION_CHECKLIST)
    framework_context = build_framework_prompt_context(framework_id)

    prompt = f"""Evaluate the following story against the evaluation rubric and validation checklist.

{framework_context}

EVALUATION RUBRIC:
{rubric_lines}

VALIDATION CHECKLIST:
{checklist_lines}

STORY TO EVALUATE:
{story_text}

Provide:
1. A score (Strong / Adequate / Needs Work) for each rubric dimension
2. Checklist pass/fail for each item
3. Top 3 specific suggestions for improvement
4. An overall assessment (1-2 sentences)

Be constructive, specific, and actionable."""

    return await _call_asi(prompt, system_instruction=SYSTEM_INSTRUCTION, logger=logger)


async def refine_story(
    story_text: str,
    feedback: str,
    framework_id: str,
    *,
    logger: Any = None,
) -> str:
    """Refine a story based on user feedback or evaluation results."""
    framework_context = build_framework_prompt_context(framework_id)

    prompt = f"""Refine and improve the following story based on the feedback. Keep the same framework structure.

{framework_context}

ORIGINAL STORY:
{story_text}

FEEDBACK / REFINEMENT REQUEST:
{feedback}

{_depth_prompt_block()}
OUTPUT RULES (critical):
1. Return: (a) the **full** refined narrative at the same or greater depth as the original unless feedback asks to shorten,
   (b) a compact "Framework Notes" subsection (≤8 sentences).
2. Do not include internal self-evaluations, checklists, or questionnaires (no "STORY BRIEF" templates, no "please provide" prompts).
3. Do not paste the entire original story verbatim before the revision unless the feedback asks for a side-by-side.
4. Apply feedback concretely; if feedback is thin, strengthen clarity, pacing, and examples while preserving length where appropriate.
5. Do not shrink a long narrative into a summary unless the user asked for shorter.

Generate the refined output now:"""

    return await _call_asi(
        prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        logger=logger,
        max_tokens=_get_narrative_max_tokens(),
    )
