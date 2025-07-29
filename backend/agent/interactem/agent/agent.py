import asyncio
import os
import tempfile
import time
import uuid
from collections.abc import Coroutine
from typing import Any

import podman
import podman.errors
import stamina
from faststream.nats import NatsBroker
from faststream.nats.publisher.asyncapi import AsyncAPIPublisher
from podman.domain.containers import Container
from pydantic import ValidationError
from stamina.instrumentation import set_on_retry_hooks

from interactem.core.constants import (
    OPERATOR_ID_ENV_VAR,
)
from interactem.core.constants.mounts import CORE_MOUNT, OPERATORS_MOUNT
from interactem.core.logger import get_logger
from interactem.core.models.containers import (
    MountDoesntExistError,
    PodmanMount,
    PodmanMountType,
)
from interactem.core.models.kvs import AgentStatus, AgentVal
from interactem.core.models.runtime import (
    AgentRuntimeOperator,
    PipelineAssignment,
    RuntimeOperator,
    RuntimeOperatorID,
    RuntimeOperatorParameter,
    RuntimeOperatorParameterUpdate,
    RuntimeParameterCollection,
    RuntimeParameterCollectionType,
)
from interactem.core.models.spec import ParameterSpecType
from interactem.core.models.uri import URI, CommBackend, URILocation
from interactem.core.nats.consumers import create_agent_mount_consumer
from interactem.core.nats.kv import InteractemBucket, KeyValueLoop
from interactem.core.nats.publish import (
    create_agent_mount_publisher,
    publish_agent_mount_parameter_ack,
    publish_pipeline_to_operators,
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
    PODMAN_COMMAND = "podman"
    from podman import PodmanClient
else:
    PODMAN_COMMAND = "podman-hpc"
    from podman_hpc_client import PodmanHpcClient as PodmanClient


logger = get_logger()


def log_hook(details: stamina.instrumentation.RetryDetails) -> None:
    logger.warning(f"Retry details: {details}")


set_on_retry_hooks([log_hook])

GLOBAL_ENV = {k: str(v) for k, v in cfg.model_dump().items()}
GLOBAL_ENV["NATS_SERVER_URL"] = GLOBAL_ENV["NATS_SERVER_URL_IN_CONTAINER"]

OPERATOR_CREDS_TARGET = "/operator.creds"
OPERATOR_CREDS_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str(cfg.OPERATOR_CREDS_FILE),
    target=OPERATOR_CREDS_TARGET,
)

INTERACTEM_IMAGE_REGISTRY = "ghcr.io/nersc/interactem/"


class ContainerTracker:
    MAX_RESTARTS: int = 3

    def __init__(
        self,
        container: Container,
        operator: AgentRuntimeOperator,
    ):
        self.container = container
        self.operator = operator
        self.marked_for_restart = False
        self.mount_parameter_tasks: list[asyncio.Task] = []
        self.num_restarts = 0

    def mark(self):
        self.marked_for_restart = True

    def unmark(self):
        self.marked_for_restart = False

    def add_parameter_task(self, task: asyncio.Task):
        self.mount_parameter_tasks.append(task)

    def __del__(self):
        for task in self.mount_parameter_tasks:
            task.cancel()
        self.mount_parameter_tasks.clear()


class Agent:
    def __init__(self, id: uuid.UUID, broker: NatsBroker):
        self.id = id
        self.pipeline: Pipeline | None = None
        self._my_operator_ids: list[uuid.UUID] = []
        self._start_time = time.time()

        if PODMAN_SERVICE_URI:
            self._podman_service_uri = PODMAN_SERVICE_URI
        else:
            self._podman_service_dir = tempfile.TemporaryDirectory(
                prefix="core-", ignore_cleanup_errors=True
            )
            self._podman_service_uri = (
                f"unix://{self._podman_service_dir.name}/podman.sock"
            )

        # Broker attributes used for NATS connections
        assert broker.stream, "JetStream not initialized"
        assert broker._connection, "NATS connection not initialized"
        self.broker = broker
        self.nc = broker._connection
        self.js = broker.stream

        # this is set in the broker code
        self.error_publisher: AsyncAPIPublisher

        self._shutdown_event = asyncio.Event()

        self.agent_val: AgentVal = AgentVal(
            name=cfg.AGENT_NAME,
            tags=cfg.AGENT_TAGS,
            uri=URI(
                id=self.id,
                location=URILocation.agent,
                hostname="localhost",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.INITIALIZING,
            networks=cfg.AGENT_NETWORKS,
        )
        self.agent_kv: KeyValueLoop[AgentVal]
        self.container_trackers: dict[RuntimeOperatorID, ContainerTracker] = {}
        self._container_monitor_task: asyncio.Task | None = None
        self._task_refs: set[asyncio.Task] = set()

    async def _start_podman_service(self, create_process=False):
        self._podman_process = None
        if create_process:
            args = [
                PODMAN_COMMAND,
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
            await self._wait_for_podman(client)

        logger.info("Podman service started")

    async def _wait_for_podman(self, client: PodmanClient):
        for attempt in stamina.retry_context(podman.errors.exceptions.APIError):
            with attempt:
                client.version()
                return
        raise RuntimeError("Podman service failed to start")

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

        self.container_trackers = {}

    async def run(self):
        logger.info(f"Starting agent with configuration: {cfg.model_dump()}")
        create_process = not PODMAN_SERVICE_URI
        await self._start_podman_service(create_process=create_process)

        self.agent_val.status = AgentStatus.IDLE

        self.agent_kv = KeyValueLoop[AgentVal](
            nc=self.nc,
            js=self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.STATUS,
            update_interval=10.0,
            data_model=AgentVal,
        )
        self.agent_kv.before_update_callbacks.append(self._update_agent_state)
        self.agent_kv.add_or_update_value(self.agent_val.key(), self.agent_val)

        await self.agent_kv.start()
        self._container_monitor_task = await asyncio.create_task(
            self.monitor_containers()
        )

    async def receive_assignment(self, assignment: PipelineAssignment):
        try:
            self.pipeline = Pipeline.from_pipeline(assignment.pipeline)
            self._my_operator_ids = assignment.operators_assigned
            self.agent_val.operator_assignments = assignment.operators_assigned

            logger.info(f"Operators assigned: {self._my_operator_ids}")
            self.agent_val.status = AgentStatus.BUSY
            self.agent_val.status_message = "Cleaning up containers..."
            await self.agent_kv.update_now()
            await self._cleanup_containers()
            self.agent_val.status_message = "Starting operators..."
            await self.agent_kv.update_now()
            await self.start_operators()
            self.agent_val.status_message = "Operators started..."
            self.agent_val.status = AgentStatus.IDLE
            await self.agent_kv.update_now()
        except Exception as e:
            self.agent_val.status = AgentStatus.ERROR
            _msg = f"Failed to start operators: {e}"
            self.agent_val.add_error(_msg)
            await self.agent_kv.update_now()
            await self.error_publisher.publish(_msg)
            logger.exception(_msg)

    def _update_agent_state(self) -> None:
        self.agent_val.operator_assignments = self._my_operator_ids
        self.agent_val.uptime = time.time() - self._start_time
        self.agent_val.clear_old_errors()

    async def shutdown(self):
        logger.info("Shutting down agent...")
        self.agent_val.status = AgentStatus.SHUTTING_DOWN
        if self.agent_kv:
            await self.agent_kv.update_now()
        self._shutdown_event.set()

        for task in self._task_refs:
            task.cancel()
        await asyncio.gather(*self._task_refs, return_exceptions=True)
        self._task_refs.clear()

        await self._cleanup_containers()
        await self._stop_podman_service()

        if self.agent_kv:
            await self.agent_kv.stop()

        logger.info("Agent shut down successfully.")

    async def start_operators(self):
        if not self.pipeline:
            logger.info("No pipeline configuration found...")
            return {}

        logger.info("Starting operators...")

        with PodmanClient(base_url=self._podman_service_uri) as client:
            tasks: list[asyncio.Task] = []
            for op_id, op_info in self.pipeline.operators.items():
                if op_id not in self._my_operator_ids:
                    continue
                # Create a task to start the operator
                # and add it to the task list
                tasks.append(self.create_task(self._start_operator(op_info, client)))

            results: list[
                tuple[AgentRuntimeOperator, Container] | BaseException
            ] = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, BaseException):
                    _msg = f"Error starting operator: {result}"
                    logger.exception(_msg)
                    self.agent_val.add_error(_msg)
                    await self.error_publisher.publish(_msg)
                else:
                    operator, container = result
                    self.container_trackers[operator.id] = ContainerTracker(
                        container, operator
                    )
                    tracker = self.container_trackers[operator.id]
                    if not operator.parameters:
                        continue
                    for param in operator.parameters:
                        if not param.type == ParameterSpecType.MOUNT:
                            continue
                        # TODO: this should be done once for the
                        # same canonical ID
                        tracker.add_parameter_task(
                            asyncio.create_task(self.remount_task(tracker, param))
                        )

    async def _start_operator(
        self, operator: RuntimeOperator, client: PodmanClient
    ) -> tuple[AgentRuntimeOperator, Container]:
        logger.info(f"Starting operator {operator.id} with image {operator.image}")

        operator = AgentRuntimeOperator(**operator.model_dump())

        if self.pipeline is None:
            raise ValueError("No pipeline configuration found")

        if operator.id not in self.pipeline.operators:
            raise ValueError(f"Operator {operator.id} not found in pipeline")

        env = GLOBAL_ENV.copy()
        env.update(operator.env)
        env.update({OPERATOR_ID_ENV_VAR: str(operator.id)})
        env.update(
            {"NATS_CREDS_FILE": OPERATOR_CREDS_TARGET, "NATS_SECURITY_MODE": "creds"}
        )
        operator.env = env

        # Mount in the operator credentials
        operator.add_internal_mount(OPERATOR_CREDS_MOUNT)

        # For local dev, we can mount in the core/operators
        if cfg.MOUNT_LOCAL_REPO:
            operator.add_internal_mount(CORE_MOUNT)
            operator.add_internal_mount(OPERATORS_MOUNT)

        container = await create_container(self.id, client, operator)
        if not container:
            raise RuntimeError(f"Failed to create container for operator {operator.id}")
        container.start()

        # Publish pipeline to JetStream
        await publish_pipeline_to_operators(self.broker, self.pipeline, operator.id)
        logger.debug(f"Published pipeline for operator {operator.id}")
        logger.debug(f"Pipeline: {self.pipeline.to_runtime().model_dump_json()}")

        return operator, container

    async def remount_task(
        self, tracker: ContainerTracker, parameter: RuntimeOperatorParameter
    ):
        operator = tracker.operator

        # while this is single param, collection will still work
        mount_params = RuntimeParameterCollection.from_parameter_list(
            [parameter], RuntimeParameterCollectionType.MOUNT
        )

        sub = create_agent_mount_consumer(
            self.broker, self.id, operator.canonical_id, parameter
        )
        pub = create_agent_mount_publisher(
            self.broker,
            operator.id,
            parameter.name,
        )

        self.broker.setup_publisher(pub)

        async def handler(msg: dict[str, Any]):
            logger.info(f"Received mount parameter message: {msg}")

            try:
                # Parse the structured parameter update message
                update = RuntimeOperatorParameterUpdate.model_validate(msg)
            except ValidationError as e:
                logger.exception(f"Failed to parse parameter update: {e}")
                await self.error_publisher.publish(
                    f"Invalid parameter update format: {e}"
                )
                return

            new_val = update.value

            try:
                value_changed = mount_params.update_value(parameter.name, new_val)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid mount parameter value: {e}")
                await self.error_publisher.publish(str(e))
                return

            if not value_changed:
                logger.info(f"Mount {parameter.name} unchanged, skipping restart")
                return

            # Update the operator's parameter
            operator.update_parameter_value(parameter.name, new_val)

            try:
                operator.update_param_mounts(use_default=False)
            except MountDoesntExistError as e:
                logger.exception(e)
                await self.error_publisher.publish(str(e))
                return

            logger.info(
                f"Remounting {parameter.name} for operator {operator.id} with value {new_val}"
            )

            # Mark for restart
            tracker.mark()

            updated_param = mount_params.parameters[parameter.name]
            create_task_with_ref(
                self._task_refs,
                publish_agent_mount_parameter_ack(
                    pub, operator.canonical_id, updated_param
                ),
            )

        sub(handler)
        self.broker.setup_subscriber(sub)

        await sub.start()
        logger.info(
            f"Subscribed to parameter updates for {operator.id}.{parameter.name}"
        )

        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"Parameter task for {operator.id}.{parameter.name} cancelled.")
            raise
        finally:
            await sub.close()
            logger.info(
                f"Closed parameter subscription for {operator.id}.{parameter.name}."
            )

    async def monitor_containers(self):
        while not self._shutdown_event.is_set():
            await asyncio.sleep(3)
            for _, tracker in list(self.container_trackers.items()):
                if tracker.marked_for_restart:
                    await self.restart_operator(tracker)
                    tracker.unmark()
                    continue
                try:
                    tracker.container.reload()
                    if tracker.container.status == "running":
                        continue
                    if tracker.num_restarts >= ContainerTracker.MAX_RESTARTS:
                        _msg = f"Container {tracker.container.name} reached maximum restart attempts."
                        logger.error(_msg)
                        await self.error_publisher.publish(
                            f"Operator {tracker.operator.image} failed to start after {ContainerTracker.MAX_RESTARTS} attempts."
                        )
                        del self.container_trackers[tracker.operator.id]
                        continue
                    logger.info(
                        f"Container {tracker.container.name} stopped. Restarting..."
                    )
                    await self.restart_operator(tracker)
                    tracker.num_restarts += 1

                except podman.errors.exceptions.NotFound:
                    logger.warning(
                        f"Container {tracker.container.name} not found during monitoring"
                    )
                    # Remove the tracker if the container is not found
                    del self.container_trackers[tracker.operator.id]
                except Exception as e:
                    logger.exception(
                        f"Error monitoring container {tracker.container.name}: {e}"
                    )

    async def restart_operator(self, tracker: ContainerTracker):
        container = tracker.container
        operator = tracker.operator
        logger.info(f"Restarting operator {tracker.operator.id}")
        await stop_and_remove_container(container)
        with PodmanClient(base_url=self._podman_service_uri) as client:
            new_container = await create_container(self.id, client, operator)
            new_container.start()
            self.container_trackers[operator.id].container = new_container

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        return create_task_with_ref(self._task_refs, coro)


class NameConflictError(podman.errors.exceptions.APIError):
    pass


def is_name_conflict_error(exc: Exception) -> bool:
    if isinstance(exc, podman.errors.exceptions.APIError):
        error_message = str(exc)
        return (
            "container name" in error_message and "is already in use" in error_message
        )
    else:
        return False


async def create_container(
    agent_id: uuid.UUID,
    client: PodmanClient,
    operator: AgentRuntimeOperator,
) -> Container:
    name = f"operator-{operator.id}"
    network_mode = operator.network_mode or "host"
    log_config = {}
    if PODMAN_COMMAND == "podman-hpc":
        log_config = {"Type": "json-file"}

    # Try to pull the image first if it doesn't exist
    try:
        client.images.get(operator.image)
        logger.debug(f"Image {operator.image} is already available")
    except podman.errors.exceptions.ImageNotFound:
        logger.info(f"Image {operator.image} not found locally, attempting to pull...")
        if not operator.image.startswith(INTERACTEM_IMAGE_REGISTRY):
            _msg = f"Image {operator.image} is not from the interactem registry ({INTERACTEM_IMAGE_REGISTRY})."
            logger.error(_msg)
            raise RuntimeError(_msg)
        try:
            client.images.pull(operator.image)
            logger.info(f"Successfully pulled image {operator.image}")
        except Exception as e:
            error_msg = f"Failed to pull image {operator.image}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    for attempt in stamina.retry_context(on=is_name_conflict_error):
        # Expand users
        # This should only be done at the agent (where data resides)
        with attempt:
            if attempt.num > 1:
                await handle_name_conflict(client, name)
            return client.containers.create(
                image=operator.image,
                environment=operator.env,
                name=name,
                command=operator.command,
                detach=True,
                stdout=True,
                stderr=True,
                log_config=log_config,
                network_mode=network_mode,
                remove=True,
                labels={"agent.id": str(agent_id)},
                mounts=[mount.model_dump() for mount in operator.all_mounts],
            )

    raise RuntimeError(
        f"Failed to create container for operator {operator.id} after multiple attempts"
    )


async def stop_and_remove_container(container: Container) -> None:
    class ContainerStillRunning(Exception):
        pass

    try:
        container.reload()
    except podman.errors.exceptions.NotFound:
        logger.warning(f"Container {container.name} not found during reload")
        return

    try:
        if container.status == "running":
            logger.info(f"Stopping container {container.name}")
            await asyncio.to_thread(container.stop)
            for attempt in stamina.retry_context(on=ContainerStillRunning):
                with attempt:
                    container.reload()
                    if container.status == "running":
                        raise ContainerStillRunning(
                            f"Container {container.name} is still running"
                        )

        logger.info(f"Removing container {container.name}")
        await asyncio.to_thread(container.remove, force=True)
    except podman.errors.exceptions.NotFound:
        logger.warning(f"Container {container.name} not found during removal")


async def handle_name_conflict(client: PodmanClient, container_name: str) -> None:
    logger.warning(
        f"Container name conflict detected for {container_name}. "
        f"Attempting to remove the conflicting container."
    )
    conflicting_container = client.containers.get(container_name)
    await stop_and_remove_container(conflicting_container)
    logger.info(f"Conflicting container {conflicting_container.id} removed. ")
