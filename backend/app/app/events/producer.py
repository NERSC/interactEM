import logging

import nats

from ..core.config import settings
from ..models import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


producer = None

SUBJECT_PIPELINES_EVENT = "pipelines"


async def start():
    global producer
    logger.info(f"Connecting to NATS server: {settings.NATS_SERVER_ADDRESS}")
    producer = await nats.connect(settings.NATS_SERVER_ADDRESS.unicode_string())


async def stop():
    if producer:
        await producer.close()


async def publish_pipeline_event(event: Pipeline) -> None:
    if producer is None:
        raise Exception("Producer has not been initialized")

    try:
        await producer.publish(
            SUBJECT_PIPELINES_EVENT, event.model_dump_json().encode()
        )
    except:  # noqa
        logger.exception(f"Exception send on topic: {SUBJECT_PIPELINES_EVENT}")
