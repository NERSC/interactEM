import asyncio.subprocess
import os
import signal
import tempfile
import time
import uuid

import nats
import nats.errors
import podman
import podman.errors
from core.constants import BUCKET_AGENTS, DEFAULT_NATS_ADDRESS
from core.logger import get_logger
from core.models.agent import AgentStatus, AgentVal
from core.models.uri import URI, CommBackend, URILocation
from core.pipeline import Pipeline
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import BucketNotFoundError
from podman.domain.containers import Container
from pydantic import ValidationError

from .config import cfg

# Can use this for mac:
# https://podman-desktop.io/blog/5-things-to-know-for-a-docker-user#docker-compatibility-mode
if cfg.DOCKER_COMPATIBILITY_MODE:
    PODMAN_SERVICE_URI = "unix:///var/run/docker.sock"
else:
    PODMAN_SERVICE_URI = None

# Use configuration, as we always expect to install podman-hpc-client
if cfg.LOCAL:
    from podman import PodmanClient
else:
    from podman_hpc_client import PodmanHpcClient as PodmanClient


logger = get_logger("agent", "DEBUG")


class Agent:
    def __init__(self):
        self.id = uuid.uuid4()
        self.pipeline: Pipeline | None = None
        self.containers: dict[uuid.UUID, Container] = {}

        if PODMAN_SERVICE_URI:
            self._podman_service_uri = PODMAN_SERVICE_URI
        else:
            self._podman_service_dir = tempfile.TemporaryDirectory(
                prefix="core-", ignore_cleanup_errors=True
            )
            self._podman_service_uri = (
                f"unix://{self._podman_service_dir.name}/podman.sock"
            )

        self._shutdown_event = asyncio.Event()
        self.nc: NATSClient | None = None
        self.js: JetStreamContext | None = None
        self.agent_val: AgentVal = AgentVal(
            uri=URI(
                id=self.id,
                location=URILocation.agent,
                hostname="localhost",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.INITIALIZING,
        )
        self.heartbeat_task: asyncio.Task | None = None
        self.server_task: asyncio.Task | None = None

    async def _start_podman_service(self):
        self._podman_process = None
        if not cfg.DOCKER_COMPATIBILITY_MODE:
            args = ["podman", "system", "service", "--time=0", self._podman_service_uri]
            logger.info(f"Starting podman service: {self._podman_service_uri}")

            # We use preexec_fn to create a new process group so that the podman service
            # doesn't get killed when the agent is killed as we needed it to perform
            # cleanup
            self._podman_process = await asyncio.create_subprocess_exec(
                *args, preexec_fn=os.setpgrp
            )

        # Wait for the service to be ready before continuing
        with PodmanClient(base_url=self._podman_service_uri) as client:
            tries = 10
            while tries > 0:
                try:
                    client.version()
                    break
                except podman.errors.exceptions.APIError:
                    logger.debug("Waiting for podman service to start")
                    time.sleep(0.1)
                    tries -= 1

            if tries == 0:
                raise RuntimeError("Podman service didn't successfully start")

            logger.info("Podman service started")

    async def _stop_podman_service(self):
        if self._podman_process is not None:
            logger.info("Stopping podman service")
            self._podman_process.terminate()
            await self._podman_process.wait()

    def _cleanup_containers(self):
        logger.info("Cleaning up containers...")
        with PodmanClient(base_url=self._podman_service_uri) as client:
            for container in client.containers.list(label=f"core.agent.id={self.id}"):
                logger.info(f"Stopping container {container.id}")
                container.stop()
                logger.info(f"Removing container {container.id}")
                container.remove()

    async def run(self):
        await asyncio.gather(
            *[self.setup_signal_handlers(), self._start_podman_service()]
        )

        self.nc = await nats.connect(servers=[DEFAULT_NATS_ADDRESS], name=f"agent-{id}")
        self.js = self.nc.jetstream()

        self.heartbeat_task = asyncio.create_task(self.heartbeat(self.js, self.id))
        self.server_task = asyncio.create_task(self.server_loop())

        await asyncio.gather(self.server_task, self.heartbeat_task)

    async def heartbeat(self, js: JetStreamContext, id: uuid.UUID):
        while True:
            try:
                bucket = await js.key_value(BUCKET_AGENTS)
            except BucketNotFoundError:
                continue
            break

        if not self.nc:
            logger.error("NATS connection not established. Exiting heartbeat loop.")
            return

        while not self._shutdown_event.is_set():
            try:
                if self.nc.is_closed:
                    logger.info("NATS connection closed, exiting heartbeat loop.")
                    break
                await bucket.put(f"{id}", self.agent_val.model_dump_json().encode())
            except nats.errors.ConnectionClosedError:
                logger.warning(
                    "Connection closed while trying to update key-value. Exiting loop."
                )
                break

            try:
                # this avoids waiting in this loop after the shutdown event is set
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        await self.remove_agent_key()

    async def remove_agent_key(self):
        if not self.nc or not self.js:
            logger.error("NATS connection not established. Exiting remove_agent_key.")
            return

        try:
            bucket = await self.js.key_value(BUCKET_AGENTS)
        except BucketNotFoundError:
            logger.warning(
                f"Bucket {BUCKET_AGENTS} not found. Exiting remove_agent_key."
            )
            return

        logger.info(f"Removing agent key {self.id}")
        try:
            await bucket.delete(f"{self.id}")
            logger.info(f"Agent key {self.id} removed successfully.")
        except Exception as e:
            logger.exception(f"Exception occurred while removing agent key: {e}")

    async def shutdown(self):
        logger.info("Shutting down agent...")
        self._shutdown_event.set()

        if self.heartbeat_task:
            await self.heartbeat_task

        if self.nc:
            # TODO: not sure why, but this results in drain timeout.
            # try:
            #     await self.nc.drain()  # Drain and close NATS connection
            # except nats.errors.FlushTimeoutError as err:
            #     logger.warning(f'{err}')
            await self.nc.close()

        self._cleanup_containers()
        await self._stop_podman_service()

        logger.info("Agent shut down successfully.")

    async def server_loop(self):
        logger.info("Server loop running...")
        # TODO: placeholder
        if not self.nc or not self.js:
            logger.error("NATS connection not established. Exiting server loop.")
            return
        await self._shutdown_event.wait()
        logger.info("Server loop exiting")

    async def setup_signal_handlers(self):
        logger.info("Setting up signal handlers...")

        loop = asyncio.get_running_loop()

        def handle_signal():
            logger.info("Signal received, shutting down processes...")
            asyncio.create_task(self.shutdown())

        loop.add_signal_handler(signal.SIGINT, handle_signal)
        loop.add_signal_handler(signal.SIGTERM, handle_signal)

    def start_operators(self) -> dict[uuid.UUID, Container]:
        containers = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return containers
        try:
            self.pipeline.to_json()
        except ValidationError as e:
            logger.error(f"No pipeline configuration found: {e}")
            return containers

        env = {k: str(v) for k, v in cfg.model_dump().items()}

        with PodmanClient(base_url=self._podman_service_uri) as client:
            for id, op_info in self.pipeline.operators.items():
                container = client.containers.create(
                    image=op_info.image,
                    environment=env,  # For now we have to pass everything through
                    name=f"operator-{id}",
                    command=["--id", str(id)],
                    detach=True,
                    network_mode="host",
                    remove=True,
                    labels={"agent.id": str(self.id)},
                )
                container.start()
                containers[id] = container

        return containers
