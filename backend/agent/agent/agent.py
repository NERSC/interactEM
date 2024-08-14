import asyncio
import uuid
from uuid import uuid4

import nats
from core.constants import BUCKET_AGENTS
from core.logger import get_logger
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import BucketNotFoundError

logger = get_logger("orchestrator", "DEBUG")

DEFAULT_NATS_ADDRESS: str = "nats://nats1:4222"


async def agent_updater(js: JetStreamContext, id: uuid.UUID):
    while True:
        try:
            bucket = await js.key_value(BUCKET_AGENTS)
        except BucketNotFoundError:
            continue
        break

    while True:
        await bucket.put(f"agent-{id}", bytes(f"agent-{id}", "utf-8"))
        await asyncio.sleep(10)


async def main():
    id: uuid.UUID = uuid4()
    nc: NATSClient = await nats.connect(
        servers=[DEFAULT_NATS_ADDRESS], name=f"orchestrator-{id}"
    )
    js: JetStreamContext = nc.jetstream()
    logger.info(f"Agent {id} is running...")
    await asyncio.gather(agent_updater(js, id))
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
