import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import nats
import nats.js
import nats.js.errors
from core.constants import (
    BUCKET_AGENTS,
    BUCKET_AGENTS_TTL,
    DEFAULT_COMPOSE_NATS_ADDRESS,
    STREAM_AGENTS,
    SUBJECT_PIPELINES_RUN,
)
from core.events.pipelines import PipelineRunEvent
from core.logger import get_logger
from core.models.agent import AgentVal
from core.pipeline import Pipeline, PipelineJSON
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, StreamConfig
from nats.js.errors import BadRequestError, KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue
from pydantic import ValidationError

logger = get_logger("orchestrator", "DEBUG")


async def handle_run_pipeline(msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline run event...")
    await msg.ack()

    try:
        event = PipelineRunEvent.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        return
    valid_pipeline = PipelineJSON(id=event.id, **event.data)
    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    _ = Pipeline.from_pipeline(valid_pipeline)

    agents = await get_agents(js)
    logger.info(f"There are currently {len(agents)} agent(s) available...")
    logger.info(f"Agents: {agents}")
    if len(agents) < 1:
        logger.info("No agents available to run pipeline.")
        # TODO: publish event to send message back to API that says this won't work
        return

    first_agent_info = await get_agent_info(js, agents[0])
    if not first_agent_info:
        logger.error("Agent info not found.")
        return

    logger.info(f"Assigning pipeline to agent: {first_agent_info.uri.id}")
    logger.info(f"Agent info: {first_agent_info}")
    await js.publish(
        f"{STREAM_AGENTS}.{first_agent_info.uri.id}",
        stream=f"{STREAM_AGENTS}",
        payload=msg.data,
    )

    logger.info("Pipeline run event processed.")


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
        bucket_cfg = nats.js.api.KeyValueConfig(
            bucket=BUCKET_AGENTS, ttl=BUCKET_AGENTS_TTL
        )
        bucket = await js.create_key_value(config=bucket_cfg)
    try:
        num_agents = len(await bucket.keys())
    except NoKeysError:
        return 0
    return num_agents


async def get_agents(js: JetStreamContext) -> list[str]:
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        agents = await bucket.keys()
    except NoKeysError:
        return []
    return agents


async def get_agent_info(js: JetStreamContext, agent_id: str) -> AgentVal | None:
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        entry = await bucket.get(agent_id)
        if not entry.value:
            return
        return AgentVal.model_validate_json(entry.value)
    except KeyNotFoundError:
        return


async def create_bucket_if_doesnt_exist(
    js: JetStreamContext, bucket_name: str, ttl: int
) -> KeyValue:
    try:
        kv = await js.key_value(bucket_name)
    except nats.js.errors.BucketNotFoundError:
        bucket_cfg = nats.js.api.KeyValueConfig(bucket=bucket_name, ttl=ttl)
        kv = await js.create_key_value(config=bucket_cfg)
    return kv


async def main():
    id: str = str(uuid4())
    nc: NATSClient = await nats.connect(
        servers=[DEFAULT_COMPOSE_NATS_ADDRESS], name=f"orchestrator-{id}"
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

    agent_stream_cfg = StreamConfig(
        name=STREAM_AGENTS,
        description="A stream for messages to the agents.",
        subjects=[f"{STREAM_AGENTS}.>"],
    )

    # TODO: make this a util
    try:
        agent_stream_info = await js.add_stream(config=agent_stream_cfg)
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            agent_stream_info = await js.update_stream(config=agent_stream_cfg)
        else:
            raise

    logger.info(f"Created agent stream: {agent_stream_info}")

    await asyncio.gather(
        consume_messages(pipeline_run_psub, handle_run_pipeline, js),
    )

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
