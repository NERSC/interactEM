import asyncio.subprocess
import json
import os
import signal
import tempfile
import time
import uuid
from collections.abc import Coroutine
from typing import Any

import nats
import nats.errors
import nats.js
import nats.js.errors
import podman
import podman.errors
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import BucketNotFoundError
from podman.domain.containers import Container
from podman_hpc_client import PodmanHpcClient
from pydantic import ValidationError

from interactem.core.constants import (
    BUCKET_AGENTS,
    OPERATOR_ID_ENV_VAR,
    STREAM_OPERATORS,
    STREAM_PARAMETERS_UPDATE,
)
from interactem.core.constants.mounts import CORE_MOUNT, OPERATORS_MOUNT
from interactem.core.logger import get_logger
from interactem.core.models.agent import AgentStatus, AgentVal
from interactem.core.models.operators import OperatorParameter, ParameterType
from interactem.core.models.pipeline import (
    OperatorJSON,
    PipelineAssignment,
    PipelineJSON,
    PodmanMount,
    PodmanMountType,
)
from interactem.core.models.uri import URI, CommBackend, URILocation
from interactem.core.nats import (
    create_or_update_stream,
    get_agents_bucket,
    nc,
    publish_error,
)
from interactem.core.nats.config import (
    AGENTS_STREAM_CONFIG,
    NOTIFICATIONS_STREAM_CONFIG,
    OPERATORS_STREAM_CONFIG,
    PARAMETERS_STREAM_CONFIG,
)
from interactem.core.nats.consumers import (
    create_agent_consumer,
    create_agent_parameter_consumer,
)
from interactem.core.pipeline import Pipeline
from interactem.core.util import create_task_with_ref

from .config import cfg

# Can use this for mac:
# https://podman-desktop.io/blog/5-things-to-know-for-a-docker-user#docker-compatibility-mode
if cfg.PODMAN_SERVICE_URI:
    PODMAN_SERVICE_URI = cfg.PODMAN_SERVICE_URI
else:
    PODMAN_SERVICE_URI = None

# Use configuration, as we always expect to install podman-hpc-client
if cfg.LOCAL:
    from podman import PodmanClient
else:
    from podman_hpc_client import PodmanHpcClient as PodmanClient


logger = get_logger()

GLOBAL_ENV = {k: str(v) for k, v in cfg.model_dump().items()}
GLOBAL_ENV["NATS_SERVER_URL"] = GLOBAL_ENV["NATS_SERVER_URL_IN_CONTAINER"]

OPERATOR_CREDS_TARGET = "/operator.creds"
OPERATOR_CREDS_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str(cfg.OPERATOR_CREDS_FILE),
    target=OPERATOR_CREDS_TARGET,
)


class Agent:
    def __init__(self):
        self.id = uuid.uuid4()
        self.pipeline: Pipeline | None = None
        self.my_operator_ids: list[uuid.UUID] = []
        self.start_time = time.time()

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
            tags=cfg.AGENT_TAGS,
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
        self.watch_tasks: dict[uuid.UUID, asyncio.Task] = {}
        self.task_refs: set[asyncio.Task] = set()

    async def _start_podman_service(self, create_process=False):
        self._podman_process = None
        if create_process:
            if PodmanClient is PodmanHpcClient:
                podman_cmd = "podman-hpc"
            else:
                podman_cmd = "podman"

            args = [
                podman_cmd,
                "system",
                "service",
                "--time=0",
                self._podman_service_uri,
            ]
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

            if tries == 0 and create_process:
                raise RuntimeError("Podman service didn't successfully start")

            if tries == 0:
                logger.warning("Podman is not running, trying to start it up...")
                await self._start_podman_service(create_process=True)

            logger.info("Podman service started")

    async def _stop_podman_service(self):
        if self._podman_process is not None:
            logger.info("Stopping podman service")
            self._podman_process.terminate()
            await self._podman_process.wait()

    async def _cleanup_containers(self):
        logger.info("Cleaning up containers...")

        with PodmanClient(base_url=self._podman_service_uri) as client:
            containers = client.containers.list(
                filters={"label": f"agent.id={self.id}"}
            )
            tasks = [stop_and_remove_container(container) for container in containers]

            # Run the tasks concurrently
            await asyncio.gather(*tasks)

    async def run(self):
        logger.info(f"Starting agent with configuration: {cfg.model_dump()}")
        await asyncio.gather(
            *[self.setup_signal_handlers(), self._start_podman_service()]
        )

        self.nc = await nc(servers=[str(cfg.NATS_SERVER_URL)], name=f"agent-{self.id}")
        self.js = self.nc.jetstream()

        await create_or_update_stream(PARAMETERS_STREAM_CONFIG, self.js)
        await create_or_update_stream(AGENTS_STREAM_CONFIG, self.js)
        await create_or_update_stream(OPERATORS_STREAM_CONFIG, self.js)
        await create_or_update_stream(NOTIFICATIONS_STREAM_CONFIG, self.js)

        self.agent_val.status = AgentStatus.IDLE
        self.heartbeat_task = self.create_task(self.heartbeat(self.js, self.id))
        self.server_task = self.create_task(self.server_loop())

        await self._shutdown_event.wait()
        await self.shutdown()
        await asyncio.gather(self.server_task, self.heartbeat_task)

    async def heartbeat(self, js: JetStreamContext, id: uuid.UUID):
        if not self.nc:
            logger.error("NATS connection not established. Exiting heartbeat loop.")
            return

        tries = 10
        while tries > 0:
            try:
                bucket = await get_agents_bucket(js)
            except BucketNotFoundError:
                await asyncio.sleep(0.2)
                tries -= 1
                continue
            break

        if not bucket:
            logger.error(f"Bucket {BUCKET_AGENTS} not found. Exiting heartbeat loop.")
            return

        while not self._shutdown_event.is_set():
            try:
                if self.nc.is_closed:
                    logger.info("NATS connection closed, exiting heartbeat loop.")
                    break

                # Update the agent values with the current state
                self.agent_val.pipeline_assignments = self.my_operator_ids
                self.agent_val.uptime = time.time() - self.start_time

                # Clear old error messages
                self.agent_val.clear_old_errors()

                await bucket.put(f"{id}", self.agent_val.model_dump_json().encode())
            except nats.errors.ConnectionClosedError:
                logger.warning(
                    "Connection closed while trying to update key-value. Exiting loop."
                )
                break
            except nats.js.errors.ServiceUnavailableError as e:
                logger.exception(
                    f"JetStream service unavailable while trying to update key-value: {e}."
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
        self.agent_val.status = AgentStatus.SHUTTING_DOWN

        if self.heartbeat_task:
            await self.heartbeat_task

        if self.server_task:
            await self.server_task

        if self.nc:
            await self.nc.close()

        await self._cleanup_containers()
        await self._stop_podman_service()

        logger.info("Agent shut down successfully.")

    async def server_loop(self):
        logger.info("Server loop running...")
        if not self.nc or not self.js:
            logger.error("NATS connection not established. Exiting server loop.")
            return

        psub = await create_agent_consumer(self.js, self.id)

        while not self._shutdown_event.is_set():
            try:
                msgs = await psub.fetch(1)
                [self.create_task(msg.ack()) for msg in msgs]
            except nats.errors.TimeoutError:
                try:
                    await psub.consumer_info()
                except nats.js.errors.NotFoundError as e:
                    self.agent_val.status = AgentStatus.ERROR
                    _msg = f"Consumer not found: {e}"
                    self.agent_val.add_error(_msg)
                    logger.exception(_msg)
                continue

            for msg in msgs:
                try:
                    event = PipelineAssignment.model_validate_json(msg.data)
                    assert event.agent_id == self.id
                    logger.info(f"Agent ID verified: {event.agent_id}")
                except (ValidationError, AssertionError) as e:
                    self.agent_val.status = AgentStatus.ERROR
                    _msg = f"Invalid assignment: {e}"
                    self.agent_val.add_error(_msg)
                    logger.exception(_msg)
                    continue

                try:
                    valid_pipeline = PipelineJSON.model_validate(event.pipeline)
                    self.pipeline = Pipeline.from_pipeline(valid_pipeline)
                    self.my_operator_ids = event.operators_assigned
                    self.agent_val.operator_assignments = (
                        event.operators_assigned
                    )  # Set operator assignments
                    logger.info(f"Operators assigned: {self.my_operator_ids}")
                    self.agent_val.status = AgentStatus.BUSY
                    self.agent_val.status_message = "Starting operators..."
                    await self.start_operators()
                    self.agent_val.status_message = "Operators started..."
                    self.agent_val.status = AgentStatus.IDLE
                except Exception as e:
                    self.agent_val.status = AgentStatus.ERROR
                    _msg = f"Failed to start operators: {e}"
                    self.agent_val.add_error(_msg)
                    publish_error(self.js, _msg, task_refs=self.task_refs)
                    logger.exception(_msg)
                    continue
        logger.info("Server loop exiting")

    async def setup_signal_handlers(self):
        logger.info("Setting up signal handlers...")

        loop = asyncio.get_running_loop()

        def handle_signal(sig_num=None):
            signal_name = (
                signal.Signals(sig_num).name if sig_num is not None else "UNKNOWN"
            )
            logger.info(f"Signal {signal_name} received, shutting down processes...")
            self._shutdown_event.set()

        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    async def start_operators(self) -> dict[uuid.UUID, Container]:
        if not self.js:
            raise ValueError("No JetStream context")
        # Destroy any existing containers
        await self.cancel_and_cleanup()
        containers = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return containers

        logger.info("Starting operators...")

        with PodmanClient(base_url=self._podman_service_uri) as client:
            tasks: list[asyncio.Task] = []

            for id, op_info in self.pipeline.operators.items():
                if id not in self.my_operator_ids:
                    continue

                task = self.create_task(
                    self._start_operator(
                        op_info,
                        client,
                    )
                )
                tasks.append(task)

            results: list[
                tuple[OperatorJSON, Container] | BaseException
            ] = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, BaseException):
                    _msg = f"Error starting operator: {result}"
                    logger.exception(_msg)
                    self.agent_val.add_error(_msg)
                    publish_error(self.js, _msg, task_refs=self.task_refs)
                else:
                    operator, container = result
                    containers[operator.id] = container
                    self.watch_tasks[operator.id] = self.create_task(
                        self.container_task(operator, container)
                    )

        return containers

    async def _start_operator(
        self, operator: OperatorJSON, client: PodmanClient
    ) -> tuple[OperatorJSON, Container]:
        logger.info(f"Starting operator {operator.id} with image {operator.image}")

        if self.pipeline is None:
            raise ValueError("No pipeline configuration found")

        if operator.id not in self.pipeline.operators:
            raise ValueError(f"Operator {operator.id} not found in pipeline")

        env = GLOBAL_ENV.copy()
        env.update(operator.env)
        env.update({OPERATOR_ID_ENV_VAR: str(operator.id)})

        # Mount in the operator credentials
        operator.mounts.append(OPERATOR_CREDS_MOUNT)
        env.update(
            {"NATS_CREDS_FILE": OPERATOR_CREDS_TARGET, "NATS_SECURITY_MODE": "creds"}
        )

        if cfg.MOUNT_LOCAL_REPO:
            operator.mounts.append(CORE_MOUNT)
            operator.mounts.append(OPERATORS_MOUNT)

        container = await create_container(
            self.id,
            client,
            operator,
            env,
        )
        container.start()

        if not self.js:
            raise ValueError("No JetStream context")

        # Publish pipeline to JetStream
        try:
            await self.js.publish(
                subject=f"{STREAM_OPERATORS}.{operator.id}",
                payload=self.pipeline.to_json().model_dump_json().encode(),
            )
            logger.info(f"Published pipeline for operator {operator.id}")
            logger.debug(f"Pipeline: {self.pipeline.to_json().model_dump_json()}")
        except Exception as e:
            raise ValueError(
                f"Failed to publish to JetStream for operator {operator.id}: {e}"
            )

        return operator, container

    async def container_task(
        self, operator: OperatorJSON, container: Container
    ) -> None:
        """
        Manages the operator's container lifecycle and restarts it when mount parameters change.
        """
        if not self.js:
            raise ValueError("No JetStream context")

        restart_event = asyncio.Event()

        changed_parameters: dict[str, OperatorParameter] = {}
        parameter_tasks: list[asyncio.Task] = []

        current_operator = operator
        current_container = container

        # Start parameter tasks for each mount parameter
        if operator.parameters is not None:
            for param in operator.parameters:
                if param.type != ParameterType.MOUNT:
                    continue
                changed_parameters[param.name] = param
                # Start a parameter task for each mount parameter
                parameter_task = self.create_task(
                    self.parameter_task(
                        current_operator, param, restart_event, changed_parameters
                    )
                )
                parameter_tasks.append(parameter_task)

        while not self._shutdown_event.is_set():
            shutdown_task = self.create_task(self._shutdown_event.wait())
            restart_task = self.create_task(restart_event.wait())

            _, pending = await asyncio.wait(
                [shutdown_task, restart_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if self._shutdown_event.is_set():
                break

            # Check if the container is still running
            try:
                current_container.reload()
            except podman.errors.exceptions.APIError as e:
                logger.warning(f"Container {current_container.name} not found: {e}")
                break
            if current_container.status != "running":
                logger.info(f"Container {current_container.name} is no longer running.")
                await stop_and_remove_container(current_container)
                break

            if restart_event.is_set():
                restart_event.clear()

                # Restart the container with updated mounts
                # No need to create a new operator; current_operator has updated mounts
                # Re-resolve the mounts
                resolved = True
                for mount in current_operator.mounts:
                    if not mount.resolve():
                        _msg = f"Mount source not found: {mount.source}"
                        logger.error(_msg)
                        self.agent_val.add_error(_msg)
                        resolved = False
                if not resolved:
                    logger.error("Failed to resolve mounts")
                    continue

                await stop_and_remove_container(current_container)
                with PodmanClient(base_url=self._podman_service_uri) as client:
                    try:
                        new_operator, new_container = await self.create_task(
                            self._start_operator(current_operator, client)
                        )
                        current_operator = new_operator
                        current_container = new_container
                    except Exception as e:
                        _msg = f"Error starting operator: {e}"
                        logger.exception(_msg)
                        publish_error(self.js, _msg, task_refs=self.task_refs)
                        self.agent_val.add_error(_msg)
                        continue

                for param in changed_parameters.values():
                    await update_parameter(self.js, current_operator, param)
                changed_parameters.clear()

        for task in parameter_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"Exited container task loop for operator {operator.id}")

    async def parameter_task(
        self,
        operator: OperatorJSON,
        parameter: OperatorParameter,
        restart_event: asyncio.Event,
        changed_parameters: dict[str, OperatorParameter],
    ):
        if not self.js:
            raise ValueError("No JetStream context")

        try:
            psub = await create_agent_parameter_consumer(
                self.js, self.id, operator, parameter
            )
        except Exception as e:
            logger.exception(f"Error subscribing to parameter {parameter.name}: {e}")
            return

        # Publish initial value
        await update_parameter(self.js, operator, parameter)

        # Create an invalid parameter to publish when the parameter is invalid
        invalid_parameter = OperatorParameter(
            name=parameter.name,
            label=parameter.label,
            description=parameter.description,
            type=parameter.type,
            default=parameter.default,
            required=parameter.required,
            value="ERROR",
        )

        while not self._shutdown_event.is_set():
            try:
                msgs = await psub.fetch(1, timeout=1)
                if not msgs:
                    continue
                msg = msgs[0]
                await msg.ack()
                if not msg.data:
                    logger.warning(
                        f"Received empty message for parameter '{parameter.name}'"
                    )
                    continue
                try:
                    val = json.loads(msg.data.decode("utf-8"))
                    new_val = val.get(parameter.name)
                    if new_val == parameter.value:
                        await update_parameter(self.js, operator, parameter)
                        continue
                    # Validate the new value before updating
                    if not operator.validate_mount_for_parameter(parameter, new_val):
                        logger.error(
                            f"Invalid mount path for parameter '{parameter.name}': {new_val}"
                        )
                        await update_parameter(self.js, operator, invalid_parameter)
                        continue

                    parameter.value = new_val
                    operator.update_mounts_for_parameter(parameter)
                    changed_parameters[parameter.name] = parameter
                    restart_event.set()
                except json.JSONDecodeError as e:
                    _msg = (
                        f"Error decoding message for parameter '{parameter.name}': {e}"
                    )
                    logger.exception(_msg)
                    self.agent_val.add_error(_msg)
                    publish_error(self.js, _msg, task_refs=self.task_refs)
                    continue
            except nats.errors.TimeoutError:
                continue
            except Exception as e:
                _msg = f"Error fetching update for parameter '{parameter.name}': {e}"
                logger.exception(_msg)
                self.agent_val.add_error(_msg)
                publish_error(self.js, _msg, task_refs=self.task_refs)
                continue

        await psub.unsubscribe()

    async def cancel_and_cleanup(self):
        for operator_id, task in self.watch_tasks.items():
            logger.info(
                f"Cancelling existing container task for operator {operator_id}"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Container task for operator {operator_id} cancelled.")
        self.watch_tasks.clear()
        await self._cleanup_containers()

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        return create_task_with_ref(self.task_refs, coro)


async def update_parameter(
    js: JetStreamContext,
    operator: OperatorJSON,
    parameter: OperatorParameter,
):
    value = parameter.value if parameter.value is not None else parameter.default
    subject = f"{STREAM_PARAMETERS_UPDATE}.{operator.id}.{parameter.name}"
    payload = json.dumps(value).encode("utf-8")
    asyncio.create_task(js.publish(subject=subject, payload=payload))


async def create_container(
    agent_id: uuid.UUID,
    client: PodmanClient,
    operator: OperatorJSON,
    env: dict[str, Any],
    max_retries=1,
) -> Container:
    name = f"operator-{operator.id}"
    network_mode = operator.network_mode or "host"

    # Try to pull the image first if it doesn't exist
    try:
        client.images.get(operator.image)
        logger.debug(f"Image {operator.image} is already available")
    except podman.errors.exceptions.ImageNotFound:
        logger.info(f"Image {operator.image} not found locally, attempting to pull...")
        try:
            client.images.pull(operator.image)
            logger.info(f"Successfully pulled image {operator.image}")
        except Exception as e:
            error_msg = f"Failed to pull image {operator.image}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    for attempt in range(max_retries + 1):
        # Expand users
        # This should only be done at the agent (where data resides)
        for mount in operator.mounts:
            mount.resolve()
        try:
            return client.containers.create(
                image=operator.image,
                environment=env,
                name=name,
                command=operator.command,
                detach=True,
                stdout=True,
                stderr=True,
                log_config={
                    "Type": "json-file",
                } if isinstance(client, PodmanHpcClient) else {},
                network_mode=network_mode,
                remove=True,
                labels={"agent.id": str(agent_id)},
                mounts=[mount.model_dump() for mount in operator.mounts],
            )
        except podman.errors.exceptions.APIError as e:
            # _cleanup_containers() doesn't work for dead containers
            # These are left behind and need to be removed
            # TODO: should _cleanup_containers() work for dead containers?
            if is_name_conflict_error(e):
                if attempt < max_retries:
                    await handle_name_conflict(client, name)
                else:
                    raise e
            else:
                raise e
        except Exception as e:
            raise e
    raise RuntimeError(
        f"Failed to create container {name} after {max_retries + 1} attempts"
    )


async def stop_and_remove_container(container: Container) -> None:
    try:
        container.reload()
        if container.status == "running":
            logger.info(f"Stopping container {container.name}")
            await asyncio.to_thread(container.stop)
        logger.info(f"Removing container {container.name}")
        await asyncio.to_thread(container.remove)
    except podman.errors.exceptions.APIError as e:
        logger.warning(f"Error stopping/removing container {container.name}: {e}")


def is_name_conflict_error(error: podman.errors.exceptions.APIError) -> bool:
    error_message = str(error)
    return "container name" in error_message and "is already in use" in error_message


async def handle_name_conflict(client: PodmanClient, container_name: str) -> None:
    logger.warning(
        f"Container name conflict detected for {container_name}. "
        f"Attempting to remove the conflicting container."
    )
    conflicting_container = client.containers.get(container_name)
    await stop_and_remove_container(conflicting_container)
    logger.info(f"Conflicting container {conflicting_container.id} removed. ")
