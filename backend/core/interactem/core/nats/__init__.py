import asyncio
from typing import Awaitable, Callable, Set

from interactem.core.util import create_task_with_ref
import nats

from interactem.core.constants import (
    BUCKET_METRICS,
    BUCKET_METRICS_TTL,
    BUCKET_STATUS,
    BUCKET_STATUS_TTL,
    SUBJECT_NOTIFICATIONS_ERRORS,
    SUBJECT_NOTIFICATIONS_INFO,
)
from nats.js import JetStreamContext
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError, KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue
from nats.aio.msg import Msg as NATSMsg
from nats.aio.client import Client as NATSClient
from nats.js.api import StreamConfig, StreamInfo
from nats.js.errors import BadRequestError
from typing import TypeVar, Type
from pydantic import BaseModel, ValidationError
from nats.js.kv import KeyValue
from nats.js.errors import KeyNotFoundError

from interactem.core.logger import get_logger
from interactem.core.config import cfg
from .config import (
    SFAPI_STREAM_CONFIG,
    DEPLOYMENTS_STREAM_CONFIG,
    IMAGES_STREAM_CONFIG,
    NOTIFICATIONS_STREAM_CONFIG,
    PARAMETERS_STREAM_CONFIG,
    TABLE_STREAM_CONFIG,
    METRICS_STREAM_CONFIG,
)

ValType = TypeVar("ValType", bound=BaseModel)
logger = get_logger()


async def nc(servers: list[str], name: str) -> NATSClient:
    options_map = {
        cfg.NATS_SECURITY_MODE.NKEYS: {
            "nkeys_seed_str": cfg.NKEYS_SEED_STR,
        },
        cfg.NATS_SECURITY_MODE.CREDS: {
            "user_credentials": str(cfg.NATS_CREDS_FILE),
        },
    }
    options = options_map[cfg.NATS_SECURITY_MODE]

    async def disconnected_cb():
        logger.info(f"NATS disconnected.")

    async def reconnected_cb():
        logger.info(f"NATS reconnected.")

    async def closed_cb():
        logger.info(f"NATS connection closed.")

    return await nats.connect(
        servers=servers,
        name=name,
        reconnected_cb=reconnected_cb,
        disconnected_cb=disconnected_cb,
        closed_cb=closed_cb,
        **options,
    )


async def create_bucket_if_doesnt_exist(
    js: JetStreamContext, bucket_name: str, ttl: int
) -> KeyValue:
    try:
        kv = await js.key_value(bucket_name)
    except BucketNotFoundError:
        bucket_cfg = KeyValueConfig(bucket=bucket_name, ttl=ttl)
        kv = await js.create_key_value(config=bucket_cfg)
    return kv


async def get_status_bucket(js: JetStreamContext) -> KeyValue:
    return await create_bucket_if_doesnt_exist(js, BUCKET_STATUS, BUCKET_STATUS_TTL)


async def get_metrics_bucket(js: JetStreamContext) -> KeyValue:
    return await create_bucket_if_doesnt_exist(js, BUCKET_METRICS, BUCKET_METRICS_TTL)


async def get_keys(bucket: KeyValue, filters: list[str] = []) -> list[str]:
    try:
        keys = await bucket.keys(filters=filters)
    except NoKeysError:
        return []
    return keys


async def get_val(
    bucket: KeyValue, key: str, pydantic_cls: Type[ValType]
) -> ValType | None:
    try:
        entry = await bucket.get(key)
        if not entry.value:
            logger.warning(f"Key {key} has no value in bucket for {pydantic_cls}...")
            return None
        try:
            return pydantic_cls.model_validate_json(entry.value)
        except ValidationError:
            logger.warning(
                f"Key {key} has invalid value in bucket for {pydantic_cls}..."
            )
            return None
    except KeyNotFoundError:
        logger.warning(f"Key {key} not found in bucket for {pydantic_cls}...")
        return None


async def consume_messages(
    psub: JetStreamContext.PullSubscription,
    handler: Callable[[NATSMsg, JetStreamContext], Awaitable],
    js: JetStreamContext,
    num_msgs: int = 1,
):
    logger.info(f"Consuming messages on pull subscription {await psub.consumer_info()}")
    handler_tasks: set[asyncio.Task] = set()
    while True:
        msgs = await psub.fetch(num_msgs, timeout=None)
        for msg in msgs:
            create_task_with_ref(handler_tasks, handler(msg, js))


async def create_or_update_stream(
    cfg: StreamConfig, js: JetStreamContext
) -> StreamInfo:
    stream_info: StreamInfo | None = None
    try:
        stream_info = await js.add_stream(config=cfg)
        logger.info(f"Created stream {cfg.name}. Description: {cfg.description}")
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            try:
                stream_info = await js.update_stream(config=cfg)
                logger.info(
                    f"Updated stream {cfg.name}. Description: {cfg.description}"
                )
            except Exception as update_err:
                logger.error(f"Failed to update stream {cfg.name}: {update_err}")
                raise update_err
        else:
            logger.error(f"Failed to add stream {cfg.name}: {e}")
            raise
    except Exception as add_err:
        logger.error(
            f"An unexpected error occurred while adding stream {cfg.name}: {add_err}"
        )
        raise add_err

    if stream_info is None:
        # This case should ideally not be reached if exceptions are handled correctly above.
        raise RuntimeError(f"Stream info could not be obtained for stream {cfg.name}")

    return stream_info

async def create_all_streams(js: JetStreamContext) -> list[StreamInfo]:
    stream_infos: list[StreamInfo] = []
    tasks: set[asyncio.Task] = set()
    create_task_with_ref(
        tasks,
        create_or_update_stream(DEPLOYMENTS_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(SFAPI_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(TABLE_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(IMAGES_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(PARAMETERS_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(NOTIFICATIONS_STREAM_CONFIG, js),
    )
    create_task_with_ref(
        tasks,
        create_or_update_stream(METRICS_STREAM_CONFIG, js),
    )
    try:
        stream_infos = await asyncio.gather(*tasks)
        logger.info(f"All streams created or updated successfully.")
    except Exception as e:
        logger.error(f"Failed to create or update streams: {e}")
        raise
    return stream_infos


def publish_error(js: JetStreamContext, msg: str, task_refs: Set[asyncio.Task]) -> None:
    create_task_with_ref(
        task_refs,
        js.publish(
            f"{SUBJECT_NOTIFICATIONS_ERRORS}",
            payload=msg.encode(),
        ),
    )


def publish_notification(
    js: JetStreamContext, msg: str, task_refs: Set[asyncio.Task]
) -> None:
    create_task_with_ref(
        task_refs,
        js.publish(
            f"{SUBJECT_NOTIFICATIONS_INFO}",
            payload=msg.encode(),
        ),
    )
