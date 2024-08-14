from pathlib import Path
from uuid import UUID

import nats
import nats.micro
from nats.js.api import StreamConfig

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import CommBackend, URILocation
from zmglue.models.uri import URI

logger = get_logger("agent", "DEBUG")

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
DEFAULT_AGENT_URI = URI(
    id=UUID("583cd5b3-c94d-4644-8be7-dbd4f0570e91"),
    comm_backend=CommBackend.ZMQ,
    location=URILocation.agent,
    query={
        "address": [
            f"tcp://?hostname=localhost&interface={cfg.AGENT_INTERFACE}&port={cfg.AGENT_PORT}"
        ]
    },  # type: ignore
    hostname="localhost",
)


PIPELINES_STREAM_CONFIG = StreamConfig(
    name="pipelines", subjects=["pipelines.>"], max_bytes=1024 * 1024 * 1024
)

DEFAULT_NATS_ADDRESS: str = "nats://localhost:4222"


async def main():
    nc = await nats.connect("localhost")

    # Create JetStream context.
    js = nc.jetstream()
    await js.add_stream(PIPELINES_STREAM_CONFIG)

    for i in range(0, 10):
        ack = await js.publish("foo", f"hello world: {i}".encode())
        print(ack)

    # Create pull based consumer on 'foo'.
    psub = await js.pull_subscribe("foo", "psub")

    # Fetch and ack messagess from consumer.
    for _ in range(0, 10):
        msgs = await psub.fetch(1)
        for msg in msgs:
            print(msg)

    # Create single ephemeral push based subscriber.
    sub = await js.subscribe("foo")
    msg = await sub.next_msg()
    await msg.ack()

    # Create single push based subscriber that is durable across restarts.
    sub = await js.subscribe("foo", durable="myapp")
    msg = await sub.next_msg()
    await msg.ack()

    # Create deliver group that will be have load balanced messages.
    async def qsub_a(msg):
        print("QSUB A:", msg)
        await msg.ack()

    async def qsub_b(msg):
        print("QSUB B:", msg)
        await msg.ack()

    await js.subscribe("foo", "workers", cb=qsub_a)
    await js.subscribe("foo", "workers", cb=qsub_b)

    for i in range(0, 10):
        ack = await js.publish("foo", f"hello world: {i}".encode())
        print("\t", ack)

    # Create ordered consumer with flow control and heartbeats
    # that auto resumes on failures.
    osub = await js.subscribe("foo", ordered_consumer=True)
    data = bytearray()

    while True:
        try:
            msg = await osub.next_msg()
            data.extend(msg.data)
        except TimeoutError:
            break
    print("All data in stream:", len(data))

    await nc.close()
