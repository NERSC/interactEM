import asyncio

import anyio
from faststream import Context, ContextRepo, Depends, FastStream
from faststream.nats import NatsMessage

from interactem.core.constants import NATS_TIMEOUT_DEFAULT, SUBJECT_AGENTS_DEPLOYMENTS
from interactem.core.events.deployments import (
    AgentDeploymentEvent,
    AgentDeploymentEventType,
)
from interactem.core.logger import get_logger
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.consumers import AGENT_CONSUMER_CONFIG
from interactem.core.nats.publish import create_error_publisher
from interactem.core.nats.streams import DEPLOYMENTS_JSTREAM

from .agent import Agent, cfg

logger = get_logger()
AGENT_ID = cfg.ID
broker = get_nats_broker(servers=[str(cfg.NATS_SERVER_URL)], name=f"agent-{AGENT_ID}")
app = FastStream(broker, logger=logger)

error_pub = create_error_publisher(
    broker=broker,
    id=AGENT_ID,
)


@app.after_startup
async def after_startup(context: ContextRepo):
    agent = Agent(id=AGENT_ID, broker=broker)
    agent.error_publisher = error_pub
    agent.error_publisher.timeout = NATS_TIMEOUT_DEFAULT
    context.set_global("agent", agent)
    await agent.run()


@app.on_shutdown
async def on_shutdown(agent: Agent = Context()):
    await agent.shutdown()


PROGRESS_UPDATE_INTERVAL = 1 # sec
# Since receiving assignments can take a while, use dep to tell nats connection not to die.
async def progress(message: NatsMessage):
    async def in_progress_task():
        while True:
            await anyio.sleep(PROGRESS_UPDATE_INTERVAL)
            await message.in_progress()

    task = asyncio.create_task(in_progress_task())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except anyio.get_cancelled_exc_class():
            pass


progress_dep = Depends(progress)
agent_consumer_config = AGENT_CONSUMER_CONFIG
agent_consumer_config.description = f"agent-{AGENT_ID}"



@broker.subscriber(
    stream=DEPLOYMENTS_JSTREAM,
    subject=f"{SUBJECT_AGENTS_DEPLOYMENTS}.{AGENT_ID}",
    config=agent_consumer_config,
    pull_sub=True,
    dependencies=[progress_dep],
)
async def agent_deployment_event_handler(
    event: AgentDeploymentEvent, agent: Agent = Context()
):
    HANDLERS = {
        AgentDeploymentEventType.START: agent.receive_assignment,
        AgentDeploymentEventType.STOP: agent.receive_cancellation,
        AgentDeploymentEventType.RESTART_OPERATOR: agent.restart_canonical_operator,
    }
    await HANDLERS[event.root.type](event.root)
