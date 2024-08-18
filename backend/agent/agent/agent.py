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
from core.constants import BUCKET_AGENTS, DEFAULT_NATS_ADDRESS, STREAM_AGENTS
from core.events.pipelines import PipelineRunEvent
from core.logger import get_logger
from core.models.agent import AgentStatus, AgentVal
from core.models.pipeline import PipelineJSON
from core.models.uri import URI, CommBackend, URILocation
from core.pipeline import Pipeline
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy
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

    async def _stop_and_remove_container(self, container: Container):
        logger.info(f"Stopping container {container.name}")
        await asyncio.to_thread(container.stop)
        logger.info(f"Removing container {container.name}")
        await asyncio.to_thread(container.remove)

    async def _cleanup_containers(self):
        logger.info("Cleaning up containers...")

        with PodmanClient(base_url=self._podman_service_uri) as client:
            # containers = client.containers.list()
            containers = client.containers.list(label=f"agent.id={self.id}")

            tasks = [
                self._stop_and_remove_container(container) for container in containers
            ]

            # Run the tasks concurrently
            await asyncio.gather(*tasks)
            for container in containers:
                # TODO: this should be a little bit more robust
                # do we even need to store containers in the agent?
                if not isinstance(container.name, str):
                    continue
                self.containers.pop(
                    uuid.UUID(container.name.removeprefix("operator-")), None
                )

    async def run(self):
        logger.info(f"Starting agent with configuration: {cfg.model_dump()}")
        await asyncio.gather(
            *[self.setup_signal_handlers(), self._start_podman_service()]
        )

        self.nc = await nats.connect(servers=[DEFAULT_NATS_ADDRESS], name=f"agent-{id}")
        self.js = self.nc.jetstream()

        self.heartbeat_task = asyncio.create_task(self.heartbeat(self.js, self.id))
        self.server_task = asyncio.create_task(self.server_loop())

        await self._shutdown_event.wait()
        await self.shutdown()
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

        if self.heartbeat_task:
            await self.heartbeat_task

        if self.server_task:
            await self.server_task

        if self.nc:
            # TODO: not sure why, but this results in drain timeout.
            # try:
            #     await self.nc.drain()  # Drain and close NATS connection
            # except nats.errors.FlushTimeoutError as err:
            #     logger.warning(f'{err}')
            await self.nc.close()

        await self._cleanup_containers()
        await self._stop_podman_service()

        logger.info("Agent shut down successfully.")

    async def server_loop(self):
        logger.info("Server loop running...")
        if not self.nc or not self.js:
            logger.error("NATS connection not established. Exiting server loop.")
            return

        # TODO: make this a util
        consumer_cfg = ConsumerConfig(
            description=f"agent-{self.id}",
            deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
        )
        psub = await self.js.pull_subscribe(
            stream=STREAM_AGENTS,
            subject=f"{STREAM_AGENTS}.{self.id}",
            config=consumer_cfg,
        )
        print(await psub.consumer_info())

        while not self._shutdown_event.is_set():
            try:
                msgs = await psub.fetch(1)
                asyncio.gather(*[msg.ack() for msg in msgs])
                for msg in msgs:
                    try:
                        event = PipelineRunEvent.model_validate_json(msg.data)
                    except ValidationError:
                        logger.error("Invalid message")
                        return
                    valid_pipeline = PipelineJSON(id=event.id, **event.data)
                    logger.info(f"Validated pipeline: {valid_pipeline.id}")
                    self.pipeline = Pipeline.from_pipeline(valid_pipeline)
                    break

                self.containers = await self.start_operators()
            except nats.errors.TimeoutError:
                continue
        logger.info("Server loop exiting")

    async def setup_signal_handlers(self):
        logger.info("Setting up signal handlers...")

        loop = asyncio.get_running_loop()

        def handle_signal():
            logger.info("Signal received, shutting down processes...")
            self._shutdown_event.set()

        loop.add_signal_handler(signal.SIGINT, handle_signal)
        loop.add_signal_handler(signal.SIGTERM, handle_signal)

    async def start_operators(self) -> dict[uuid.UUID, Container]:
        # Destroy any existing containers
        await self._cleanup_containers()
        containers = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return containers
        try:
            self.pipeline.to_json()
        except ValidationError as e:
            logger.error(f"No pipeline configuration found: {e}")
            return containers

        logger.info("Starting operators...")

        env = {k: str(v) for k, v in cfg.model_dump().items()}

        with PodmanClient(base_url=self._podman_service_uri) as client:
            for id, op_info in self.pipeline.operators.items():
                logger.info(f"Starting operator {id} with image {op_info.image}")
                try:
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
                except podman.errors.exceptions.APIError as e:
                    logger.error(f"Error creating container: {e}")
                    continue
                container.start()
                logger.info(f"Container {container.name} started...")
                containers[id] = container

        return containers
