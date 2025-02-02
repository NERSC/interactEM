import asyncio
import contextlib
import json
import signal
from pprint import pformat

import nats
import nats.micro
from jinja2 import Environment, PackageLoader
from nats.micro.request import Request
from nats.micro.service import EndpointConfig, GroupConfig, Service, ServiceConfig
from pydantic import ValidationError
from sfapi_client._models import StatusValue
from sfapi_client.client import AsyncClient as SFApiClient
from sfapi_client.compute import Machine
from sfapi_client.exceptions import SfApiError
from sfapi_client.jobs import AsyncJobSqueue

from interactem.core.constants import (
    SFAPI_GROUP_NAME,
    SFAPI_SERVICE_NAME,
    SFAPI_STATUS_ENDPOINT,
    SFAPI_SUBMIT_ENDPOINT,
)
from interactem.core.logger import get_logger
from interactem.core.nats import nc
from interactem.launcher.models import (
    JobSubmitRequest,
    JobSubmitResponse,
    StatusRequest,
    StatusResponse,
)

from .config import cfg
from .constants import LAUNCH_AGENT_TEMPLATE

logger = get_logger()

sfapi_client = SFApiClient(key=cfg.SFAPI_KEY_PATH)
jinja_env = Environment(loader=PackageLoader("interactem.launcher"), enable_async=True)


async def status(req: Request) -> None:
    logger.info("Received status request")
    try:
        status_req = StatusRequest.model_validate_json(req.data)
    except Exception as e:
        logger.error(f"Failed to parse machine type: {e}")
        await req.respond_error(
            code="400",
            description=f"Invalid machine type: {e}, choices are {[t.value for t in Machine]}",
        )
    try:
        perlmutter = await sfapi_client.compute(status_req.machine)
        await req.respond(perlmutter.status.encode())
    except SfApiError as e:
        logger.error(f"Failed to get status: {e}")
        await req.respond_error(code="500", description=e.message)


async def submit(req: Request) -> None:
    logger.info("Received job submission request")
    try:
        job_req = JobSubmitRequest.model_validate_json(req.data)
    except ValidationError as e:
        logger.error(f"Failed to parse job request: {e}")
        await req.respond_error(code="400", description=f"Invalid job request: {e}")
        return

    perlmutter = await sfapi_client.compute(job_req.machine)

    if perlmutter.status != StatusValue.active:
        logger.error(f"Machine is not active: {perlmutter.status}")
        await req.respond_error(
            code="500", description=f"Machine is not active: {perlmutter.status}"
        )
        return

    # Render job script
    template = jinja_env.get_template(LAUNCH_AGENT_TEMPLATE)
    script = await template.render_async(
        job=job_req.model_dump(), settings=cfg.model_dump()
    )

    try:
        job: AsyncJobSqueue = await perlmutter.submit_job(script)
        logger.info(f"Job {job.jobid} submitted")
        logger.info(f"Script: \n{script}")
        await req.respond(
            data=JobSubmitResponse(jobid=int(job.jobid)).model_dump().encode()
        )
    except SfApiError as e:
        logger.error(f"Failed to submit job: {e}")
        await req.respond_error(code="500", description=e.message)


# taken from
# https://github.com/nats-io/nats.py/blob/main/examples/micro/service.py
async def main():
    quit_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
        loop.add_signal_handler(sig, lambda *_: quit_event.set())

    async with contextlib.AsyncExitStack() as stack:
        nats_client = await stack.enter_async_context(
            await nc(servers=[str(cfg.NATS_SERVER_URL)], name="sfapi-launcher")
        )

        config = ServiceConfig(
            name=SFAPI_SERVICE_NAME,
            version="0.0.1",
            description="A service for interacting with the SFAPI",
            metadata={},
            queue_group=None,
        )

        service: Service = await stack.enter_async_context(
            await nats.micro.add_service(nats_client, config=config)
        )

        sfapi_group = service.add_group(
            config=GroupConfig(
                name=SFAPI_GROUP_NAME,
                queue_group=None,
            )
        )

        await sfapi_group.add_endpoint(
            config=EndpointConfig(
                name=SFAPI_SUBMIT_ENDPOINT,
                handler=submit,
                metadata={
                    "request_schema": json.dumps(JobSubmitRequest.model_json_schema()),
                    "response_schema": json.dumps(
                        JobSubmitResponse.model_json_schema()
                    ),
                },
            )
        )

        await sfapi_group.add_endpoint(
            config=EndpointConfig(
                name=SFAPI_STATUS_ENDPOINT,
                handler=status,
                metadata={
                    "request_schema": json.dumps(StatusRequest.model_json_schema()),
                    "response_schema": json.dumps(StatusResponse.model_json_schema()),
                },
            )
        )

        logger.info("SFAPI service is running...")
        logger.info(f"Service Info:\n{pformat(service.info(), depth=3)}")
        # Wait for the quit event
        await quit_event.wait()
        await sfapi_client.close()
