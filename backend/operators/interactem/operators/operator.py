import asyncio
import os
import signal
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Generator
from datetime import datetime
from functools import wraps
from typing import Any
from uuid import UUID

import nats
import nats.errors
import nats.js
import nats.js.errors
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.constants import (
    MOUNT_DIR,
    NATS_TIMEOUT_DEFAULT,
    OPERATOR_CLASS_NAME,
    OPERATOR_ID_ENV_VAR,
)
from interactem.core.logger import get_logger
from interactem.core.models import CommBackend
from interactem.core.models.kvs import (
    OperatorStatus,
    OperatorVal,
)
from interactem.core.models.messages import BytesMessage, OperatorTrackingMetadata
from interactem.core.models.metrics import OperatorMetrics, OperatorTiming
from interactem.core.models.runtime import (
    RuntimeOperator,
    RuntimeOperatorParameterUpdate,
    RuntimeParameterCollection,
    RuntimeParameterCollectionType,
    RuntimePipeline,
)
from interactem.core.nats import (
    nc,
)
from interactem.core.nats.consumers import (
    create_operator_parameter_consumer,
    create_operator_pipeline_consumer,
)
from interactem.core.nats.kv import InteractemBucket, KeyValueLoop
from interactem.core.nats.publish import (
    publish_operator_parameter_ack,
    publish_pipeline_metrics,
)
from interactem.core.pipeline import Pipeline
from interactem.core.util import create_task_with_ref

from .config import cfg
from .messengers.base import (
    BaseMessenger,
)
from .messengers.zmq import ZmqMessenger

logger = get_logger()

BACKEND_TO_MESSENGER: dict[CommBackend, type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}

OPERATOR_ID = UUID(os.getenv(OPERATOR_ID_ENV_VAR))
assert OPERATOR_ID, "Operator ID not set in environment variables"


dependencies_funcs: list[Callable[[], Generator[None, None, None]]] = []


def dependencies(
    func: Callable[[], Generator[None, None, None]],
) -> Callable[[], Generator[None, None, None]]:
    dependencies_funcs.append(func)
    return func


async def receive_pipeline(msg: NATSMsg) -> Pipeline:
    await msg.ack()

    try:
        event = RuntimePipeline.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        raise
    return Pipeline.from_pipeline(event)


class RunnableKernel(ABC):
    @abstractmethod
    async def run_kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> BytesMessage | None:
        pass


class AsyncOperatorInterface(RunnableKernel):
    @abstractmethod
    async def kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
    ) -> BytesMessage | None:
        pass

    async def run_kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> BytesMessage | None:
        return await self.kernel(inputs, parameters)


class OperatorInterface(RunnableKernel):
    @abstractmethod
    def kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
    ) -> BytesMessage | None:
        pass

    async def run_kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> BytesMessage | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.kernel, inputs, parameters)


class OperatorMixin(RunnableKernel):
    def __init__(self):
        self.id = OPERATOR_ID
        self.messenger: BaseMessenger | None = None
        self.pipeline: Pipeline | None = None
        self.info: RuntimeOperator | None = None
        self.nc: NATSClient | None = None
        self.js: JetStreamContext | None = None
        self.messenger_task: asyncio.Task | None = None
        self.metrics_kv: KeyValueLoop[OperatorMetrics] | None = None
        self.operator_kv: KeyValueLoop[OperatorVal] | None = None
        self.val: OperatorVal | None = None
        self.parameters = RuntimeParameterCollection(
            type=RuntimeParameterCollectionType.OPERATOR
        )
        self.metrics: OperatorMetrics | None = None
        self.run_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._dependencies = []
        self._last_tracking_time: datetime = datetime.now()
        self._tracking_interval: float = 1.0
        self._tracking_ready: asyncio.Event = asyncio.Event()
        self._tracking_timer_task: asyncio.Task | None = None
        self._task_refs: set[asyncio.Task] = set()

    @property
    def input_queue(self) -> str:
        return str(self.id)

    async def start(self):
        logger.info(f"Starting operator {self.id}...")
        await self.execute_dependencies_startup()
        await self.setup_signal_handlers()
        self.nc, self.js = await self.connect_to_nats()

        # Initialize pipeline/operator information
        await self.initialize_pipeline()
        assert self.pipeline, "Pipeline not initialized"
        self.info = await self.initialize_operator()
        assert self.info, "Operator info not initialized"
        await self.initialize_parameters()
        self.publish_parameters()

        # Setup KV stores
        self.metrics_kv = KeyValueLoop[OperatorMetrics](
            self.nc,
            self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.METRICS,
            update_interval=1.0,
            data_model=OperatorMetrics,
        )
        self.metrics = OperatorMetrics(
            id=self.id,
            canonical_id=self.info.canonical_id,
            timing=OperatorTiming(),
        )
        self.metrics_kv.add_or_update_value(self.metrics.key(), self.metrics)
        await self.metrics_kv.start()
        self.operator_kv = KeyValueLoop[OperatorVal](
            self.nc,
            self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.STATUS,
            update_interval=5.0,
            data_model=OperatorVal,
        )
        self.val = OperatorVal(
            id=self.id,
            canonical_id=self.info.canonical_id,
            status=OperatorStatus.INITIALIZING,
            runtime_pipeline_id=self.pipeline.id,
            canonical_pipeline_id=self.pipeline.canonical_id,
        )
        self.operator_kv.add_or_update_value(self.val.key(), self.val)
        await self.operator_kv.start()
        await self.operator_kv.update_now()

        # Initialize messenger
        await self.initialize_messenger()
        assert self.messenger, "Messenger not initialized"
        await self.messenger.start(self.pipeline)

        # Start ur engines
        self._tracking_timer_task = asyncio.create_task(self._tracking_timer())
        self.run_task = asyncio.create_task(self.run())
        self.consume_params_task = asyncio.create_task(self.consume_params())
        self.val.status = OperatorStatus.RUNNING
        await self.operator_kv.update_now()
        await self._shutdown_event.wait()
        await self.shutdown()

    async def execute_dependencies_startup(self):
        for func in dependencies_funcs:
            gen = func()
            self._dependencies.append(gen)
            await gen.__next__() if asyncio.iscoroutinefunction(func) else next(gen)

    async def connect_to_nats(self) -> tuple[NATSClient, JetStreamContext]:
        logger.info(f"Connecting to NATS at {cfg.NATS_SERVER_URL}...")
        self.nc = await nc(
            servers=[str(cfg.NATS_SERVER_URL)], name=f"operator-{self.id}"
        )
        logger.info("Connected to NATS...")
        self.js = self.nc.jetstream()
        return self.nc, self.js

    async def initialize_pipeline(self):
        if not self.js:
            raise ValueError("JetStream context not initialized")
        psub = await create_operator_pipeline_consumer(self.js, self.id)
        try:
            msg = await psub.fetch(1)
        except nats.errors.TimeoutError:
            raise RuntimeError("No pipeline message received")
        self.pipeline = await receive_pipeline(msg[0])
        await psub.unsubscribe()

    async def initialize_operator(self) -> RuntimeOperator:
        if not self.pipeline:
            raise ValueError("Pipeline not initialized.")

        self.info = self.pipeline.get_operator(self.id)
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

        return self.info

    async def initialize_parameters(self):
        if not self.info:
            raise ValueError("Operator info not initialized.")
        if not self.info.parameters:
            logger.info("No parameters to initialize for operator.")
            return

        self.parameters = RuntimeParameterCollection.from_parameter_list(
            self.info.parameters, RuntimeParameterCollectionType.OPERATOR
        )
        logger.info(f"Operator {self.id} initialized with parameters")

    def publish_parameters(self):
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return
        if not self.info:
            logger.warning("Operator info not initialized...")
            return
        if not self.info.parameters:
            logger.info("No parameters to publish...")
            return
        for param in self.parameters.parameters.values():
            create_task_with_ref(
                self._task_refs,
                publish_operator_parameter_ack(self.js, self.info.canonical_id, param),
            )
        logger.info(f"Publishing parameters for operator {self.id}...")

    async def consume_params(self):
        if not self.js:
            raise ValueError("JetStream context not initialized")
        if not self.info:
            raise ValueError("Operator info not initialized")

        self.params_psub = await create_operator_parameter_consumer(
            self.js, self.info.canonical_id
        )

        while not self._shutdown_event.is_set():
            msgs = None
            try:
                msgs = await self.params_psub.fetch(1, timeout=NATS_TIMEOUT_DEFAULT)
            except nats.js.errors.FetchTimeoutError:
                # If we can't get any messages, we just continue
                continue
            except nats.errors.Error:
                # If we can't fetch messages for a nats error, then we
                # try to reinitialize the consumer
                # TODO: this could be done elsewhere...
                # note, we want to make sure we aren't doing this every loop.
                self.params_psub = await create_operator_parameter_consumer(
                    self.js, self.info.canonical_id
                )
                continue
            except Exception as e:
                logger.error(f"Error fetching parameter messages: {e}")
                continue

            if not msgs:
                continue

            # Process parameter updates
            for msg in msgs:
                try:
                    update = RuntimeOperatorParameterUpdate.model_validate_json(
                        msg.data
                    )
                    # Use the parameter collection's update method
                    self.parameters.update_value(update.name, update.value)

                    # Also update the operator info parameter list for consistency
                    if self.info:
                        self.info.update_parameter_value(update.name, update.value)

                except (ValidationError, KeyError) as e:
                    logger.error(f"Parameter update failed: {e}")
                    await msg.term()

                create_task_with_ref(self._task_refs, msg.ack())

            self.publish_parameters()

    async def initialize_messenger(self):
        # TODO: put this somewhere else
        comm_backend = CommBackend.ZMQ
        messenger_cls = BACKEND_TO_MESSENGER.get(comm_backend)
        if messenger_cls is None:
            raise ValueError(f"Invalid communications backend: {comm_backend}")
        if not self.js:
            raise ValueError("JetStream context not initialized")
        self.messenger = messenger_cls(self.id, self.js)
        logger.info(f"Initialized messenger {self.messenger}...")

    async def shutdown(self):
        self.val.status = OperatorStatus.SHUTTING_DOWN
        await self.operator_kv.update_now()
        logger.info(f"Shutting down operator {self.id}...")

        await self.execute_dependencies_teardown()

        if self.run_task:
            self.run_task.cancel()
            try:
                await self.run_task
            except asyncio.CancelledError:
                logger.info("Run task cancelled")

        if self.messenger:
            logger.info(f"Stopping messenger {self.messenger}...")
            await self.messenger.stop()

        if self.consume_params_task:
            self.consume_params_task.cancel()
            try:
                await self.consume_params_task
            except asyncio.CancelledError:
                logger.info("Consume paramaters task cancelled")

        if self.params_psub:
            await self.params_psub.unsubscribe()
            logger.info("Unsubscribed from parameters stream")

        if self.nc:
            logger.info("Closing NATS connection...")
            await self.nc.close()

        logger.info(f"Operator {self.id} shutdown complete")

    async def execute_dependencies_teardown(self):
        for gen in reversed(self._dependencies):
            try:
                await gen.__next__() if asyncio.iscoroutinefunction(gen) else next(gen)
            except StopIteration:
                pass

    # TODO: refactor into core
    async def setup_signal_handlers(self):
        logger.info("Setting up signal handlers...")

        loop = asyncio.get_running_loop()

        def handle_signal():
            logger.info("Signal received, shutting down processes...")
            self._shutdown_event.set()

        loop.add_signal_handler(signal.SIGINT, handle_signal)
        loop.add_signal_handler(signal.SIGTERM, handle_signal)

    async def run(self):
        assert self.messenger, "Messenger not initialized"
        assert self.js, "JetStream context not initialized"
        assert self.val, "Operator value not initialized"
        assert self.operator_kv, "Operator KV not initialized"
        assert self.metrics, "Operator metrics not initialized"

        has_input = True if len(self.messenger.input_ports) > 0 else False
        error_count, max_retries, error_state = 0, 10, False
        self.val.status = OperatorStatus.RUNNING
        await self.operator_kv.update_now()
        while not self._shutdown_event.is_set():
            tasks: list[Coroutine] = []
            msg = None
            _tracking = None
            timing_this_iter = False
            before_kernel = None
            after_kernel = None

            if has_input:
                msg = await self.messenger.recv()
                if not msg:
                    continue
                # inject metrics if has input and there is tracking info in the header
                _tracking = msg.header.tracking
                timing_this_iter = True if _tracking is not None else False
            # if it doesn't have input, we inject every tracking interval (seconds)
            elif not has_input and self._tracking_ready.is_set():
                self._tracking_ready.clear()
                self._last_tracking_time = datetime.now()
                timing_this_iter = True

            if timing_this_iter:
                before_kernel = datetime.now()

            try:
                processed_msg = await self.run_kernel(msg, self.parameters.values)
                error_count = 0
            except Exception as e:
                logger.exception(f"Error in kernel: {e}")
                if not error_state:
                    error_state = True
                    self.val.add_error(str(e))
                    await self.operator_kv.update_now()

                error_count += 1
                if error_count >= max_retries:
                    logger.error("Too many errors, shutting down...")
                    self._shutdown_event.set()

                continue

            if timing_this_iter:
                after_kernel = datetime.now()

            # if we were previously in error state and successfully processed a message
            # we need to publish that we are running again
            if error_state and processed_msg:
                error_state = False
                self.val.clear_errors()
                await self.operator_kv.update_now()

            if processed_msg:
                processed_msg.header.tracking = _tracking
                if timing_this_iter:
                    self._update_metrics(processed_msg, before_kernel, after_kernel)
                if self.messenger.output_ports:
                    await self.messenger.send(processed_msg)
                # if last operator in pipeline, publish tracking information
                elif timing_this_iter:
                    tasks.append(self._publish_pipeline_metrics(processed_msg))
            elif timing_this_iter and msg:
                tasks.append(
                    self._update_and_publish_pipeline_metrics(
                        msg, before_kernel, after_kernel
                    )
                )

            if timing_this_iter:
                self.metrics.timing.after_send = datetime.now()
                self.metrics.timing.before_kernel = before_kernel
                self.metrics.timing.after_kernel = after_kernel

            for task in tasks:
                create_task_with_ref(self._task_refs, task)

    async def _tracking_timer(self):
        """Task that periodically sets the tracking flag."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self._tracking_interval)
            self._tracking_ready.set()

    async def _publish_pipeline_metrics(self, msg: BytesMessage):
        """These are the metrics from the tracking information
        that should be sent through the full pipeline."""
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return
        if not msg.header.tracking:
            logger.warning("No tracking data in message to publish...")
            return

        await publish_pipeline_metrics(self.js, msg)

    def _update_metrics(
        self,
        msg: BytesMessage,
        before_kernel: datetime | None,
        after_kernel: datetime | None,
    ) -> BytesMessage:
        if before_kernel is None or after_kernel is None:
            logger.warning("Tracking data incomplete...")
            return msg

        meta = OperatorTrackingMetadata(
            id=self.id,
            time_before_operate=before_kernel,
            time_after_operate=after_kernel,
        )
        if msg.header.tracking is None:
            msg.header.tracking = []
        msg.header.tracking.append(meta)
        return msg

    async def _update_and_publish_pipeline_metrics(
        self,
        msg: BytesMessage,
        before_kernel: datetime | None,
        after_kernel: datetime | None,
    ):
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return

        msg = self._update_metrics(msg, before_kernel, after_kernel)
        if not msg:
            return

        await self._publish_pipeline_metrics(msg)


class Operator(OperatorMixin, OperatorInterface):
    pass


class AsyncOperator(OperatorMixin, AsyncOperatorInterface):
    pass


Parameters = dict[str, Any]

KernelFn = Callable[
    [BytesMessage | None, Parameters],
    BytesMessage | None,
]

AsyncKernelFn = Callable[
    [BytesMessage | None, Parameters],
    Coroutine[Any, Any, BytesMessage | None],
]

def operator(
    func: KernelFn | None = None,
    start: bool = False,
) -> Any:
    def decorator(func: KernelFn) -> Callable[[], Operator]:
        @wraps(func)
        def wrapper():
            @wraps(func)
            def kernel(_, *args, **kwargs):
                return func(*args, **kwargs)

            name = func.__name__
            class_name = f"{name.capitalize()}Operator"
            OpClass = type(class_name, (Operator,), {"kernel": kernel})

            obj = OpClass()

            if start:
                asyncio.create_task(obj.start())

            return obj

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator


def async_operator(
    func: AsyncKernelFn | None = None,
    start: bool = False,
) -> Any:
    def decorator(func: AsyncKernelFn) -> Callable[[], AsyncOperator]:
        @wraps(func)
        def wrapper():
            @wraps(func)
            async def kernel(_, *args, **kwargs):
                return await func(*args, **kwargs)

            name = func.__name__
            class_name = f"{name.capitalize()}{OPERATOR_CLASS_NAME}"
            OpClass = type(class_name, (AsyncOperator,), {"kernel": kernel})

            obj = OpClass()

            if start:
                asyncio.create_task(obj.start())

            return obj

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator


DATA_DIRECTORY = MOUNT_DIR
