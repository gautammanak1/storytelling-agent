import os
import asyncio
from pathlib import Path

import dotenv
from uagents import Agent, Context
from uagents.crypto import Identity

dotenv.load_dotenv()

from protocols.chat_proto import story_chat_proto
from agents_shared.sentry import init_sentry
from agents_shared.health import start_health_server, mark_ready

_state_dir = os.getenv("AGENT_STATE_DIR")
if _state_dir:
    Path(_state_dir).mkdir(parents=True, exist_ok=True)
    os.chdir(_state_dir)


def _get_private_key() -> str | None:
    pk = os.getenv("PRIVATE_KEY")
    if isinstance(pk, str) and pk.strip():
        return pk.strip()
    return None


def _get_seed() -> str | None:
    seed = os.getenv("AGENT_SEED")
    if isinstance(seed, str) and seed.strip():
        return seed.strip()
    return None


_pk = _get_private_key()
_seed = _get_seed()
if not _pk and not _seed:
    raise RuntimeError("Missing identity. Set PRIVATE_KEY (preferred) or AGENT_SEED.")

agent = Agent(
    name="storytelling_agent",
    mailbox=True,
    port=8030,
    seed=_seed if not _pk else None,
    handle_messages_concurrently=False,
    agentverse=os.getenv("AGENTVERSE_URL"),
    mark_inactive_on_shutdown=False,
    shutdown_timeout=int(os.getenv("SHUTDOWN_TIMEOUT_SECONDS")),
)

if _pk:
    agent._identity = Identity.from_string(_pk)


@agent.on_event("startup")
async def startup(ctx: Context):
    asyncio.create_task(start_health_server())

    agent_address = None
    address_source = None
    if hasattr(ctx, "address") and ctx.address:
        agent_address = str(ctx.address)
        address_source = "ctx.address"
    elif hasattr(agent, "address") and agent.address:
        agent_address = str(agent.address)
        address_source = "agent.address"
    else:
        agent_address = str(agent.wallet.address())
        address_source = "agent.wallet.address()"

    ctx.logger.info(f"Storytelling Agent started: {agent_address} (from {address_source})")

    init_sentry(
        agent_name="storytelling_agent",
        agent_address=agent_address,
        environment=None,
        agent_type="storytelling",
        service="storytelling",
        version="1.0.0",
    )

    db_url_set = bool((os.getenv("DATABASE_URL") or "").strip())
    if not db_url_set:
        ctx.logger.info("[db] DATABASE_URL not set -> DB persistence DISABLED")
    else:
        ctx.logger.info("[db] DATABASE_URL is set -> attempting DB persistence init")
        try:
            from agents_shared.db import init_db

            await init_db(agent_name="storytelling_agent", agent_address=agent_address)
            ctx.logger.info("[db] DB persistence init OK")
        except Exception as e:
            ctx.logger.warning(f"[db] DB persistence init FAILED: {e}")

    try:
        from ai import setup_ai_instance

        db_url = (os.getenv("DATABASE_URL") or "").strip()
        used_pg = await setup_ai_instance(db_url or None)
        if used_pg:
            ctx.logger.info("[ai] LangGraph checkpointer: Postgres (multipod-safe with shared DB)")
        elif db_url:
            ctx.logger.info(
                "[ai] LangGraph checkpointer: in-memory — Postgres was unreachable or misconfigured "
                "(agent still runs; start Postgres or fix DATABASE_URL for persistence)"
            )
        else:
            ctx.logger.info("[ai] LangGraph checkpointer: in-memory (set DATABASE_URL for Postgres + multipod)")
    except Exception as exc:
        ctx.logger.warning(f"[ai] LangGraph setup failed: {exc}")
        try:
            from ai.runtime import ensure_compiled_fallback

            await ensure_compiled_fallback()
            ctx.logger.info("[ai] LangGraph recovered with in-memory checkpointer (so chat can run)")
        except Exception as exc2:
            ctx.logger.warning(f"[ai] LangGraph could not recover at startup (will retry on first message): {exc2}")

    asi_key = bool((os.getenv("ASI_ONE_API_KEY") or "").strip())
    model = os.getenv("STORY_MODEL", "asi1")

    ctx.logger.info("=== Storytelling Agent ===")
    ctx.logger.info(f"   LLM (ASI1): {'CONFIGURED' if asi_key else 'MISSING (set ASI_ONE_API_KEY)'}")
    ctx.logger.info(f"   Model: {model}")
    ctx.logger.info("   Frameworks: Business, 4 C's, Hero's Journey, Man in the Hole, In Medias Res")
    ctx.logger.info("   Ready to craft narratives!")

    mark_ready()

    if os.getenv("SENTRY_TEST_ERROR", "").lower() == "true":
        ctx.logger.info("Testing Sentry error capture...")
        from agents_shared.sentry import capture_agent_error

        try:
            raise ValueError("TEST ERROR: Sentry test for storytelling_agent")
        except Exception as test_error:
            capture_agent_error(
                test_error,
                extra_context={"test": {"purpose": "Sentry integration test", "agent_name": "storytelling_agent"}},
            )


agent.include(story_chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
