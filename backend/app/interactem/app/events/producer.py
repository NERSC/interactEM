import asyncio
import logging

from fastapi import HTTPException
from nats.aio.msg import Msg as NatsMessage
from nats.errors import NoRespondersError as NatsNoRespondersError
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import StreamInfo
from nats.js.errors import APIError, NoStreamResponseError
from pydantic import BaseModel
from sqlmodel import SQLModel

from interactem.core.constants import (
    SFAPI_GROUP_NAME,
    SFAPI_STATUS_ENDPOINT,
    STREAM_PIPELINES,
    STREAM_SFAPI,
    SUBJECT_PIPELINES_RUN,
    SUBJECT_PIPELINES_STOP,
    SUBJECT_SFAPI_JOBS_SUBMIT,
)
from interactem.core.events.pipelines import PipelineRunEvent, PipelineStopEvent
from interactem.core.nats import create_or_update_stream, nc
from interactem.core.nats.config import PIPELINES_STREAM_CONFIG, SFAPI_STREAM_CONFIG
from interactem.sfapi_models import AgentCreateEvent, StatusRequest

from ..core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

nats_tasks: list[asyncio.Task] = []

NATS_REQ_TIMEOUT_DEFAULT = 5
NATS_REQ_TIMEOUT_SFAPI = 10


async def start():
    global nats_client
    global nats_jetstream
    logger.info(f"Connecting to NATS server: {settings.NATS_SERVER_URL}")
    nats_client = await nc([str(settings.NATS_SERVER_URL)], "api")
    nats_jetstream = nats_client.jetstream()
    stream_infos: list[StreamInfo] = []
    stream_infos.append(
        await create_or_update_stream(PIPELINES_STREAM_CONFIG, nats_jetstream)
    )
    stream_infos.append(
        await create_or_update_stream(SFAPI_STREAM_CONFIG, nats_jetstream)
    )
    logger.info(f"Streams information:\n {stream_infos}")


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
    except NoStreamResponseError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to publish event on stream: {stream}. \nNats error: {e}.",
        )
    except APIError as e:
        if not e.code:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=e.code, detail=str(e))


async def nats_req_rep(
    subject: str,
    payload: BaseModel | SQLModel,
    timeout: int = NATS_REQ_TIMEOUT_DEFAULT,
) -> NatsMessage:
    try:
        rep: NatsMessage = await nats_client.request(
            subject=subject,
            payload=payload.model_dump_json().encode(),
            headers=None,
            timeout=timeout,
        )
    except NatsNoRespondersError as e:
        raise HTTPException(
            status_code=503,
            detail=f"No responders found for subject: {subject}. Nats error: {e}.",
        )
    except NatsTimeoutError as e:
        logger.exception(f"Timeout for subject: {subject}")
        raise HTTPException(
            status_code=504,
            detail=f"Timeout for subject: {subject}. Nats error: {e}.",
        )

    return rep


async def publish_pipeline_run_event(event: PipelineRunEvent) -> None:
    await publish_jetstream_event(STREAM_PIPELINES, SUBJECT_PIPELINES_RUN, event)

async def publish_pipeline_stop_event(event: PipelineStopEvent) -> None:
    await publish_jetstream_event(STREAM_PIPELINES, SUBJECT_PIPELINES_STOP, event)


async def request_machine_status(payload: StatusRequest) -> NatsMessage:
    return await nats_req_rep(
        f"{SFAPI_GROUP_NAME}.{SFAPI_STATUS_ENDPOINT}",
        payload,
        timeout=NATS_REQ_TIMEOUT_SFAPI,  # longer timeout for sfapi calls
    )

async def publish_sfapi_submit_event(event: AgentCreateEvent) -> None:
    await publish_jetstream_event(STREAM_SFAPI, SUBJECT_SFAPI_JOBS_SUBMIT, event)
