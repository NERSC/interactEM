import logging

from pydantic import BaseModel
from sqlmodel import SQLModel

from interactem.core.constants import STREAM_PIPELINES, SUBJECT_PIPELINES_RUN
from interactem.core.events.pipelines import PipelineRunEvent
from interactem.core.nats import create_or_update_stream, nc
from interactem.core.nats.config import PIPELINES_STREAM_CONFIG

from ..core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start():
    global nats_client
    global nats_jetstream
    logger.info(f"Connecting to NATS server: {settings.NATS_SERVER_URL}")
    nats_client = await nc([str(settings.NATS_SERVER_URL)], "api")
    nats_jetstream = nats_client.jetstream()
    info = await create_or_update_stream(PIPELINES_STREAM_CONFIG, nats_jetstream)
    logger.info(f"Stream information: {info}")


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
