"""ASI1 (OpenAI-compatible) HTTP client: unified router + shared chat completion."""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from . import defaults
from .models import UnifiedTurnDecision

_log = logging.getLogger(__name__)

_async_client: AsyncOpenAI | None = None


def _get_api_key() -> str:
    return (os.getenv("ASI_ONE_API_KEY") or "").strip()


def _get_base_url() -> str:
    return (os.getenv("ASI_BASE_URL") or "https://api.asi1.ai/v1").strip().rstrip("/")


def _get_model() -> str:
    return (os.getenv("STORY_MODEL") or "asi1").strip()


def _web_search_extra_body() -> dict[str, Any]:
    """ASI1 supports ``web_search`` in ``extra_body`` (enable via ``ASI_WEB_SEARCH``)."""
    raw = (os.getenv("ASI_WEB_SEARCH") or "true").strip().lower()
    enabled = raw in ("1", "true", "yes", "on")
    return {"web_search": enabled}


def _client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=_get_api_key(), base_url=_get_base_url())
    return _async_client


@lru_cache(maxsize=1)
def _router_prompt_baseline() -> str:
    path = Path(__file__).resolve().parent / "PROMPT.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        _log.warning("[llm] PROMPT.md missing; using minimal baseline")
        return (
            "You route user messages: reply_only (greeting, help, meta) vs continue_pipeline "
            "(real story brief). Output JSON only per contract."
        )


def _build_unified_prompt(user_text: str) -> str:
    u = user_text if user_text is not None else ""
    return (
        f"{_router_prompt_baseline()}\n\n---\n\n"
        "## Live user message (classify now)\n\n"
        f'"""\n{u}\n"""\n\n'
        "Respond with **only** the JSON object as described in the output contract. "
        "No markdown fences, no text before or after the JSON."
    )


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", s, re.I)
    if m:
        return m.group(1).strip()
    return s


def _parse_unified_json(raw: str) -> UnifiedTurnDecision | None:
    s = _strip_json_fence(raw)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(obj, dict):
        return None
    action = str(obj.get("action", "")).strip().lower()
    if action not in ("reply_only", "continue_pipeline"):
        return None
    msg = obj.get("message")
    if action == "continue_pipeline":
        return UnifiedTurnDecision(action="continue_pipeline", message=None)
    if isinstance(msg, str) and msg.strip():
        return UnifiedTurnDecision(action="reply_only", message=msg.strip())
    return UnifiedTurnDecision(action="reply_only", message=defaults.HELP_FALLBACK_REPLY)


async def chat_completion(
    *,
    user_prompt: str,
    system_instruction: str = "",
    temperature: float = 0.8,
    max_tokens: int = 4096,
    logger: Any | None = None,
    log_label: str = "story_gen",
) -> str:
    """
    Single ASI1 chat completion (``model`` from ``STORY_MODEL``, default ``asi1``).
    Passes ``extra_body`` with ``web_search`` when enabled.
    """
    if not _get_api_key():
        raise RuntimeError("ASI_ONE_API_KEY must be set")

    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": user_prompt})

    model = _get_model()
    if logger:
        logger.info(f"[{log_label}] ASI1 model={model} prompt_len={len(user_prompt)}")

    client = _client()
    create_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra_body": _web_search_extra_body(),
    }
    top_p_raw = (os.getenv("STORY_TOP_P") or "").strip()
    if top_p_raw:
        try:
            create_kwargs["top_p"] = float(top_p_raw)
        except ValueError:
            pass

    resp = await client.chat.completions.create(**create_kwargs)

    choice = resp.choices[0].message if resp.choices else None
    text = (getattr(choice, "content", None) or "").strip() if choice else ""
    if not text:
        raise RuntimeError("ASI1 returned empty content")
    if logger:
        logger.info(f"[{log_label}] ASI1 response OK, length={len(text)}")
    return text


async def unified_turn_decision(
    *,
    user_text: str,
    logger: Any | None = None,
) -> UnifiedTurnDecision:
    """
    Single model call: classify per ``PROMPT.md`` and return structured decision.

    Without ``ASI_ONE_API_KEY``, uses minimal safe fallbacks (no heuristics).
    """
    text = user_text if user_text is not None else ""

    if not _get_api_key():
        if not text.strip():
            return UnifiedTurnDecision(action="reply_only", message=defaults.GREETING_FALLBACK_REPLY)
        return UnifiedTurnDecision(action="continue_pipeline", message=None)

    try:
        raw = await chat_completion(
            user_prompt=_build_unified_prompt(text),
            system_instruction="",
            temperature=defaults.UNIFIED_TEMPERATURE,
            max_tokens=defaults.UNIFIED_MAX_OUTPUT_TOKENS,
            logger=logger,
            log_label="router",
        )
    except Exception as e:
        if logger:
            logger.warning(f"[llm] unified failed: {e}")
        return _fallback_decision(text)

    parsed = _parse_unified_json(raw)
    if parsed is not None:
        return parsed
    if logger:
        logger.warning(f"[llm] unified parse failed, raw[:300]={raw[:300]!r}")
    return _fallback_decision(text)


def _fallback_decision(user_text: str) -> UnifiedTurnDecision:
    """When HTTP fails or JSON is invalid: prefer safe short replies; else allow pipeline."""
    t = (user_text or "").strip()
    if not t:
        return UnifiedTurnDecision(action="reply_only", message=defaults.GREETING_FALLBACK_REPLY)
    return UnifiedTurnDecision(action="continue_pipeline", message=None)
