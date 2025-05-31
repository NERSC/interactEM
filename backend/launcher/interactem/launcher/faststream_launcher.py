import asyncio
from contextlib import asynccontextmanager

from faststream import Context, ContextRepo, Depends, FastStream
from faststream.nats import NatsMessage
from jinja2 import Environment, PackageLoader
from sfapi_client.client import AsyncClient as SFApiClient
from sfapi_client.exceptions import SfApiError

from interactem.core.constants import (
    SUBJECT_NOTIFICATIONS_ERRORS,
    SUBJECT_SFAPI_JOBS_SUBMIT,
)
from interactem.core.faststream import create_nats_broker
from interactem.core.logger import get_logger
from interactem.sfapi_models import (
    AgentCreateEvent,
    StatusRequest,
    StatusResponse,
)

from .config import cfg
from .job_handler import JobHandler

logger = get_logger()




async def progress_sender(message: NatsMessage):
    async def in_progress_task():
        while True:
            await asyncio.sleep(10.0)
            await message.in_progress()

    task = asyncio.create_task(in_progress_task())
    yield
    task.cancel()



@asynccontextmanager
async def lifespan(context: ContextRepo):
    """Application lifespan management."""
    logger.info("Starting FastStream Launcher Service")
    jinja_env = Environment(loader=PackageLoader("interactem.launcher"), enable_async=True)
    async with SFApiClient(key=cfg.SFAPI_KEY_PATH) as sfapi_client:
        job_handler = JobHandler(sfapi_client, jinja_env, cfg)
        context.set_global("sfapi_client", sfapi_client)
        context.set_global("job_handler", job_handler)
        yield
    logger.info("Shutting down FastStream Launcher Service")

# Create FastStream app
broker = create_nats_broker(servers=[str(cfg.NATS_SERVER_URL)])
app = FastStream(broker=broker, lifespan=lifespan)

@broker.subscriber(
    "sfapi.status",
    # FastStream handles request/reply pattern automatically
)
async def handle_status_request(
    request: StatusRequest,
    sfapi_client: SFApiClient = Context()
) -> StatusResponse:
    """Handle machine status requests."""
    logger.info(f"Received status request for {request.machine}")

    try:
        compute = await sfapi_client.compute(request.machine)
        return StatusResponse(status=compute.status)
    except SfApiError as e:
        logger.error(f"Failed to get status: {e}")
        raise  # FastStream will handle error response

@broker.subscriber(SUBJECT_SFAPI_JOBS_SUBMIT, dependencies=[Depends(progress_sender)])
async def handle_job_submission(
    message: AgentCreateEvent,
    job_handler: JobHandler = Context(),
) -> None:
    """Handle job submission requests."""
    logger.info("Received job submission request")

    try:
        await job_handler.submit_job(message)
    except Exception as e:
        logger.error(f"Job submission failed: {e}")
        # Publish error notification
        await broker.publish(
            str(e),
            subject=SUBJECT_NOTIFICATIONS_ERRORS
        )
        raise  # Let FastStream handle retry logic
