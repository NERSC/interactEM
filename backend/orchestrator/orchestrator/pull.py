import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import nats
import nats.js
import nats.js.errors
from core.constants import (
    BUCKET_AGENTS,
    BUCKET_AGENTS_TTL,
    DEFAULT_NATS_ADDRESS,
    SUBJECT_PIPELINES_RUN,
)
from core.events.pipelines import PipelineRunEvent
from core.logger import get_logger
from core.pipeline import Pipeline, PipelineJSON
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.errors import NoKeysError
from pydantic import ValidationError

logger = get_logger("orchestrator", "DEBUG")


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
    agents = await get_agents(js)
    logger.info(f"There are currently {number_of_agents} agent(s) available...")
    logger.info(f"Agents: {agents}")
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


async def get_current_num_agents(js: JetStreamContext):
    try:
        bucket = await js.key_value(BUCKET_AGENTS)
    except nats.js.errors.BucketNotFoundError:
        bucket_cfg = nats.js.api.KeyValueConfig(bucket=BUCKET_AGENTS, ttl=BUCKET_AGENTS_TTL)
        bucket = await js.create_key_value(config=bucket_cfg)
    try:
        num_agents = len(await bucket.keys())
    except NoKeysError:
        return 0
    return num_agents


async def get_agents(js: JetStreamContext):
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        agents = await bucket.keys()
    except NoKeysError:
        return []
    return agents

async def create_bucket_if_doesnt_exist(js: JetStreamContext, bucket_name: str, ttl: int):
    try:
        await js.key_value(bucket_name)
    except nats.js.errors.BucketNotFoundError:
        bucket_cfg = nats.js.api.KeyValueConfig(bucket=bucket_name, ttl=ttl)
        await js.create_key_value(config=bucket_cfg)


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

    await create_bucket_if_doesnt_exist(js, BUCKET_AGENTS, BUCKET_AGENTS_TTL)

    await asyncio.gather(
        consume_messages(pipeline_run_psub, handle_run_pipeline, js),
    )

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
