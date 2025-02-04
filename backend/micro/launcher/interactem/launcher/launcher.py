import asyncio
import contextlib
import json
import signal
from pprint import pformat

import nats
import nats.micro
from jinja2 import Environment, PackageLoader
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
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
    SUBJECT_NOTIFICATIONS_ERRORS,
    SUBJECT_NOTIFICATIONS_INFO,
)
from interactem.core.logger import get_logger
from interactem.core.nats import consume_messages, create_or_update_stream, nc
from interactem.core.nats.config import NOTIFICATIONS_STREAM_CONFIG, SFAPI_STREAM_CONFIG
from interactem.core.nats.consumers import create_sfapi_submit_consumer
from interactem.core.util import create_task_with_ref
from interactem.sfapi_models import (
    AgentCreateEvent,
    JobSubmitEvent,
    StatusRequest,
    StatusResponse,
)

from .config import cfg
from .constants import LAUNCH_AGENT_TEMPLATE

logger = get_logger()

sfapi_client = SFApiClient(key=cfg.SFAPI_KEY_PATH)
jinja_env = Environment(loader=PackageLoader("interactem.launcher"), enable_async=True)

task_refs: set[asyncio.Task] = set()


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
        logger.info(f"Status request completed, responded with: {perlmutter.status}")
    except SfApiError as e:
        logger.error(f"Failed to get status: {e}")
        await req.respond_error(code="500", description=e.message)


def publish_error(js: JetStreamContext, msg: str) -> None:
    create_task_with_ref(
        task_refs,
        js.publish(
            f"{SUBJECT_NOTIFICATIONS_ERRORS}",
            payload=msg.encode(),
        ),
    )


def publish_notification(js: JetStreamContext, msg: str) -> None:
    create_task_with_ref(
        task_refs,
        js.publish(
            f"{SUBJECT_NOTIFICATIONS_INFO}",
            payload=msg.encode(),
        ),
    )


async def monitor_job(job: AsyncJobSqueue, js: JetStreamContext) -> None:
    msg = f"Job {job.jobid} has been submitted to SFAPI. Waiting for it to run..."
    logger.info(msg)
    publish_notification(js, msg)

    try:
        await job.running()
    except SfApiError as e:
        # Occurs when the job goes into terminal state. The state is updated in the job object
        # here, so we can publish its state directly
        logger.error(f"SFAPI Error: {e.message}.")
        publish_error(js, e.message)
        return

    await job.complete()
    msg = f"Job {job.jobid} has completed. Job state: {job.state}."
    logger.info(msg)
    publish_notification(js, msg)


async def submit(msg: NATSMsg, js: JetStreamContext) -> None:
    logger.info("Received job submission request")
    # Before we get into job submission, we want to let the server
    # know that we are working on it
    create_task_with_ref(task_refs, msg.in_progress())
    try:
        agent_event = AgentCreateEvent.model_validate_json(msg.data)

        # Convert to JobSubmitEvent because we want to limit the frontend
        # to not knowing what a job is...
        job_submit_event = JobSubmitEvent(
            machine=agent_event.machine,
            account=cfg.SFAPI_ACCOUNT,
            qos=cfg.SFAPI_QOS,
            constraint=agent_event.compute_type.value,
            walltime=agent_event.duration,
            reservation=agent_event.reservation,
            num_nodes=agent_event.num_agents,
        )
    except ValidationError as e:
        logger.error(f"Failed to parse job request: {e}")
        create_task_with_ref(task_refs, msg.term())
        return

    compute = await sfapi_client.compute(job_submit_event.machine)

    if compute.status != StatusValue.active:
        logger.error(f"Machine is not active: {compute.status}")
        create_task_with_ref(task_refs, msg.term())
        return

    # Render job script
    template = jinja_env.get_template(LAUNCH_AGENT_TEMPLATE)
    script = await template.render_async(
        job=job_submit_event.model_dump(), settings=cfg.model_dump()
    )

    create_task_with_ref(task_refs, msg.in_progress())
    try:
        job: AsyncJobSqueue = await compute.submit_job(script)
        logger.info(f"Job {job.jobid} submitted")
        logger.info(f"Script: \n{script}")
        create_task_with_ref(task_refs, msg.ack())
        create_task_with_ref(task_refs, monitor_job(job, js))
    except SfApiError as e:
        _msg = f"Failed to submit job: {e.message}"
        logger.error(_msg)
        publish_error(js, _msg)
        create_task_with_ref(task_refs, msg.term())


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
        js: JetStreamContext = nats_client.jetstream()

        startup_tasks: list[asyncio.Task] = []
        startup_tasks.append(
            asyncio.create_task(create_or_update_stream(SFAPI_STREAM_CONFIG, js))
        )
        startup_tasks.append(
            asyncio.create_task(
                create_or_update_stream(NOTIFICATIONS_STREAM_CONFIG, js)
            )
        )
        await asyncio.gather(*startup_tasks)

        config = ServiceConfig(
            name=SFAPI_SERVICE_NAME,
            version="0.0.1",
            description="A service for getting SFAPI status.",
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

        sfapi_submit_psub = await create_sfapi_submit_consumer(js)
        submit_task = asyncio.create_task(
            consume_messages(sfapi_submit_psub, submit, js)
        )
        # Wait for the quit event
        await quit_event.wait()
        submit_task.cancel()
        await sfapi_client.close()
