"""
Storytelling knowledge base derived from Tatia's Business Framework,
the Decision-Based Framework Selector, and all narrative frameworks.

Each framework is stored as a dict with structured fields so the agent
can retrieve, explain, and apply them during conversation.
"""

from __future__ import annotations

import re
from typing import TypedDict


class FrameworkDef(TypedDict, total=False):
    id: str
    name: str
    best_for: str
    brief_explanation: str
    caution: str
    elements: list[dict[str, str]]
    simple_flow: list[str]
    speaking_formula: str
    story_template_fields: list[dict[str, str]]


BUSINESS_FRAMEWORK: FrameworkDef = {
    "id": "business",
    "name": "Business Framework (Default)",
    "best_for": "Clear, practical business communication",
    "brief_explanation": (
        "Use when you need a logical flow, a strong message, and a usable outcome. "
        "Structures a presentation around a real audience, a clear challenge, and a persuasive solution."
    ),
    "caution": "Avoid freeform narrative drift when a clear brief or framework is present.",
    "elements": [
        {
            "element": "Context",
            "key_question": "What is the current situation?",
            "include": "The setting, background, audience, business conditions, and relevant facts.",
            "audience_feel": "I understand the starting point.",
        },
        {
            "element": "Innovation / Solution",
            "key_question": "What is the proposed answer?",
            "include": "The idea, product, strategy, or approach being recommended.",
            "audience_feel": "This is a credible path forward.",
        },
        {
            "element": "Outcome",
            "key_question": "What will change?",
            "include": "Expected results, benefits, metrics, and evidence of impact.",
            "audience_feel": "This decision has clear value.",
        },
        {
            "element": "Key Message",
            "key_question": "So what?",
            "include": "A concise, memorable statement of meaning the audience should take away.",
            "audience_feel": "I know exactly what matters.",
        },
    ],
    "simple_flow": [
        "Identify the persona. Define the audience, users, stakeholders, or decision-makers.",
        "Define the challenge. State the problem clearly and explain why it matters now.",
        "Build the narrative. Use Context, Innovation / Solution, Outcome, and Key Message.",
        "Support the story. Use data, examples, and AI tools to strengthen the argument.",
        "End with action. Make it clear what the audience should understand, decide, fund, adopt, or change.",
    ],
    "speaking_formula": (
        "Start here: The current context is [situation]. "
        "Introduce the innovation: Our solution is [idea / tool / process], which works by [brief explanation]. "
        "Show the outcome: This could lead to [benefits / impact / metrics]. "
        "End with meaning: The key message is that [so what]."
    ),
    "story_template_fields": [
        {
            "field": "Audience / Persona",
            "include": "Who they are. What they care about. What decision they need to make.",
        },
        {"field": "Context", "include": "The current environment, system, or business reality."},
        {"field": "Challenge", "include": "The core problem, risk, inefficiency, or pressure point."},
        {"field": "Innovation / Solution", "include": "The proposed action, solution, or strategic direction."},
        {"field": "Outcome", "include": "What this will improve. What the measurable effect could be."},
        {"field": "Key Message", "include": "What the audience should take away."},
    ],
}


FOUR_CS_FRAMEWORK: FrameworkDef = {
    "id": "4cs",
    "name": "4 C's Framework",
    "best_for": "Clear problem to clear solution",
    "brief_explanation": (
        "Use when the issue is clear, the answer is clear, and the audience needs proof. "
        "Designed for business cases, proposals, recommendation papers, and presentations that need clarity, logic, and proof."
    ),
    "caution": "Works best when the problem is already visible; less suited for exploratory or change-oriented narratives.",
    "elements": [
        {
            "element": "Context",
            "key_question": "What is the current situation?",
            "include": "The setting, background, audience, business conditions, and relevant facts.",
            "audience_feel": "I understand the starting point.",
        },
        {
            "element": "Complication",
            "key_question": "What is making this difficult or urgent?",
            "include": "The obstacle, pain point, inefficiency, risk, tension, or missed opportunity.",
            "audience_feel": "This issue is real and needs attention.",
        },
        {
            "element": "Choice",
            "key_question": "What should we do?",
            "include": "The proposed decision, solution, direction, or intervention, with rationale.",
            "audience_feel": "This is the sensible path.",
        },
        {
            "element": "Consequence",
            "key_question": "What happens next?",
            "include": "Expected results, gains, trade-offs, metrics, and what happens if the choice is accepted or ignored.",
            "audience_feel": "This decision has clear value.",
        },
    ],
    "simple_flow": [
        "Define the situation. Explain what is happening and who it affects.",
        "Clarify the complication. Show the friction, urgency, or barrier.",
        "Present the choice. State the solution or decision clearly.",
        "Prove the consequence. Show likely outcomes with evidence, examples, or metrics.",
        "End with action. Make the required decision explicit.",
    ],
    "speaking_formula": (
        "Start here: The current context is [situation]. "
        "Introduce the complication: The problem is [issue], which matters because [stakes]. "
        "Present the choice: The best next step is [decision / solution]. "
        "Show the consequence: This could lead to [benefits / results / avoided risk]. "
        "End with action: We should now [approve / adopt / invest / change]."
    ),
    "story_template_fields": [
        {
            "field": "Audience / Persona",
            "include": "Who they are. What they care about. What decision they need to make.",
        },
        {"field": "Context", "include": "The current environment, system, or business reality."},
        {"field": "Complication", "include": "The core problem, risk, inefficiency, or pressure point."},
        {"field": "Choice", "include": "The proposed action, solution, or strategic direction."},
        {"field": "Consequence", "include": "What this choice will improve. What the measurable effect could be."},
        {"field": "Key Decision", "include": "What the audience is being asked to approve, fund, support, or adopt."},
    ],
}


HEROS_JOURNEY_FRAMEWORK: FrameworkDef = {
    "id": "heros_journey",
    "name": "Hero's Journey Framework",
    "best_for": "Adoption, change, or buy-in",
    "brief_explanation": (
        "Use when the audience needs to move from hesitation to commitment. "
        "Useful for transformation stories, change communication, innovation adoption, and stakeholder buy-in. "
        "The audience, user, team, or organisation is the hero. The presenter is a guide."
    ),
    "caution": "Requires a genuine transformation arc; don't force heroic framing on simple operational updates.",
    "elements": [
        {
            "element": "Ordinary World",
            "key_question": "What is the current state before change?",
            "include": "The current way of working, existing habits, familiar routines, and why they feel stable.",
            "audience_feel": "I recognise this world.",
        },
        {
            "element": "Call to Change",
            "key_question": "Why must something change now?",
            "include": "The trigger, shift, disruption, opportunity, or pressure that makes change necessary.",
            "audience_feel": "I see why standing still is risky.",
        },
        {
            "element": "Challenge and Resistance",
            "key_question": "What makes change difficult?",
            "include": "Doubts, fears, constraints, competing priorities, or cultural resistance.",
            "audience_feel": "This feels human and believable.",
        },
        {
            "element": "Guide and Path",
            "key_question": "What support or solution helps the hero move forward?",
            "include": "The tool, strategy, framework, team, or process that enables progress.",
            "audience_feel": "There is a credible way through this.",
        },
        {
            "element": "Transformation",
            "key_question": "What changes after the journey?",
            "include": "New capability, improved performance, stronger alignment, better outcomes, or adoption.",
            "audience_feel": "Change is possible and worthwhile.",
        },
        {
            "element": "Return with Value",
            "key_question": "What lasting benefit comes back to the wider group?",
            "include": "Organisational gain, user benefit, shared learning, scale, or long-term impact.",
            "audience_feel": "This creates meaningful value.",
        },
    ],
    "simple_flow": [
        "Start with the familiar world. Show the audience where they are now.",
        "Introduce the call to change. Explain the trigger or opportunity.",
        "Acknowledge resistance. Name the barriers honestly.",
        "Position the solution as guidance. Show how the path becomes manageable.",
        "Describe transformation. Explain what success looks like.",
        "End with shared value. Make clear how the wider group benefits.",
    ],
    "speaking_formula": (
        "Start here: Today, [audience] operates in a world where [current state]. "
        "Introduce the call: This is changing because [trigger / opportunity / pressure]. "
        "Acknowledge resistance: The real challenge is [fear / obstacle / friction]. "
        "Offer the guide: Our solution helps them move forward by [how it helps]. "
        "Show transformation: As a result, they can [new capability / improvement]. "
        "End with value: This matters because it creates [shared benefit / wider impact]."
    ),
    "story_template_fields": [
        {
            "field": "Audience / Hero",
            "include": "The user, team, customer, or stakeholder group whose journey matters.",
        },
        {"field": "Ordinary World", "include": "The current situation and what feels familiar or comfortable."},
        {"field": "Call to Change", "include": "The reason change is now necessary or attractive."},
        {"field": "Resistance", "include": "The fears, objections, or operational barriers."},
        {"field": "Guide / Solution", "include": "The system, proposal, product, or support mechanism that helps."},
        {"field": "Transformation and Shared Value", "include": "The improved future state plus the broader impact."},
    ],
}


MAN_IN_HOLE_FRAMEWORK: FrameworkDef = {
    "id": "man_in_hole",
    "name": "Man in the Hole Framework",
    "best_for": "Risk, recovery, or resilience",
    "brief_explanation": (
        "Use when the story needs to show setback, response, and credible recovery. "
        "Designed for stories of challenge, setback, and recovery without glorifying the difficulty itself."
    ),
    "caution": "Don't dramatise or overplay the descent; the value is in the disciplined response and what was learned.",
    "elements": [
        {
            "element": "Stable Ground",
            "key_question": "What was the initial situation?",
            "include": "The baseline, expected path, or normal state before the setback.",
            "audience_feel": "I understand where things started.",
        },
        {
            "element": "Descent",
            "key_question": "What went wrong?",
            "include": "The disruption, setback, risk, mistake, failure, or external pressure.",
            "audience_feel": "This is serious and credible.",
        },
        {
            "element": "Lowest Point",
            "key_question": "Why was this a real challenge?",
            "include": "The consequences, tension, uncertainty, and what was at stake.",
            "audience_feel": "The challenge was genuinely difficult.",
        },
        {
            "element": "Recovery Action",
            "key_question": "What was done in response?",
            "include": "The decisions, interventions, leadership, support, or correction steps taken.",
            "audience_feel": "There was a disciplined response.",
        },
        {
            "element": "Climb Out",
            "key_question": "How did improvement happen?",
            "include": "Evidence of recovery, learning, restored performance, or renewed confidence.",
            "audience_feel": "Progress was earned and believable.",
        },
        {
            "element": "Stronger Position",
            "key_question": "What is better now?",
            "include": "Lessons learned, resilience gained, prevention measures, or strategic advantage.",
            "audience_feel": "This experience produced durable value.",
        },
    ],
    "simple_flow": [
        "Establish the baseline. Show what normal looked like.",
        "Introduce the setback. Explain what disrupted that baseline.",
        "Clarify the stakes. Show why the low point mattered.",
        "Describe the response. Focus on actions, judgment, and recovery steps.",
        "Show the climb out. Present evidence of improvement.",
        "End with resilience. Highlight what is stronger now.",
    ],
    "speaking_formula": (
        "Start here: We began from [baseline / expectation]. "
        "Introduce the descent: Then [setback / disruption] created a serious challenge. "
        "Show the low point: At stake was [risk / cost / trust / performance]. "
        "Explain the response: We addressed this through [actions / solution / intervention]. "
        "Show recovery: This led to [improvement / recovery / measurable result]. "
        "End with resilience: The key lesson is that we are now stronger because [learning / capability]."
    ),
    "story_template_fields": [
        {"field": "Audience / Stakeholder", "include": "Who experienced the challenge or is affected by the recovery."},
        {"field": "Stable Ground", "include": "The original condition, plan, or expectation."},
        {"field": "Setback", "include": "The risk, problem, crisis, or disruption that caused the drop."},
        {"field": "Lowest Point / Stakes", "include": "What was threatened. What could have been lost."},
        {"field": "Recovery Action", "include": "The response, mitigation, redesign, or support introduced."},
        {
            "field": "Recovery and Resilience Message",
            "include": "What improved, how this is evidenced, and what is now stronger.",
        },
    ],
}


IN_MEDIAS_RES_FRAMEWORK: FrameworkDef = {
    "id": "in_medias_res",
    "name": "In Medias Res Framework",
    "best_for": "An immediate hook",
    "brief_explanation": (
        "Use when you need to capture attention fast for a busy audience. "
        "Starts in the middle of tension, urgency, or action, then quickly explains context and moves to resolution."
    ),
    "caution": "The hook must be genuine and connect to the real issue — avoid clickbait openings that don't pay off.",
    "elements": [
        {
            "element": "Immediate Tension",
            "key_question": "What urgent moment are we entering?",
            "include": "A striking fact, live problem, decision point, conflict, or unresolved issue.",
            "audience_feel": "I need to pay attention now.",
        },
        {
            "element": "Rapid Orientation",
            "key_question": "What do I need to know to understand this?",
            "include": "Minimal background, actors, stakes, and why this moment matters.",
            "audience_feel": "I am now grounded in the story.",
        },
        {
            "element": "Core Problem",
            "key_question": "What is actually at stake?",
            "include": "The deeper issue, business challenge, risk, or opportunity beneath the opening tension.",
            "audience_feel": "This is important, not just dramatic.",
        },
        {
            "element": "Resolution Path",
            "key_question": "What can be done?",
            "include": "The proposed response, strategy, solution, or next move.",
            "audience_feel": "There is a clear way forward.",
        },
        {
            "element": "Outcome / Release",
            "key_question": "How does the tension resolve?",
            "include": "The result, benefit, lesson, or decision that closes the loop.",
            "audience_feel": "The story lands clearly and usefully.",
        },
    ],
    "simple_flow": [
        "Open with the moment of tension. Start where attention is highest.",
        "Orient the audience fast. Give only the context they need.",
        "Clarify the real issue. Connect the opening to the underlying problem.",
        "Present the resolution path. Show the answer clearly.",
        "Close the loop. Resolve the tension and leave a memorable takeaway.",
    ],
    "speaking_formula": (
        "Start here: At this moment, [urgent situation / striking fact / unresolved tension]. "
        "Orient fast: To understand this, the key context is [brief background]. "
        "Clarify the issue: The real problem is [core challenge / stake]. "
        "Present the response: We should address this through [solution / action]. "
        "Close the loop: This leads to [outcome / resolution / benefit]. "
        "End with meaning: The takeaway is [key message]."
    ),
    "story_template_fields": [
        {
            "field": "Hook",
            "include": "The surprising moment, urgent challenge, or unresolved question that opens the story.",
        },
        {"field": "Rapid Context", "include": "The shortest necessary background for understanding the hook."},
        {"field": "Core Problem", "include": "The deeper issue, risk, or opportunity that the opening reveals."},
        {"field": "Solution / Response", "include": "The action, proposal, or intervention that addresses the issue."},
        {
            "field": "Resolution / Outcome",
            "include": "The result, payoff, or decision that resolves the opening tension.",
        },
        {"field": "Key Takeaway", "include": "The message the audience should remember after the fast-paced opening."},
    ],
}


ALL_FRAMEWORKS: dict[str, FrameworkDef] = {
    "business": BUSINESS_FRAMEWORK,
    "4cs": FOUR_CS_FRAMEWORK,
    "heros_journey": HEROS_JOURNEY_FRAMEWORK,
    "man_in_hole": MAN_IN_HOLE_FRAMEWORK,
    "in_medias_res": IN_MEDIAS_RES_FRAMEWORK,
}


FRAMEWORK_SELECTOR_GUIDE = """Framework Selection Guide:

| Framework | Best For | When to Use |
|-----------|----------|-------------|
| Business (default) | Clear, practical business communication | Logical flow, strong message, usable outcome |
| 4 C's | Clear problem to clear solution | Issue is clear, answer is clear, audience needs proof |
| Hero's Journey | Adoption, change, or buy-in | Audience must move from hesitation to commitment |
| Man in the Hole | Risk, recovery, or resilience | Show setback, response, and credible recovery |
| In Medias Res | An immediate hook | Capture attention fast for a busy audience |

Use Business as the default. Switch frameworks when the communication goal specifically matches another pattern."""


EVALUATION_RUBRIC = {
    "clarity": "Is the message immediately understandable? Does each section flow logically?",
    "relevance": "Does the story speak to the stated audience and their actual concerns?",
    "feasibility": "Are the claims and outcomes realistic and grounded?",
    "impact": "Does the story create emotional and intellectual engagement?",
    "coherence": "Does the narrative hold together from opening to close?",
    "memorability": "Will the audience remember the key message after the presentation?",
}


VALIDATION_CHECKLIST = [
    "Audience defined clearly",
    "Problem/challenge stated with specificity",
    "Stakes are visible and urgent",
    "Framework fit is sound for the communication goal",
    "Resolution is clear and actionable",
    "Key message is concise and memorable",
]


class StoryBrief(TypedDict, total=False):
    objective: str
    audience: str
    stakes: str
    format: str
    channel: str
    tone: str
    constraints: str
    desired_outcome: str
    industry: str


class AudienceProfile(TypedDict, total=False):
    persona_name: str
    needs: str
    frustrations: str
    motivations: str
    decision_context: str
    emotional_trigger: str


def get_framework(framework_id: str) -> FrameworkDef | None:
    return ALL_FRAMEWORKS.get(framework_id)


def rationale_is_user_pick_placeholder(rationale: str) -> bool:
    """Internal line like 'User selected heros_journey framework.' — not shown in chat."""
    t = (rationale or "").strip().lower()
    if not t:
        return True
    return bool(re.match(r"^user selected \w+ framework\.?$", t))


def framework_followup_for_chat() -> str:
    """Reply when user asks 'and more?', 'what else?', etc. after seeing the framework list — not a story brief."""
    return (
        "I only use **these five** storytelling frameworks here — there isn’t a separate “more” beyond them: "
        "**Business**, **4 C’s**, **Hero’s Journey**, **Man in the Hole**, and **In Medias Res**.\n\n"
        "Pick one by name, or share a real **brief** (objective, audience, format) and I’ll recommend the best fit."
    )


def framework_catalog_for_chat() -> str:
    """Compact list for 'which frameworks?' — avoids running the story-brief / LLM pipeline."""
    lines = [
        "Here are the **frameworks** I can use to structure your narrative:",
        "",
    ]
    order = ("business", "4cs", "heros_journey", "man_in_hole", "in_medias_res")
    for fid in order:
        fw = ALL_FRAMEWORKS.get(fid)
        if not fw:
            continue
        lines.append(f"• **{fw['name']}** — {fw['best_for']}")
    lines.extend(
        [
            "",
            "Share your **objective**, **audience**, and **format** when you want a recommendation, "
            "or say **Business**, **4 C's**, **Hero's Journey**, **Man in the Hole**, or **In Medias Res** to pick one.",
        ]
    )
    return "\n".join(lines)


def framework_confirmation_footer(framework_id: str) -> str:
    """UX copy: selected framework + how to confirm or switch."""
    fw = get_framework(framework_id)
    label = fw["name"] if fw else framework_id
    return (
        f"**Next Step:** I will draft using **{label}**.\n"
        "To use a different structure, reply with a framework name. "
        "When you're ready, send a short go-ahead.\n\n"
        "• **Business** · **4 C's** · **Hero's Journey** · **Man in the Hole** · **In Medias Res**"
    )

def framework_recommendation_reminder(framework_id: str, rationale: str) -> str:
    """Restate framework choice when the user asks 'which one?' at confirm step."""
    fw = get_framework(framework_id)
    label = fw["name"] if fw else framework_id
    best = (fw.get("best_for") or "").strip() if fw else ""
    rat = (rationale or "").strip()
    if len(rat) > 500:
        rat = rat[:497] + "…"

    head = f"**Recommended:** {label}"
    if best:
        head += f" — {best}"
    head += ".\n\n"
    if rat and not rationale_is_user_pick_placeholder(rat):
        head += f"**Why This Framework:** {rat}\n\n"

    return (
        head
        + "Ready for the draft? Send a short go-ahead. "
        + "To switch, name one of the options below.\n\n"
        + "• **Business** · **4 C's** · **Hero's Journey** · **Man in the Hole** · **In Medias Res**"
    )


def get_framework_summary(framework_id: str) -> str:
    fw = get_framework(framework_id)
    if not fw:
        return f"Unknown framework: {framework_id}"

    lines = [
        f"**{fw['name']}**",
        f"**Best For:** {fw['best_for']}",
        fw["brief_explanation"],
        "",
        "**Narrative Flow:**",
    ]
    for i, step in enumerate(fw.get("simple_flow", []), 1):
        lines.append(f"  {i}. {step}")

    lines.append("")
    lines.append("**Speaking Formula:**")
    lines.append(fw.get("speaking_formula", ""))

    return "\n".join(lines)


def get_all_framework_summaries() -> str:
    lines = [FRAMEWORK_SELECTOR_GUIDE, ""]
    for fid in ALL_FRAMEWORKS:
        lines.append(get_framework_summary(fid))
        lines.append("")
    return "\n".join(lines)


def build_framework_prompt_context(framework_id: str) -> str:
    """Build a context block the LLM can use when generating a story."""
    fw = get_framework(framework_id)
    if not fw:
        fw = BUSINESS_FRAMEWORK

    lines = [
        f"FRAMEWORK: {fw['name']}",
        f"PURPOSE: {fw['brief_explanation']}",
        f"CAUTION: {fw.get('caution', '')}",
        "",
        "NARRATIVE ELEMENTS:",
    ]
    for elem in fw.get("elements", []):
        lines.append(f"  - {elem['element']}: {elem['include']}")
        lines.append(f"    Audience should feel: {elem.get('audience_feel', '')}")
    lines.append("")
    lines.append("SPEAKING FORMULA:")
    lines.append(fw.get("speaking_formula", ""))
    lines.append("")
    lines.append("VALIDATION CHECKLIST:")
    for item in VALIDATION_CHECKLIST:
        lines.append(f"  - {item}")

    return "\n".join(lines)
