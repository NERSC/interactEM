import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, StreamConfig
from pydantic import ValidationError

from zmglue.logger import get_logger
from zmglue.models import CommBackend, URILocation
from zmglue.models.messages import NewPipelineMessage
from zmglue.models.uri import URI

logger = get_logger("orchestrator", "DEBUG")

DEFAULT_NATS_ADDRESS: str = "nats://localhost:4222"
DEFAULT_ORCHESTRATOR_URI = URI(
    id=uuid4(),
    hostname="localhost",
    location=URILocation.orchestrator,
    comm_backend=CommBackend.NATS,
    query={"address": [DEFAULT_NATS_ADDRESS]},
)

PIPELINES_SUBJECT = "pipelines"

PIPELINES_STREAM_CONFIG = StreamConfig(
    name="pipelines", subjects=["pipelines.>"], max_bytes=1024 * 1024 * 1024
)

AGENTS_STREAM_CONFIG = StreamConfig(
    name="agents", subjects=["agents.>"], max_bytes=1024 * 1024 * 1024
)


async def handle_new_pipeline(msg: NATSMsg, js: JetStreamContext):
    try:
        msg_ = NewPipelineMessage.model_validate_json(msg.data)
        logger.info(f"Received and validated message: {msg_}")
    except ValidationError:
        logger.error("Invalid message")
        await msg.ack()
        return

    # Process the message and publish another message
    new_subject = "agents.processed"
    new_message = {"status": "processed", "pipeline_id": str(msg_.id)}
    await js.publish(new_subject, str(new_message).encode())

    await msg.ack()


async def handle_different_thing(msg: NATSMsg, js: JetStreamContext):
    # Placeholder for actual message handling logic
    logger.info(f"Handling different message: {msg.data}")
    await msg.ack()


async def consume_messages(
    psub: JetStreamContext.PullSubscription,
    handler: Callable[[NATSMsg, JetStreamContext], Awaitable],
    js: JetStreamContext,
):
    while True:
        msgs = await psub.fetch(1)  # Fetch 1 message at a time, adjust as needed
        for msg in msgs:
            await handler(msg, js)


async def main():
    nc: NATSClient = await nats.connect(DEFAULT_NATS_ADDRESS)
    js: JetStreamContext = nc.jetstream()
    await js.add_stream(PIPELINES_STREAM_CONFIG)
    await js.add_stream(AGENTS_STREAM_CONFIG)

    logger.info("Orchestrator is running...")

    pipelines_psub = await js.pull_subscribe(
        "pipelines.new", config=ConsumerConfig(durable_name="pipelines")
    )
    agents_psub = await js.pull_subscribe(
        "agents.new", config=ConsumerConfig(durable_name="agents")
    )

    await asyncio.gather(
        consume_messages(pipelines_psub, handle_new_pipeline, js),
        consume_messages(agents_psub, handle_different_thing, js),
    )

    # Keep the connection alive
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
