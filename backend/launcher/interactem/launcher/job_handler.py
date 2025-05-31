"""Job handling logic extracted from main launcher."""

import asyncio

from jinja2 import Environment
from sfapi_client._models import StatusValue
from sfapi_client.client import AsyncClient as SFApiClient
from sfapi_client.exceptions import SfApiError
from sfapi_client.jobs import AsyncJobSqueue
from sfapi_client.paths import AsyncRemotePath

from interactem.core.logger import get_logger
from interactem.sfapi_models import AgentCreateEvent, JobSubmitEvent

from .config import Settings
from .constants import LAUNCH_AGENT_TEMPLATE

logger = get_logger()

class JobHandler:
    """Handles job submission and monitoring logic."""

    def __init__(
        self,
        sfapi_client: "SFApiClient",
        jinja_env: "Environment",
        config: "Settings"
    ):
        self.sfapi_client = sfapi_client
        self.jinja_env = jinja_env
        self.config = config

    async def submit_job(self, agent_event: AgentCreateEvent) -> None:
        """Submit and monitor a job."""
        # Convert to JobSubmitEvent
        reservation = None
        if agent_event.extra:
            reservation = agent_event.extra.get("reservation")

        job_submit_event = JobSubmitEvent(
            machine=agent_event.machine,
            account=self.config.SFAPI_ACCOUNT,
            qos=self.config.SFAPI_QOS,
            constraint=agent_event.compute_type.value,
            walltime=agent_event.duration,
            reservation=reservation,
            num_nodes=agent_event.num_nodes,
        )

        # Validate compute availability
        compute = await self.sfapi_client.compute(job_submit_event.machine)
        if compute.status != StatusValue.active:
            raise ValueError(f"{job_submit_event.machine.value} is not active: {compute.status}")

        # Check environment file
        try:
            remote_path = AsyncRemotePath(path=self.config.ENV_FILE_PATH, compute=compute)
            await remote_path.update()
        except (SfApiError, FileNotFoundError):
            raise ValueError("Failed to find .env file for agent startup")

        # Render job script
        template = self.jinja_env.get_template(LAUNCH_AGENT_TEMPLATE)
        script = await template.render_async(
            job=job_submit_event.model_dump(),
            settings=self.config.model_dump()
        )

        # Submit job
        job: AsyncJobSqueue = await compute.submit_job(script)
        logger.info(f"Job {job.jobid} submitted")
        logger.info(f"Script: \n{script}")

        # Start monitoring in background
        asyncio.create_task(self._monitor_job(job))

    async def _monitor_job(self, job: AsyncJobSqueue) -> None:
        """Monitor job lifecycle."""
        logger.info(f"Job {job.jobid} has been submitted to SFAPI. Waiting for it to run...")

        try:
            await job.running()
        except SfApiError as e:
            logger.error(f"SFAPI Error: {e.message}")
            return

        await job.complete()
        logger.info(f"Job {job.jobid} has completed. Job state: {job.state}")
