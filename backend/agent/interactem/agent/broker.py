import asyncio

from faststream import Context, ContextRepo, Depends, FastStream
from faststream.nats import JStream, NatsBroker, NatsMessage
from nats.js.api import RetentionPolicy

from interactem.core.constants import STREAM_AGENTS, STREAM_NOTIFICATIONS
from interactem.core.logger import get_logger
from interactem.core.models.runtime import PipelineAssignment
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.consumers import AGENT_CONSUMER_CONFIG

from .agent import Agent, cfg

logger = get_logger()
AGENT_ID = cfg.ID
broker = get_nats_broker(servers=[str(cfg.NATS_SERVER_URL)], name=f"agent-{AGENT_ID}")

app = FastStream(broker=broker)

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
    await agent.shutdown()


AGENT_JSTREAM = JStream(
    name=STREAM_AGENTS,
    description="A stream for messages to the agents.",
    subjects=[f"{STREAM_AGENTS}.>"],
)

agent_consumer_config = AGENT_CONSUMER_CONFIG
agent_consumer_config.description = f"agent-{AGENT_ID}"


PROGRESS_UPDATE_INTERVAL = 1 # sec
# Since receiving assignments can take a while, use dep to tell nats connection not to die.
async def progress(message: NatsMessage):
    async def in_progress_task():
        while True:
            await asyncio.sleep(PROGRESS_UPDATE_INTERVAL)
            await message.in_progress()

    task = asyncio.create_task(in_progress_task())
    yield
    task.cancel()


progress_dep = Depends(progress)


@broker.subscriber(
    stream=AGENT_JSTREAM,
    subject=f"{STREAM_AGENTS}.{AGENT_ID}",
    config=agent_consumer_config,
    pull_sub=True,
    dependencies=[progress_dep],
)
async def assignment_handler(assignment: PipelineAssignment, agent: Agent = Context()):
    await agent.receive_assignment(assignment)
