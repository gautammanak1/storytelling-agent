"""
LangGraph conversation state machine for the storytelling agent (``ai.graph``).

Flow: idle → collect_brief → select_framework → generate → evaluate → refine → idle.

Uses LangGraph ``StateGraph`` and the same outbox pattern as veo3-agent for side-effect separation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict, cast

from langgraph.graph import StateGraph, START, END

from knowledge_base import (
    framework_confirmation_footer,
    framework_recommendation_reminder,
    get_framework_summary,
    rationale_is_user_pick_placeholder,
)


Stage = Literal[
    "idle",
    "collect_brief",
    "select_framework",
    "confirm_framework",
    "generating",
    "story_ready",
    "refining",
]

_STORY_MENU = (
    "**What would you like to do next?**\n"
    "• **Evaluate** — score against clarity, relevance, impact, coherence, and memorability\n"
    '• **Refine** — tell me what to change (e.g. "make it more urgent" or "shorten the opening")\n'
    "• **Re-frame** — same brief, new framework (e.g. \"same story with 4 C's\")\n"
    "• **New story** — start fresh with a new brief"
)

_EVAL_MENU = (
    "**What next?**\n"
    "• **Refine** — tell me what to change based on the evaluation\n"
    "• **Re-frame** — same story, new framework (name it)\n"
    "• **New story** — start fresh"
)

_FRESH_START_MSG = "Starting fresh. Tell me about your new story — objective, audience, and format."


class StoryState(TypedDict, total=False):
    stage: Stage
    raw_brief: str
    structured_brief: dict[str, str]
    framework_id: str
    framework_rationale: str
    generated_story: str
    evaluation: str
    refinement_count: int
    outbox: list[dict[str, Any]]
    # Ephemeral: merged from ``ainvoke`` input only; stripped before checkpoint persistence.
    event: NotRequired[dict[str, Any]]


ChatEvent = TypedDict(
    "ChatEvent",
    {
        "type": Literal["chat"],
        "control_text": str,
    },
)

GenerationCompleteEvent = TypedDict(
    "GenerationCompleteEvent",
    {
        "type": Literal["generation_complete"],
        "story": str,
        "framework_id": str,
        "brief": dict[str, str],
        "rationale": str,
    },
)

EvaluationCompleteEvent = TypedDict(
    "EvaluationCompleteEvent",
    {
        "type": Literal["evaluation_complete"],
        "evaluation": str,
    },
)

RefinementCompleteEvent = TypedDict(
    "RefinementCompleteEvent",
    {
        "type": Literal["refinement_complete"],
        "refined_story": str,
    },
)

Event = ChatEvent | GenerationCompleteEvent | EvaluationCompleteEvent | RefinementCompleteEvent


def strip_mentions(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if not t:
        return ""
    t = re.sub(r"^(?:@\S+\s+)+", "", t).strip()
    t = re.sub(r"@\S+", "", t).strip()
    return t


def _append_outbox(state: StoryState, action: dict[str, Any]) -> None:
    ob = state.get("outbox")
    if not isinstance(ob, list):
        state["outbox"] = []
    state["outbox"].append(action)


def _looks_like_substantive_new_brief(t: str) -> bool:
    """Heuristic: user is sending a new assignment, not confirming the framework."""
    if len(t) > 420:
        return True
    if t.count(".") >= 3 and len(t) > 150:
        return True
    return bool(
        re.search(
            r"\b(i want you to|i need you to|write (me )?(a |the )|draft (a |me )|"
            r"create (a |me )(presentation|pitch|story)|help me (write|draft)|"
            r"pitch (for|to) |business case (for|about)|presentation (on|about|for))\b",
            t,
            re.I,
        )
    )


def _is_yes(text: str) -> bool:
    """True for confirmations — exact tokens, Hinglish, and casual English ('sounds good', 'go ahead')."""
    t = strip_mentions(text).strip().lower()
    if not t:
        return False
    if len(t) > 280:
        return False
    if _looks_like_substantive_new_brief(t):
        return False

    if t in {
        "y",
        "yes",
        "ok",
        "okay",
        "sure",
        "yeah",
        "yep",
        "go",
        "proceed",
        "generate",
        "looks good",
        "perfect",
        "great",
        "fine",
        "cool",
        "👍",
        "✅",
    }:
        return True

    # Hinglish / Roman Urdu (common in chat)
    if t in {
        "haan",
        "haan ji",
        "han",
        "han ji",
        "theek hai",
        "thik hai",
        "theek",
        "chaliye",
        "chalo",
        "sahi hai",
        "sahi",
        "bilkul",
        "kar do",
        "kardo",
        "banado",
        "ji",
        "ji haan",
    }:
        return True
    if re.match(r"^(haan|han|theek|thik|chaliye|chalo)\b", t) and len(t) < 72:
        return True

    # Casual confirmations (no leading 'yes' required)
    if len(t) <= 200:
        soft = (
            "go ahead",
            "go for it",
            "do it",
            "let's do it",
            "lets do it",
            "sounds good",
            "sounds great",
            "works for me",
            "that works",
            "fine by me",
            "all good",
            "please continue",
            "please proceed",
            "yes please",
            "yeah please",
            "yep please",
            "ok please",
            "okay please",
            "keep going",
            "use this",
            "stick with",
            "stick with this",
            "confirmed",
            "agreed",
            "approved",
            "lgtm",
            "ship it",
        )
        if any(p in t for p in soft):
            return True

    # Starts with yes/ok + proceed / continue (avoids classifying a new pitch as yes)
    first = t.split(None, 1)[0].strip(".,!\"'")
    if first in {"y", "yes", "yeah", "yep", "ok", "okay", "sure"}:
        if re.search(r"\b(proceed|continue)\b", t) and not re.search(
            r"\b(pitch|brief|story about|write me|i want to (create|write|draft))\b",
            t,
        ):
            return True
        if re.search(r"\b(go ahead|let'?s go|lets go|let'?s proceed|sound(s)? good)\b", t) and len(t) < 200:
            return True
        # "yes please", "ok thanks" — short polite confirmations (not a new brief)
        rest = t.split(None, 1)[1].strip(".,!\"'") if len(t.split(None, 1)) > 1 else ""
        if rest in {"please", "pls", "plz", "thanks", "thank you", "ty", "thx"} and len(t) < 96:
            return True
    return False


def is_affirmation_only(text: str) -> bool:
    """True when the user is only confirming (yes/ok/etc.) with no edit instructions — used by handlers."""
    return _is_yes(text)


def _is_too_thin_for_idle_brief(text: str) -> bool:
    """Reject single-token chitchat / confirmations as a 'brief' when stage is idle."""
    t = strip_mentions(text).strip()
    if not t:
        return True
    if _extract_framework_choice(text):
        return False
    if _is_yes(text):
        return True
    tl = t.lower()
    if len(t) < 12 and " " not in t and not any(ch.isdigit() for ch in t):
        if tl in {
            "hi",
            "hey",
            "hello",
            "thanks",
            "thankyou",
            "thx",
            "bye",
            "yo",
        }:
            return True
    return False


def _is_greeting(text: str) -> bool:
    t = strip_mentions(text).strip().lower()
    return t in {"hi", "hey", "hello", "yo", "sup", "hii", "hiii", "namaste", "hola"}


def _is_satisfied(text: str) -> bool:
    """User is expressing satisfaction/closure — story is done, no further action."""
    t = strip_mentions(text).strip().lower()
    if not t or len(t) > 200:
        return False
    signals = (
        "thanks", "thank you", "thankyou", "thx", "ty",
        "that works", "thats work", "that's work", "works for me",
        "looks good", "looks great", "its good", "it's good",
        "no thanks", "no thank", "no change", "no more",
        "im good", "i'm good", "all good", "good enough",
        "its ok", "it's ok", "its fine", "it's fine",
        "perfect", "awesome", "great job", "well done",
        "nah i'm good", "nah im good", "done", "all set",
    )
    return any(sig in t for sig in signals)


def _is_no(text: str) -> bool:
    t = strip_mentions(text).strip().lower()
    if t in {"n", "no", "nope", "change", "different", "switch"}:
        return True
    return False


def _asks_which_framework_help(text: str) -> bool:
    """User is asking which framework to use / help choosing — not a failed yes/no."""
    t = strip_mentions(text).strip().lower()
    if not t or len(t) > 220:
        return False
    needles = (
        "which one",
        "which framework",
        "which should i",
        "which do i",
        "which would you",
        "what should i pick",
        "what should i choose",
        "help me choose",
        "help me pick",
        "help me decide",
        "not sure which",
        "dont know which",
        "don't know which",
        "which is better",
        "which is best",
        "idk which",
        "confused which",
        "which to use",
    )
    return any(n in t for n in needles)


def _wants_refinement(text: str) -> bool:
    t = strip_mentions(text).strip().lower()
    refinement_signals = [
        "refine",
        "improve",
        "change",
        "modify",
        "update",
        "edit",
        "make it",
        # Avoid bare "can you" — phrases like "can you do it" are often go-aheads, not edit requests.
        "can you make",
        "can you add",
        "can you remove",
        "can you change",
        "can you update",
        "can you shorten",
        "can you expand",
        "can you rewrite",
        "can you tweak",
        "can you fix",
        "adjust",
        "rewrite",
        "revise",
        "tweak",
        "more",
        "less",
        "stronger",
        "shorter",
        "longer",
        "different",
        "fix",
        "tone",
        "opening",
        "paragraph",
        "snappier",
        "urgent",
    ]
    return any(sig in t for sig in refinement_signals)


def _wants_evaluation(text: str) -> bool:
    t = strip_mentions(text).strip().lower()
    eval_signals = [
        "evaluate",
        "evaluation",
        "score",
        "assess",
        "rate",
        "review",
        "check",
        "validate",
    ]
    return any(sig in t for sig in eval_signals)


def _implicit_story_feedback(text: str) -> bool:
    """Long free-form change request without keywords like 'refine' (post-narrative menu)."""
    t = strip_mentions(text).strip()
    return len(t) >= 40


def _wants_new_story(text: str) -> bool:
    t = strip_mentions(text).strip().lower()
    new_signals = ["new story", "start over", "new brief", "fresh", "another", "new narrative", "reset"]
    if any(sig in t for sig in new_signals):
        return True
    # Standalone "new" or short phrases like "try new", "want new"
    if t == "new":
        return True
    if len(t) < 40 and " new" in t and not any(w in t for w in ("framework", "4c", "hero", "hole", "medias")):
        return True
    return False


def same_brief_new_framework_request(text: str) -> bool:
    """Re-draft the existing narrative using another named framework (same structured brief in state)."""
    if not _extract_framework_choice(text):
        return False
    t = strip_mentions(text).strip().lower()
    if len(t) > 220:
        return False
    cues = (
        "above",
        "previous",
        "that story",
        "that one",
        "last story",
        "same story",
        "same brief",
        "new framework",
        "different framework",
        "another framework",
        "rewrite",
        "redo",
        "reframe",
        "convert",
        "apply the",
        "switch to",
        "change to",
        "make the",
        "make it",
        "can you make",
        "with the",
        " same",
        "do it in",
    )
    return any(c in t for c in cues)


def user_intends_post_story_resume(text: str) -> bool:
    """Evaluate / refine / re-framework on an existing draft — used to recover lost ``story_ready`` stage."""
    return bool(
        _wants_evaluation(text)
        or _wants_refinement(text)
        or same_brief_new_framework_request(text)
    )


def _extract_framework_choice(text: str) -> str | None:
    t = strip_mentions(text).strip().lower()
    mapping = {
        "business": "business",
        "4cs": "4cs",
        "4c": "4cs",
        "4 c": "4cs",
        "four c": "4cs",
        "hero": "heros_journey",
        "journey": "heros_journey",
        "man in": "man_in_hole",
        "hole": "man_in_hole",
        "resilience": "man_in_hole",
        "recovery": "man_in_hole",
        "medias res": "in_medias_res",
        "in medias": "in_medias_res",
        "hook": "in_medias_res",
        "immediate": "in_medias_res",
    }
    for key, fid in mapping.items():
        if key in t:
            return fid
    return None


def default_state() -> StoryState:
    return {
        "stage": "idle",
        "raw_brief": "",
        "structured_brief": {},
        "framework_id": "",
        "framework_rationale": "",
        "generated_story": "",
        "evaluation": "",
        "refinement_count": 0,
        "outbox": [],
    }


def _node_collect_brief(state: StoryState) -> StoryState:
    _append_outbox(
        state,
        {
            "type": "send_text",
            "text": (
                "I've received your brief. Let me analyze it and recommend the best storytelling framework...\n\n"
                "⏳ Working on it now."
            ),
        },
    )
    state["stage"] = "collect_brief"
    return state


def _node_confirm_framework(state: StoryState) -> StoryState:
    fid = state.get("framework_id", "business")
    rationale = state.get("framework_rationale", "")
    summary = get_framework_summary(fid)
    why_block = ""
    if rationale and not rationale_is_user_pick_placeholder(str(rationale)):
        why_block = f"**Why This Framework:** {rationale}\n\n"

    _append_outbox(
        state,
        {
            "type": "send_text",
            "text": (
                f"📋 **Recommended Framework:**\n\n{summary}\n\n"
                f"{why_block}"
                f"{framework_confirmation_footer(fid)}"
            ),
        },
    )
    state["stage"] = "confirm_framework"
    return state


def _node_generating(state: StoryState) -> StoryState:
    # Single follow-up bubble after generation (instacart-style: no "typing" message that the UI replaces).
    _append_outbox(state, {"type": "generate_story"})
    state["stage"] = "generating"
    return state


def _node_story_ready(state: StoryState) -> StoryState:
    story = state.get("generated_story", "")
    count = state.get("refinement_count", 0)
    version_label = f"v{count + 1}" if count > 0 else ""
    header = f"✅ **Your Narrative{' (' + version_label + ')' if version_label else ''}**"

    combined = f"{header}\n\n{story}\n\n---\n{_STORY_MENU}"
    _append_outbox(state, {"type": "send_text", "text": combined})
    state["stage"] = "story_ready"
    return state


def _node_refining(state: StoryState) -> StoryState:
    _append_outbox(state, {"type": "refine_story"})
    state["stage"] = "refining"
    return state


def clear_outbox(state: StoryState) -> None:
    state["outbox"] = []


def _ensure_state_defaults(state: StoryState) -> None:
    if not isinstance(state.get("stage"), str) or not state.get("stage"):
        state["stage"] = "idle"
    if not isinstance(state.get("refinement_count"), int):
        state["refinement_count"] = 0


def _greeting_nudge(state: StoryState, stage: Stage) -> dict[str, Any] | None:
    """Contextual response when user sends a greeting mid-flow."""
    if stage == "collect_brief":
        if (state.get("raw_brief") or "").strip():
            return {"type": "process_brief"}
        return {"type": "send_text", "text": "I'm here! Share your story brief — objective, audience, and format."}
    if stage == "confirm_framework":
        fid = str(state.get("framework_id") or "business")
        return {"type": "send_text", "text": f"Still here! We have a framework ready.\n\n{framework_confirmation_footer(fid)}"}
    if stage == "generating":
        return {"type": "send_text", "text": "Still drafting your narrative — hang tight!"}
    if stage == "story_ready":
        return {"type": "send_text", "text": _STORY_MENU}
    if stage == "refining":
        return {"type": "send_text", "text": "Still applying your edits — almost there!"}
    return None


def apply_story_event(prior: StoryState, event: Event) -> StoryState:
    """Pure transition: one event applied to prior checkpoint state (LangGraph node body)."""
    state: StoryState = {**prior}
    _ensure_state_defaults(state)
    clear_outbox(state)

    stage: Stage = state.get("stage", "idle")

    if event["type"] == "generation_complete":
        state["generated_story"] = event.get("story", "")
        state["framework_id"] = event.get("framework_id", state.get("framework_id", "business"))
        state["structured_brief"] = event.get("brief", state.get("structured_brief", {}))
        state["framework_rationale"] = event.get("rationale", state.get("framework_rationale", ""))
        state = _node_story_ready(state)
        state.pop("event", None)
        return state

    if event["type"] == "evaluation_complete":
        evaluation = event.get("evaluation", "")
        state["evaluation"] = evaluation
        combined = f"📊 **Story Evaluation**\n\n{evaluation}\n\n---\n{_EVAL_MENU}"
        _append_outbox(state, {"type": "send_text", "text": combined})
        state["stage"] = "story_ready"
        state.pop("event", None)
        return state

    if event["type"] == "refinement_complete":
        state["generated_story"] = event.get("refined_story", "")
        state["refinement_count"] = (state.get("refinement_count") or 0) + 1
        state = _node_story_ready(state)
        state.pop("event", None)
        return state

    control = strip_mentions(event.get("control_text") or "")

    if _is_greeting(control) and stage != "idle":
        nudge = _greeting_nudge(state, stage)
        if nudge:
            _append_outbox(state, nudge)
        state.pop("event", None)
        return state

    if stage == "idle":
        if control:
            if _is_too_thin_for_idle_brief(control):
                _append_outbox(state, {
                    "type": "send_text",
                    "text": "Send your **pitch or story goal** first (objective, audience, format). "
                            "After I recommend a framework, reply **yes** to generate the narrative.",
                })
            else:
                state["raw_brief"] = control
                state["stage"] = "collect_brief"
                _append_outbox(state, {"type": "process_brief"})
        else:
            _append_outbox(state, {
                "type": "send_text",
                "text": "Please describe what story or narrative you need — include the objective, audience, and format.",
            })

    elif stage == "collect_brief":
        if control:
            state["raw_brief"] = (state.get("raw_brief", "") + "\n" + control).strip()
            _append_outbox(state, {"type": "process_brief"})

    elif stage == "confirm_framework":
        if _is_yes(control):
            state = _node_generating(state)
        elif _wants_new_story(control):
            state = default_state()
            _append_outbox(state, {"type": "send_text", "text": _FRESH_START_MSG})
        elif _asks_which_framework_help(control):
            fid_now = str(state.get("framework_id") or "business")
            rationale_now = str(state.get("framework_rationale") or "")
            _append_outbox(state, {"type": "send_text", "text": framework_recommendation_reminder(fid_now, rationale_now)})
        elif _extract_framework_choice(control) or _is_no(control):
            chosen = _extract_framework_choice(control)
            if chosen:
                state["framework_id"] = chosen
                state["framework_rationale"] = f"User selected {chosen} framework."
            state = _node_confirm_framework(state)
        elif _looks_like_substantive_new_brief(control):
            state["raw_brief"] = control
            state["stage"] = "collect_brief"
            _append_outbox(state, {"type": "process_brief"})
        else:
            fid_now = str(state.get("framework_id") or "business")
            _append_outbox(state, {"type": "send_text", "text": f"Not sure what you mean.\n\n{framework_confirmation_footer(fid_now)}"})

    elif stage == "generating":
        if control.strip():
            _append_outbox(state, {"type": "send_text", "text": "Still drafting your narrative — it'll arrive shortly."})

    elif stage == "story_ready":
        if _wants_new_story(control):
            state = default_state()
            _append_outbox(state, {"type": "send_text", "text": f"🔄 {_FRESH_START_MSG}"})
        elif same_brief_new_framework_request(control):
            fid = _extract_framework_choice(control)
            if fid:
                state["framework_id"] = fid
                state["framework_rationale"] = (
                    "Re-drafted from the same structured brief using the framework you requested in chat."
                )
                state = _node_generating(state)
        elif _wants_evaluation(control):
            _append_outbox(state, {"type": "evaluate_story", "user_text": control})
        elif _looks_like_substantive_new_brief(control):
            # User sent a whole new brief while at story_ready — start fresh pipeline.
            state["raw_brief"] = control
            state["stage"] = "collect_brief"
            _append_outbox(state, {"type": "process_brief"})
        elif _wants_refinement(control):
            state["stage"] = "refining"
            _append_outbox(state, {"type": "refine_story", "feedback": control})
        elif _implicit_story_feedback(control):
            state["stage"] = "refining"
            _append_outbox(state, {"type": "refine_story", "feedback": control})
        elif _is_satisfied(control):
            _append_outbox(state, {
                "type": "send_text",
                "text": "Glad it works for you! If you need another story or want to revisit this one later, just send a new brief.",
            })
        else:
            _append_outbox(state, {"type": "send_text", "text": _STORY_MENU})

    elif stage == "refining":
        if control.strip():
            _append_outbox(state, {"type": "send_text", "text": "I'm still applying your last edit. Wait for that reply, then send more changes if needed."})

    state.pop("event", None)
    return state


def story_graph_node(state: StoryState) -> StoryState:
    """Single compiled node: merge checkpoint + optional ``event`` input from ``ainvoke``."""
    merged = dict(state)
    ev_raw = merged.pop("event", None)
    prior = {**default_state(), **merged}
    prior.pop("event", None)
    if not ev_raw:
        return prior
    return apply_story_event(prior, cast(Event, ev_raw))


def build_compiled_story_graph(checkpointer: Any) -> Any:
    """``StateGraph`` + checkpointer (Postgres or in-memory), same pattern as instacart-agent."""
    g = StateGraph(StoryState)
    g.add_node("story", story_graph_node)
    g.add_edge(START, "story")
    g.add_edge("story", END)
    return g.compile(checkpointer=checkpointer)


@dataclass(frozen=True)
class StepResult:
    state: StoryState
    outbox: list[dict[str, Any]]
