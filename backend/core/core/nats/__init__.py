from typing import Awaitable, Callable
from core.constants import BUCKET_AGENTS, BUCKET_AGENTS_TTL
from core.models.agent import AgentVal
from nats.js import JetStreamContext
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError, KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue
from nats.aio.msg import Msg as NATSMsg
from nats.js.api import ConsumerConfig, DeliverPolicy, StreamConfig, StreamInfo
from nats.js.errors import BadRequestError

from core.logger import get_logger

logger = get_logger("core.nats", "DEBUG")


async def create_bucket_if_doesnt_exist(
    js: JetStreamContext, bucket_name: str, ttl: int
) -> KeyValue:
    try:
        kv = await js.key_value(bucket_name)
    except BucketNotFoundError:
        bucket_cfg = KeyValueConfig(bucket=bucket_name, ttl=ttl)
        kv = await js.create_key_value(config=bucket_cfg)
    return kv


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


async def get_current_num_agents(js: JetStreamContext):
    try:
        bucket = await js.key_value(BUCKET_AGENTS)
    except BucketNotFoundError:
        bucket_cfg = KeyValueConfig(bucket=BUCKET_AGENTS, ttl=BUCKET_AGENTS_TTL)
        bucket = await js.create_key_value(config=bucket_cfg)
    try:
        num_agents = len(await bucket.keys())
    except NoKeysError:
        return 0
    return num_agents


async def consume_messages(
    psub: JetStreamContext.PullSubscription,
    handler: Callable[[NATSMsg, JetStreamContext], Awaitable],
    js: JetStreamContext,
):
    while True:
        msgs = await psub.fetch(1, timeout=None)
        for msg in msgs:
            await handler(msg, js)


async def create_or_update_stream(
    cfg: StreamConfig, js: JetStreamContext
) -> StreamInfo:
    updated = False
    try:
        stream_info = await js.add_stream(config=cfg)
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            updated = True
            stream_info = await js.update_stream(config=cfg)
        else:
            raise
    finally:
        if updated:
            logger.info(f"Updated stream {cfg.name}. Description: {cfg.description}")
        else:
            logger.info(f"Created stream {cfg.name}. Description: {cfg.description}")
        return stream_info
