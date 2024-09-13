import logging

import nats
import nats.errors
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.api import StreamConfig
from nats.js.errors import BadRequestError
from pydantic import BaseModel
from sqlmodel import SQLModel

from core.constants import STREAM_PIPELINES, SUBJECT_PIPELINES_RUN
from core.events.pipelines import PipelineRunEvent

from ..core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


nats_client: NATSClient | None = None
nats_jetstream: JetStreamContext | None = None


async def start():
    global nats_client
    global nats_jetstream
    logger.info(f"Connecting to NATS server: {settings.NATS_SERVER_URL}")
    nats_client = await nats.connect(settings.NATS_SERVER_URL.unicode_string())
    nats_jetstream = nats_client.jetstream()
    pipeline_cfg = StreamConfig(
        name=STREAM_PIPELINES,
        description="A stream for pipeline messages",
        subjects=[f"{STREAM_PIPELINES}.>"],
    )
    try:
        pipeline_stream_info = await nats_jetstream.add_stream(config=pipeline_cfg)
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            pipeline_stream_info = await nats_jetstream.update_stream(
                config=pipeline_cfg
            )
        else:
            raise
    logger.info(f"Stream information: {pipeline_stream_info}")


async def stop():
    if nats_client:
        await nats_client.close()


async def publish_jetstream_event(
    stream: str,
    subject: str,
    event: BaseModel | SQLModel,
) -> None:
    if nats_jetstream is None:
        raise Exception("Producer has not been initialized")

    try:
        await nats_jetstream.publish(
            subject=subject,
            payload=event.model_dump_json().encode(),
            timeout=None,
            stream=stream,
            headers=None,
        )
    except:  # noqa
        logger.exception(f"Exception send on subject: {subject}")


async def publish_pipeline_run_event(event: PipelineRunEvent) -> None:
    await publish_jetstream_event(STREAM_PIPELINES, SUBJECT_PIPELINES_RUN, event)
