import asyncio
import functools
import os
import tempfile
import time
import uuid

import anyio
import podman
import podman.errors
import stamina
from anyio import to_thread
from faststream.nats import NatsBroker
from faststream.nats.publisher.usecase import LogicPublisher
from podman.domain.containers import Container
from stamina.instrumentation import set_on_retry_hooks

from interactem.core.constants import (
    INTERACTEM_IMAGE_REGISTRY,
    OPERATOR_ID_ENV_VAR,
    VECTOR_IMAGE,
)
from interactem.core.constants.mounts import CORE_MOUNT, OPERATORS_MOUNT
from interactem.core.events.deployments import (
    AgentDeploymentRunEvent,
    AgentDeploymentStopEvent,
    AgentOperatorRestartEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.containers import (
    MountDoesntExistError,
    PodmanMount,
    PodmanMountType,
)
from interactem.core.models.kvs import AgentStatus, AgentVal
from interactem.core.models.runtime import (
    AgentRuntimeOperator,
    RuntimeOperator,
    RuntimeOperatorID,
    RuntimeOperatorParameter,
    RuntimeOperatorParameterUpdate,
    RuntimeParameterCollection,
    RuntimeParameterCollectionType,
)
from interactem.core.models.spec import ParameterSpecType
from interactem.core.models.uri import URI, CommBackend, URILocation
from interactem.core.nats.consumers import (
    create_agent_mount_consumer,
)
from interactem.core.nats.kv import InteractemBucket, KeyValueLoop
from interactem.core.nats.publish import (
    create_agent_mount_publisher,
    publish_agent_mount_parameter_ack,
    publish_pipeline_to_operators,
)
from interactem.core.pipeline import Pipeline

from .config import cfg
from .deployment import DeploymentContext
from .util import (
    detect_gpu_enabled,
)

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

if cfg.PODMAN_BINARY_PATH:
    PODMAN_COMMAND = str(cfg.PODMAN_BINARY_PATH)

agent_log_file = cfg.LOG_DIR / "agent.log"
logger = get_logger(log_file=agent_log_file)
logger.info(f"Agent logging initialized. Log file: {agent_log_file}")


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


PODMAN_MAX_POOL_SIZE = 100
IMAGE_PULL_LOCK = anyio.Lock()


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
        self.num_restarts = 0

    def mark(self):
        self.marked_for_restart = True

    def unmark(self):
        self.marked_for_restart = False


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
        self.broker = broker
        self.nc = broker.config.connection_state.connection
        self.js = broker.config.connection_state.stream

        # this is set in the broker code
        self.error_publisher: LogicPublisher

        agent_tags = list(cfg.AGENT_TAGS)
        if detect_gpu_enabled() and "gpu" not in agent_tags:
            agent_tags.append("gpu")
            logger.info("Detected GPU-capable agent; adding tag 'gpu'")

        self.agent_val: AgentVal = AgentVal(
            name=cfg.AGENT_NAME,
            tags=agent_tags,
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
        # suppress monitor during container cleanup
        self._suppress_monitor = False

        # Deployment management
        self._current_deployment: DeploymentContext | None = None
        self._deployment_task: asyncio.Task | None = None
        self._deployment_lock = anyio.Lock()
        self._monitor_task: asyncio.Task | None = None
        # Use asyncio.Event since KeyValueLoop expects it
        self._shutdown_event = asyncio.Event()
        # Separate shutdown event for KV loop to maintain updates during shutdown
        self._kv_shutdown_event = asyncio.Event()

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
        await self._set_status(
            AgentStatus.CLEANING_OPERATORS, "Cleaning up containers..."
        )
        self._suppress_monitor = True
        try:
            # Clear trackers first to avoid restarts
            self.container_trackers.clear()
            with PodmanClient(
                base_url=self._podman_service_uri, max_pool_size=PODMAN_MAX_POOL_SIZE
            ) as client:
                containers = client.containers.list(
                    filters={"label": f"agent.id={self.id}"}
                )
                # Exclude vector container from cleanup
                operator_containers = [
                    container
                    for container in containers
                    if container.labels.get("container.type") != "vector"
                ]
                async with anyio.create_task_group() as tg:
                    for container in operator_containers:
                        tg.start_soon(stop_and_remove_container, container)
        finally:
            self._suppress_monitor = False

    async def run(self):
        logger.info(f"Starting agent with configuration: {cfg.model_dump()}")
        create_process = not PODMAN_SERVICE_URI
        await self._start_podman_service(create_process=create_process)

        await self._set_status(AgentStatus.IDLE, update_now=False)

        self.agent_kv = KeyValueLoop[AgentVal](
            nc=self.nc,
            js=self.js,
            shutdown_event=self._kv_shutdown_event,
            bucket=InteractemBucket.STATUS,
            update_interval=10.0,
            data_model=AgentVal,
        )
        self.agent_kv.before_update_callbacks.append(self._update_agent_state)
        self.agent_kv.add_or_update_value(self.agent_val.key(), self.agent_val)

        await self.agent_kv.start()
        # Start the container monitor task at the agent level
        self._monitor_task = asyncio.create_task(self.monitor_containers())
        self._vector_container = await self._start_vector_container()

    async def _start_vector_container(self) -> Container:
        logger.info("Starting Vector container for log aggregation...")

        with PodmanClient(
            base_url=self._podman_service_uri, max_pool_size=PODMAN_MAX_POOL_SIZE
        ) as client:
            await pull_image(client, VECTOR_IMAGE)

            log_config = {
                "Type": "k8s-file",
                "Config": {"path": f"{cfg.LOG_DIR}/vector.log"},
            }
            container = client.containers.create(
                image=VECTOR_IMAGE,
                environment=GLOBAL_ENV,
                name=f"vector-{self.id}",
                detach=True,
                stdout=True,
                stderr=True,
                log_config=log_config,
                network_mode="host",
                remove=True,
                labels={"agent.id": str(self.id), "container.type": "vector"},
                mounts=[mount.model_dump() for mount in cfg.vector_mounts],
            )
            container.start()
            return container

    async def receive_cancellation(self, event: AgentDeploymentStopEvent):
        deployment_id = event.deployment_id
        logger.info(f"Received cancellation for deployment {deployment_id}")

        async with self._deployment_lock:
            # Check if this cancellation is for the current deployment
            if self._current_deployment is None:
                logger.warning(
                    f"Received cancellation for deployment {deployment_id}, "
                    f"but no deployment is currently running"
                )
                return

            if self._current_deployment.deployment_id != deployment_id:
                logger.warning(
                    f"Received cancellation for deployment {deployment_id}, "
                    f"but current deployment is {self._current_deployment.deployment_id}"
                )
                return

            # Cancel and wait for cleanup
            self._current_deployment.cancel()
            if self._deployment_task is not None:
                try:
                    await self._deployment_task
                except anyio.get_cancelled_exc_class():
                    pass
                except Exception as e:
                    logger.exception(f"Error during cancellation: {e}")

            self._current_deployment = None
            self._deployment_task = None

    async def restart_canonical_operator(self, event: AgentOperatorRestartEvent):
        """Restart all operators matching the canonical ID for the current deployment."""

        if self._current_deployment is None or self.pipeline is None:
            logger.warning(
                "Restart requested for %s but no deployment is active",
                event.canonical_operator_id,
            )
            return

        if self._current_deployment.deployment_id != event.deployment_id:
            logger.warning(
                "Restart event for deployment %s does not match current deployment %s",
                event.deployment_id,
                self._current_deployment.deployment_id,
            )
            return

        matching_trackers = [
            tracker
            for tracker in self.container_trackers.values()
            if tracker.operator.canonical_id == event.canonical_operator_id
        ]

        if not matching_trackers:
            logger.warning(
                "No operators found for canonical ID %s to restart",
                event.canonical_operator_id,
            )
            return

        logger.info(
            "Restarting %d operators for canonical ID %s",
            len(matching_trackers),
            event.canonical_operator_id,
        )

        self._suppress_monitor = True
        try:
            for tracker in matching_trackers:
                try:
                    await self.restart_operator(tracker)
                except Exception as e:
                    logger.exception(
                        "Failed to restart operator %s: %s", tracker.operator.id, e
                    )
                    if self.error_publisher:
                        await self.error_publisher.publish(
                            f"Failed to restart operator {tracker.operator.id}: {e}"
                        )
        finally:
            self._suppress_monitor = False

    async def receive_assignment(self, event: AgentDeploymentRunEvent):
        """Handle incoming deployment assignment.

        This method creates and runs a deployment within a DeploymentContext context.
        The deployment will continue running until explicitly cancelled via receive_cancellation.
        """
        assignment = event.assignment
        deployment_id = assignment.pipeline.id

        async with self._deployment_lock:
            # Cancel and WAIT for existing deployment to finish
            if self._deployment_task is not None and not self._deployment_task.done():
                logger.info(
                    f"Cancelling existing deployment to start new deployment {deployment_id}"
                )
                if self._current_deployment is not None:
                    self._current_deployment.cancel()

                # Wait for the old deployment task to actually finish cleanup
                try:
                    await self._deployment_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelled
                except Exception as e:
                    logger.exception(f"Error in cancelled deployment: {e}")

            # Create and spawn new deployment
            self._current_deployment = DeploymentContext(deployment_id)
            self._deployment_task = asyncio.create_task(
                self._run_deployment(event),
                name=f"deployment-{deployment_id}",
            )

    async def _run_deployment(self, event: AgentDeploymentRunEvent) -> None:
        """Run a deployment within a DeploymentContext context.

        This method manages the entire lifecycle of a deployment:
        1. Setup: load pipeline, create log directory, update status
        2. Execution: start operators and manage container monitoring
        3. Teardown: clean up when deployment ends or is cancelled
        """
        if self._current_deployment is None:
            logger.error("DeploymentContext not initialized for _run_deployment")
            raise RuntimeError("DeploymentContext not initialized for _run_deployment")

        deployment_id = self._current_deployment.deployment_id
        assignment = event.assignment

        async with self._current_deployment:
            try:
                self.pipeline = Pipeline.from_pipeline(assignment.pipeline)
                self._my_operator_ids = assignment.operators_assigned
                self.agent_val.operator_assignments = assignment.operators_assigned

                # Create deployment-specific log directory
                deployment_log_dir = cfg.LOG_DIR / str(deployment_id)
                deployment_log_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created deployment log directory: {deployment_log_dir}")

                logger.info(f"Operators assigned: {self._my_operator_ids}")

                self._suppress_monitor = True
                await self._cleanup_containers()
                self._suppress_monitor = False

                await self.start_operators()

                logger.info(f"Deployment {deployment_id} running...")
                # Keep deployment alive until cancelled
                await anyio.sleep_forever()

            except anyio.get_cancelled_exc_class():
                logger.info(f"Deployment {deployment_id} cancelled")
                raise
            except Exception as e:
                self.agent_val.status = AgentStatus.DEPLOYMENT_ERROR
                _msg = f"Error in deployment {deployment_id}: {e}"
                self.agent_val.add_error(_msg)
                await self.agent_kv.update_now()
                await self.error_publisher.publish(_msg)
                logger.exception(_msg)
            finally:
                # Shield cleanup from cancellation scope so it can complete
                with anyio.CancelScope(shield=True):
                    await self._cleanup_containers()
                    self._my_operator_ids.clear()
                    self.pipeline = None
                    self.agent_val.current_deployment_id = None
                    self.agent_val.status = AgentStatus.IDLE
                    await self.agent_kv.update_now()

    def _update_agent_state(self) -> None:
        depl_id = (
            self._current_deployment.deployment_id if self._current_deployment else None
        )
        self.agent_val.current_deployment_id = depl_id
        self.agent_val.operator_assignments = self._my_operator_ids
        self.agent_val.uptime = time.time() - self._start_time

    async def shutdown(self):
        logger.info("Shutting down agent...")
        # Set main shutdown event for deployment and monitor tasks
        await self._set_status(AgentStatus.SHUTTING_DOWN)
        self._shutdown_event.set()

        # Cancel current deployment if running
        async with self._deployment_lock:
            if self._current_deployment is not None:
                logger.info(
                    f"Cancelling deployment {self._current_deployment.deployment_id}"
                )
                self._current_deployment.cancel()
                if self._deployment_task is not None:
                    try:
                        await self._deployment_task
                    except anyio.get_cancelled_exc_class():
                        pass
                    except Exception as e:
                        logger.exception(f"Error during shutdown cancellation: {e}")
                self._current_deployment = None
                self._deployment_task = None

        await self._cleanup_containers()

        # Stop the vector container
        if self._vector_container:
            logger.info("Stopping Vector container...")
            await stop_and_remove_container(self._vector_container)

        await self._stop_podman_service()

        # Now stop the KV loop after other components are shut down
        # This allows final updates to be published
        if self.agent_kv:
            await self.agent_kv.update_now()
            self._kv_shutdown_event.set()
            await self.agent_kv.stop()

        logger.info("Agent shut down successfully.")

    async def on_nats_reconnect(self) -> None:
        """Refresh NATS/JetStream handles after a reconnect."""
        logger.info("NATS reconnected; refreshing agent NATS handles")
        self.nc = self.broker.config.connection_state.connection
        self.js = self.broker.config.connection_state.stream
        if self.agent_kv is not None:
            await self.agent_kv.refresh_connection(self.nc, self.js)

    async def start_operators(self):
        if not self.pipeline:
            logger.info("No pipeline configuration found...")
            raise RuntimeError("No pipeline configuration found")

        if self._current_deployment is None:
            logger.error("No active deployment for starting operators")
            raise RuntimeError("No active deployment for starting operators")

        logger.info("Starting operators...")
        await self._set_status(AgentStatus.OPERATORS_STARTING, "Starting operators...")
        with PodmanClient(
            base_url=self._podman_service_uri, max_pool_size=PODMAN_MAX_POOL_SIZE
        ) as client:
            operator_ids = [
                op_id
                for op_id in self.pipeline.operators.keys()
                if op_id in self._my_operator_ids
            ]

            logger.info(f"Starting {len(operator_ids)} operators...")

            images_to_pull = {
                self.pipeline.operators[op_id].image for op_id in operator_ids
            }
            await self._prefetch_images(client, images_to_pull)

            # Start all operators concurrently within a nested task group
            async with anyio.create_task_group() as start_tg:
                for op_id in operator_ids:
                    op_info = self.pipeline.operators[op_id]
                    start_tg.start_soon(
                        self._start_and_track_operator,
                        op_info,
                        client,
                        name=f"start-{op_id}",
                    )
            # All operators are started when we reach here

            logger.info(f"All {len(operator_ids)} operators started")

        await self._set_status(AgentStatus.DEPLOYMENT_RUNNING, "Operators started")

    async def _prefetch_images(
        self, client: PodmanClient, images: set[str]
    ) -> None:
        if not images:
            return

        logger.info(f"Ensuring availability of {len(images)} images before launch")
        failures: list[str] = []
        for image in images:
            try:
                if cfg.ALWAYS_PULL_IMAGES:
                    await pull_image(client, image)
                else:
                    await ensure_image_present(client, image)
            except Exception as e:
                _msg = f"Failed to prepare image {image}: {e}"
                logger.error(_msg)
                failures.append(_msg)

        if failures:
            summary = (
                f"Image prefetch failed for {len(failures)} image(s): "
                + "; ".join(failures)
            )
            self.agent_val.add_error(summary)
            await self._set_status(AgentStatus.DEPLOYMENT_ERROR, summary)
            if getattr(self, "error_publisher", None):
                await self.error_publisher.publish(summary)
            raise RuntimeError(summary)

    async def _start_and_track_operator(
        self, operator: RuntimeOperator, client: PodmanClient
    ) -> None:
        """Start operator and set up tracking and parameter monitoring."""
        try:
            operator, container = await self._start_operator(operator, client)
            self.container_trackers[operator.id] = ContainerTracker(container, operator)
            tracker = self.container_trackers[operator.id]

            # Set up parameter monitoring for mount parameters
            if operator.parameters and self._current_deployment is not None:
                for param in operator.parameters:
                    if not param.type == ParameterSpecType.MOUNT:
                        continue
                    # TODO: this should be done once for the
                    # same canonical ID
                    self._current_deployment.spawn_task(
                        self.remount_task(tracker, param),
                        name=f"remount-{operator.id}-{param.name}",
                    )
        except Exception as e:
            _msg = f"Error starting operator {operator.id}: {e}"
            logger.exception(_msg)
            self.agent_val.add_error(_msg)
            await self.error_publisher.publish(_msg)
            raise

    async def _start_operator(
        self, operator: RuntimeOperator, client: PodmanClient
    ) -> tuple[AgentRuntimeOperator, Container]:
        logger.info(f"Starting operator {operator.id} with image {operator.image}")

        operator = AgentRuntimeOperator(**operator.model_dump())

        if self.pipeline is None:
            raise ValueError("No pipeline configuration found")

        if operator.id not in self.pipeline.operators:
            raise ValueError(f"Operator {operator.id} not found in pipeline")

        if self._current_deployment is None:
            raise RuntimeError("No deployment_id set for operator creation")

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

        # If we doing logging, mount in the logs directory
        if cfg.log_mount:
            operator.add_internal_mount(cfg.log_mount)

        # Publish pipeline to JetStream
        await publish_pipeline_to_operators(self.broker, self.pipeline, operator.id)
        logger.debug(f"Published pipeline for operator {operator.id}")
        logger.debug(f"Pipeline: {self.pipeline.to_runtime().model_dump_json()}")

        container = await create_container(
            self.id, client, operator, self._current_deployment.deployment_id
        )
        if not container:
            raise RuntimeError(f"Failed to create container for operator {operator.id}")
        container.start()

        return operator, container

    async def remount_task(
        self, tracker: ContainerTracker, parameter: RuntimeOperatorParameter
    ):
        operator = tracker.operator

        # while this is single param, collection will still work
        mount_params = RuntimeParameterCollection.from_parameter_list(
            [parameter], RuntimeParameterCollectionType.MOUNT
        )

        pub = create_agent_mount_publisher(
            self.broker,
            operator.canonical_id,
            parameter.name,
        )
        await pub.start()

        # Publish the current (default) mount value when the task starts so
        # subsequent launches begin from the default instead of any prior
        # overrides that may still be in the stream.
        if self._current_deployment:
            self._current_deployment.spawn_task(
                publish_agent_mount_parameter_ack(
                    pub, operator.canonical_id, mount_params.parameters[parameter.name]
                ),
                name=f"ack-{operator.id}-{parameter.name}-initial",
            )

        psub: JetStreamContext.PullSubscription | None = None

        async def create_consumer():
            nonlocal psub
            psub = await create_agent_mount_consumer(
                self.js, self.id, operator.canonical_id, parameter.name
            )
            return psub

        await create_consumer()
        assert psub is not None

        async def handle_parameter_update(msg: NATSMsg, _js):
            try:
                update = RuntimeOperatorParameterUpdate.model_validate_json(msg.data)
            except ValidationError as e:
                logger.error(f"Invalid mount parameter update: {e}")
                await msg.term()
                return

            logger.info(f"Received mount parameter message: {update}")

            new_val = update.value

            try:
                value_changed = mount_params.update_value(parameter.name, new_val)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid mount parameter value: {e}")
                await self.error_publisher.publish(str(e))
                await msg.term()
                return

            if not value_changed:
                logger.info(f"Mount {parameter.name} unchanged, skipping restart")
                await msg.ack()
                return

            # Update the operator's parameter
            operator.update_parameter_value(parameter.name, new_val)

            try:
                operator.update_param_mounts(use_default=False)
            except MountDoesntExistError as e:
                logger.exception(e)
                await self.error_publisher.publish(str(e))
                await msg.term()
                return

            logger.info(
                f"Remounting {parameter.name} for operator {operator.id} with value {new_val}"
            )

            # Mark for restart
            tracker.mark()

            updated_param = mount_params.parameters[parameter.name]
            # Spawn acknowledgment task through deployment manager
            if self._current_deployment:
                self._current_deployment.spawn_task(
                    publish_agent_mount_parameter_ack(
                        pub, operator.canonical_id, updated_param
                    ),
                    name=f"ack-{operator.id}-{parameter.name}",
                )

            await msg.ack()

        try:
            logger.info(
                "Subscribed to parameter updates for %s.%s",
                operator.canonical_id,
                parameter.name,
            )
            await consume_messages(
                psub,
                handle_parameter_update,
                self.js,
                num_msgs=1,
                create_consumer=create_consumer,
            )
        except anyio.get_cancelled_exc_class():
            logger.info(f"Parameter task for {operator.id}.{parameter.name} cancelled.")
            raise
        finally:
            if psub is not None:
                await psub.unsubscribe()
            logger.info(
                f"Closed parameter subscription for {operator.id}.{parameter.name}."
            )

    async def monitor_containers(self):
        while not self._shutdown_event.is_set():
            await anyio.sleep(3)

            if self._suppress_monitor:
                logger.debug("Container monitoring suppressed.")
                continue

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

        if self._current_deployment is None:
            raise RuntimeError("No deployment set for operator restart")

        with PodmanClient(base_url=self._podman_service_uri) as client:
            new_container = await create_container(
                self.id, client, operator, self._current_deployment.deployment_id
            )
            new_container.start()
            self.container_trackers[operator.id].container = new_container

    async def _set_status(
        self, status: AgentStatus, message: str | None = None, update_now: bool = True
    ) -> None:
        """Update agent status and optionally message, then sync to KV store."""
        self.agent_val.status = status
        if message is not None:
            self.agent_val.status_message = message
        if update_now and self.agent_kv:
            await self.agent_kv.update_now()


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


async def pull_image(client: PodmanClient, image: str) -> None:
    if not image.startswith(INTERACTEM_IMAGE_REGISTRY) and image != VECTOR_IMAGE:
        _msg = f"Image {image} is not from the interactem registry ({INTERACTEM_IMAGE_REGISTRY})."
        logger.error(_msg)
        raise RuntimeError(_msg)

    async with IMAGE_PULL_LOCK:
        try:
            logger.info(f"Pulling image {image}...")
            await to_thread.run_sync(client.images.pull, image)
            logger.info(f"Successfully pulled image {image}")
        except Exception as e:
            error_msg = f"Failed to pull image {image}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e


async def ensure_image_present(client: PodmanClient, image: str) -> None:
    try:
        await to_thread.run_sync(client.images.get, image)
        logger.debug(f"Image {image} is already available")
    except podman.errors.exceptions.ImageNotFound:
        logger.info(f"Image {image} not found locally, attempting to pull...")
        await pull_image(client, image)


async def create_container(
    agent_id: uuid.UUID,
    client: PodmanClient,
    operator: AgentRuntimeOperator,
    deployment_id: uuid.UUID,
) -> Container:
    op_name = f"operator-{operator.id}"
    network_mode = operator.network_mode or "host"

    # Logs save to file so we can extract using vector
    log_config = {
        "Type": "k8s-file",
        "Config": {"path": f"{cfg.LOG_DIR}/{deployment_id}/op-{operator.id}.log"},
    }

    await ensure_image_present(client, operator.image)

    for attempt in stamina.retry_context(on=is_name_conflict_error):
        # Expand users
        # This should only be done at the agent (where data resides)
        with attempt:
            if attempt.num > 1:
                await handle_name_conflict(client, op_name)

            create_kwargs: dict[str, object] = {}
            if not cfg.LOCAL and operator.requires_gpus:
                create_kwargs["gpu"] = True

            return client.containers.create(
                image=operator.image,
                environment=operator.env,
                name=op_name,
                command=operator.command,
                detach=True,
                stdout=True,
                stderr=True,
                log_config=log_config,
                network_mode=network_mode,
                remove=True,
                labels={"agent.id": str(agent_id)},
                mounts=[mount.model_dump() for mount in operator.all_mounts],
                **create_kwargs,
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
            await to_thread.run_sync(container.stop)
            for attempt in stamina.retry_context(on=ContainerStillRunning):
                with attempt:
                    container.reload()
                    if container.status == "running":
                        raise ContainerStillRunning(
                            f"Container {container.name} is still running"
                        )

        logger.info(f"Removing container {container.name}")
        await to_thread.run_sync(functools.partial(container.remove, force=True))
        logger.info(f"Container {container.name} removed successfully")
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
