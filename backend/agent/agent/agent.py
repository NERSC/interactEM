import asyncio.subprocess
import os
import signal
import tempfile
import time
import uuid

import nats
import nats.errors
import podman.errors
from core.constants import BUCKET_AGENTS, DEFAULT_NATS_ADDRESS
from core.logger import get_logger
from core.pipeline import Pipeline
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import BucketNotFoundError
from podman.domain.containers import Container
from pydantic import ValidationError

from .config import cfg

try:
    from podman_hpc_client import PodmanHpcClient as PodmanClient
except ImportError:
    # Fallback to podman client if podman-hpc-client is not installed for dev/test
    from podman import PodmanClient

import podman

logger = get_logger("agent", "DEBUG")

class Agent:
    def __init__(self):
        self.id = uuid.uuid4()
        self.pipeline: Pipeline | None = None
        self.containers: dict[str, Container] = {}
        self._podman_service_dir = tempfile.TemporaryDirectory(
            prefix="core-", ignore_cleanup_errors=True
        )
        self._podman_service_uri = f"unix://{self._podman_service_dir.name}/podman.sock"
        self._shutdown_event = asyncio.Event()
        self.nc: NATSClient | None = None
        self.js: JetStreamContext | None = None

    async def _start_podman_service(self):
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
        await asyncio.gather(*[self.setup_signal_handlers(), self._start_podman_service()])

        self.nc = await nats.connect(
            servers=[DEFAULT_NATS_ADDRESS], name=f"agent-{id}"
        )
        self.js = self.nc.jetstream()

        await asyncio.gather(self.server_loop(), self.heartbeat(self.js, self.id))

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
                # TODO: should put more useful information on the key-value
                # TODO: could make this an object store for things like status...
                await bucket.put(f"{id}", bytes(f"agent-{id}", "utf-8"))
            except nats.errors.ConnectionClosedError:
                logger.warning("Connection closed while trying to update key-value. Exiting loop.")
                break

            try:
                # this avoids waiting in this loop after the shutdown event is set
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        logger.info("Exiting heartbeat loop.")

    async def shutdown(self):
        logger.info("Shutting down agent...")

        if self.nc:
            await self.nc.drain() # TODO: may want to not do drain here
            await self.nc.close()

        self._shutdown_event.set()
        self._cleanup_containers()
        await self._stop_podman_service()

        logger.info("Agent shut down successfully.")
        exit(0)

    async def server_loop(self):
        logger.info("Server loop running...")
        # TODO: placeholder
        await self._shutdown_event.wait()  # Wait until the event is set
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
