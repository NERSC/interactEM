import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import nats
from core.constants import BUCKET_AGENTS, SUBJECT_PIPELINES_RUN
from core.events.pipelines import PipelineRunEvent
from core.logger import get_logger
from core.models import CommBackend, URILocation
from core.models.uri import URI
from core.pipeline import Pipeline, PipelineJSON
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, KeyValueConfig
from nats.js.errors import BucketNotFoundError, NoKeysError
from pydantic import ValidationError

logger = get_logger("orchestrator", "DEBUG")

DEFAULT_NATS_ADDRESS: str = "nats://nats1:4222"
DEFAULT_ORCHESTRATOR_URI = URI(
    id=uuid4(),
    hostname="localhost",
    location=URILocation.orchestrator,
    comm_backend=CommBackend.NATS,
    query={"address": [DEFAULT_NATS_ADDRESS]},
)


async def handle_run_pipeline(msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline run event...")
    try:
        event = PipelineRunEvent.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        await msg.nak()
        return
    valid_pipeline = PipelineJSON(id=event.id, **event.data)
    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    _ = Pipeline.from_pipeline(valid_pipeline)

    number_of_agents = await get_current_num_agents(js)

    logger.info(f"There are currently {number_of_agents} agents available...")
    if number_of_agents < 1:
        logger.info("No agents available to run pipeline.")
        await msg.nak()
        return

    await msg.ack()


async def consume_messages(
    psub: JetStreamContext.PullSubscription,
    handler: Callable[[NATSMsg, JetStreamContext], Awaitable],
    js: JetStreamContext,
):
    while True:
        msgs = await psub.fetch(1, timeout=None)
        for msg in msgs:
            await handler(msg, js)


async def watch_for_agents(
    js: JetStreamContext,
):
    bucket = await js.create_key_value(KeyValueConfig(bucket=BUCKET_AGENTS, ttl=30))

    while True:
        try:
            _ = await bucket.keys()
        except NoKeysError:
            logger.info("No keys right now...")
            await asyncio.sleep(0.1)
            continue

        await asyncio.sleep(1)

async def get_current_num_agents(js: JetStreamContext):
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        num_agents = len(await bucket.keys())
    except NoKeysError:
        return 0
    return num_agents


async def create_agent(js: JetStreamContext):
    while True:
        try:
            bucket = await js.key_value(BUCKET_AGENTS)
        except BucketNotFoundError:
            continue
        break

    agent_uuids = [uuid4() for _ in range(2)]
    while True:
        futures = [
            bucket.put(f"agent-{uuid}", bytes(f"agent-{uuid}", "utf-8"))
            for uuid in agent_uuids
        ]
        await asyncio.gather(*futures)
        await asyncio.sleep(10)


async def main():
    id: str = str(uuid4())
    nc: NATSClient = await nats.connect(
        servers=[DEFAULT_NATS_ADDRESS], name=f"orchestrator-{id}"
    )
    js: JetStreamContext = nc.jetstream()

    logger.info("Orchestrator is running...")
    consumer_cfg = ConsumerConfig(
        description=f"orchestrator-{id}", deliver_policy=DeliverPolicy.LAST_PER_SUBJECT
    )
    pipeline_run_psub = await js.pull_subscribe(
        subject=SUBJECT_PIPELINES_RUN, config=consumer_cfg
    )
    await asyncio.gather(
        consume_messages(pipeline_run_psub, handle_run_pipeline, js),
        watch_for_agents(js),
        create_agent(js),
    )

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
