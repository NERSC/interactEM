from contextlib import asynccontextmanager

from faststream import Context, ContextRepo, FastStream
from faststream.nats import JStream, NatsBroker
from nats.js.api import RetentionPolicy

from interactem.core.config import cfg as nats_cfg
from interactem.core.constants import STREAM_AGENTS, STREAM_NOTIFICATIONS
from interactem.core.logger import get_logger
from interactem.core.models.pipeline import PipelineAssignment
from interactem.core.nats.consumers import AGENT_CONSUMER_CONFIG

from .agent import Agent, cfg


def get_nats_broker(servers: list[str], name: str) -> NatsBroker:
    options_map = {
        nats_cfg.NATS_SECURITY_MODE.NKEYS: {
            "nkeys_seed_str": nats_cfg.NKEYS_SEED_STR,
        },
        nats_cfg.NATS_SECURITY_MODE.CREDS: {
            "user_credentials": str(nats_cfg.NATS_CREDS_FILE),
        },
    }
    options = options_map[nats_cfg.NATS_SECURITY_MODE]

    async def disconnected_cb():
        logger.info("NATS disconnected.")

    async def reconnected_cb():
        logger.info("NATS reconnected.")

    async def closed_cb():
        logger.info("NATS connection closed.")

    return NatsBroker(
        servers=servers,
        name=name,
        reconnected_cb=reconnected_cb,
        disconnected_cb=disconnected_cb,
        closed_cb=closed_cb,
        **options,
    )


logger = get_logger()
AGENT_ID = cfg.ID
broker = get_nats_broker(servers=[str(cfg.NATS_SERVER_URL)], name=f"agent-{AGENT_ID}")

@asynccontextmanager
async def lifespan(context: ContextRepo):
    yield

app = FastStream(broker=broker, lifespan=lifespan)

NOTIFICATIONS_JSTREAM = JStream(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[f"{STREAM_NOTIFICATIONS}.>"],
    retention=RetentionPolicy.INTEREST,
)

error_pub = broker.publisher(
    stream=NOTIFICATIONS_JSTREAM,
    subject=f"{STREAM_NOTIFICATIONS}.errors",
)


@app.after_startup
async def after_startup(context: ContextRepo, broker: NatsBroker = Context()):
    agent = Agent(id=AGENT_ID, broker=broker)
    agent.error_publisher = error_pub
    context.set_global("agent", agent)
    await agent.run()


@app.on_shutdown
async def on_shutdown(agent: Agent = Context()):
    agent._shutdown_event.set()
    await agent.shutdown()


AGENT_JSTREAM = JStream(
    name=STREAM_AGENTS,
    description="A stream for messages to the agents.",
    subjects=[f"{STREAM_AGENTS}.>"],
)

agent_consumer_config = AGENT_CONSUMER_CONFIG
agent_consumer_config.description = f"agent-{AGENT_ID}"

@broker.subscriber(
    stream=AGENT_JSTREAM,
    subject=f"{STREAM_AGENTS}.{AGENT_ID}",
    config=agent_consumer_config,
    pull_sub=True,
)
async def assignment_handler(assignment: PipelineAssignment, agent: Agent = Context()):
    await agent.receive_assignment(assignment)
