from collections.abc import Callable
from dataclasses import replace
from typing import Annotated
from uuid import UUID, uuid4

from faststream import ContextRepo as ContextRepoAnnotation
from faststream import FastStream
from faststream.context import ContextRepo
from faststream.nats import KvWatch
from faststream.nats.annotations import NatsBroker as BrokerAnnotation
from faststream.nats.message import NatsKvMessage
from faststream.params import Context
from pydantic import BaseModel

from interactem.core.constants import (
    AGENTS,
    BUCKET_STATUS,
    OPERATORS,
    SUBJECT_PIPELINES_DEPLOYMENTS,
)
from interactem.core.events.pipelines import (
    PipelineEvent,
    PipelineRunEvent,
    PipelineStopEvent,
)
from interactem.core.logger import get_logger
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.consumers import ORCHESTRATOR_DEPLOYMENTS_CONSUMER_CONFIG
from interactem.core.nats.publish import (
    create_error_publisher,
    create_info_publisher,
)
from interactem.core.nats.streams import DEPLOYMENTS_JSTREAM
from interactem.orchestrator.state import OrchestratorState

from .config import cfg
from .constants import (
    DEPLOYMENT_ID_CTX_NAME,
    ERROR_PUBLISHER_CTX_NAME,
    INFO_PUBLISHER_CTX_NAME,
    ORCHESTRATOR_STATE_CTX_NAME,
)
from .exceptions import PipelineExceptionMiddleware
from .orchestrator import (
    handle_run_pipeline,
    handle_stop_pipeline_event,
)

"""
This is a bit confusing, so to clarify:
1. broker/app are main constructs of faststream
2. we provide a middleware to the app that handles exceptions, and then publishes
out updates
3. we are putting several different publishers into the context "repo", which is like a
dict that we can pass around in the functions that are wrapped by faststream

When we get a message, it comes in already deserialized into a PipelineEvent object,
and we look up the appropriate handler function for that event type, and we call it.
If an exception is raised it will be sent to this middleware
"""


NatsKvMsg = Annotated[NatsKvMessage, Context("message")]
OrchestratorStateAnnotation = Annotated[
    OrchestratorState, Context(ORCHESTRATOR_STATE_CTX_NAME)
]

logger = get_logger()
orchestrator_id = uuid4()

broker = get_nats_broker(
    [str(cfg.NATS_SERVER_URL)],
    name=f"orchestrator-{orchestrator_id}",
    middlewares=(PipelineExceptionMiddleware,),  # type: ignore[arg-type]
)

# publishers
error_pub = create_error_publisher(
    broker=broker,
    id=orchestrator_id,
)
info_pub = create_info_publisher(
    broker=broker,
    id=orchestrator_id,
)

context_repo = ContextRepo(
    {
        ERROR_PUBLISHER_CTX_NAME: error_pub,
        INFO_PUBLISHER_CTX_NAME: info_pub,
    }
)

HANDLERS: dict[type[BaseModel], Callable] = {
    PipelineRunEvent: handle_run_pipeline,
    PipelineStopEvent: handle_stop_pipeline_event,
}


@broker.subscriber(
    stream=DEPLOYMENTS_JSTREAM,
    subject=f"{SUBJECT_PIPELINES_DEPLOYMENTS}.*",  # all deployment IDs
    durable=ORCHESTRATOR_DEPLOYMENTS_CONSUMER_CONFIG.durable_name,
    config=replace(
        ORCHESTRATOR_DEPLOYMENTS_CONSUMER_CONFIG, name=f"orchestrator-{orchestrator_id}"
    ),
    pull_sub=True,
)
async def handle_deployment_event(
    event: PipelineEvent,
    broker: BrokerAnnotation,
    context: ContextRepoAnnotation,
    state: OrchestratorStateAnnotation,
):
    # TODO: have to do this until this changes in faststream:
    # https://github.com/ag2ai/faststream/pull/2619
    js = broker.config.connection_state.stream
    logger.info(f"Received pipeline deployment event ({event.root.type.value})")
    handler = HANDLERS.get(type(event.root))
    context.set_local(DEPLOYMENT_ID_CTX_NAME, event.root.deployment_id)

    if not handler:
        raise NotImplementedError(f"No handler for event type {event.root.type}")

    await handler(event.root, js, state)


# Always be listening to KV changes for agents/operators so we can react to things
@broker.subscriber(f"{AGENTS}.>", kv_watch=KvWatch(bucket=BUCKET_STATUS, declare=False))
async def agents(
    msg: NatsKvMsg,
    state: OrchestratorStateAnnotation,
):
    entry = msg.raw_message
    key = UUID(entry.key.removeprefix(f"{AGENTS}."))
    await state.agent_entry(key, entry)

@broker.subscriber(
    f"{OPERATORS}.>", kv_watch=KvWatch(bucket=BUCKET_STATUS, declare=False)
)
async def operators(
    msg: NatsKvMsg,
    state: OrchestratorStateAnnotation,
):
    entry = msg.raw_message
    key = UUID(entry.key.removeprefix(f"{OPERATORS}."))
    await state.op_entry(key, entry)


app = FastStream(
    broker,
    logger=logger,
    context=context_repo,
)

@app.on_startup
async def on(context: ContextRepoAnnotation):
    state = OrchestratorState(broker)
    context.set_global(ORCHESTRATOR_STATE_CTX_NAME, state)


@app.after_startup
async def after(context: ContextRepoAnnotation):
    logger.info("Initializing orchestrator state from KV...")
    state: OrchestratorState = context.get(ORCHESTRATOR_STATE_CTX_NAME)
    await state.initialize()
    logger.info("Orchestrator state initialization complete.")
