import asyncio
import inspect
import os
import signal
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Generator
from datetime import datetime
from functools import partial, wraps
from typing import Any
from uuid import UUID

import anyio
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
    OPERATOR_CLASS_NAME,
    OPERATOR_ID_ENV_VAR,
    SUBJECT_OPERATORS_TRIGGERS,
)
from interactem.core.logger import get_logger
from interactem.core.models import CommBackend
from interactem.core.models.kvs import (
    OperatorStatus,
    OperatorVal,
)
from interactem.core.models.messages import (
    BytesMessage,
    OperatorTrackingMetadata,
    TrackingMetadatas,
)
from interactem.core.models.metrics import OperatorMetrics, OperatorTiming
from interactem.core.models.runtime import (
    RuntimeOperator,
    RuntimeOperatorParameterUpdate,
    RuntimeParameterCollection,
    RuntimeParameterCollectionType,
    RuntimePipeline,
)
from interactem.core.models.spec import (
    OperatorSpecTrigger,
    TriggerInvocationMode,
)
from interactem.core.models.triggers import (
    TriggerInvocation,
    TriggerInvocationRequest,
    TriggerInvocationResponseStatus,
)
from interactem.core.nats import (
    consume_messages,
    nc,
    respond_trigger,
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
from interactem.core.util import BaseExceptionGroup, create_task_with_ref

from .config import cfg
from .messengers.base import (
    BaseMessenger,
)
from .messengers.zeromq.messenger import ZmqMessenger

logger = get_logger()

BACKEND_TO_MESSENGER: dict[CommBackend, type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}

OPERATOR_ID = UUID(os.getenv(OPERATOR_ID_ENV_VAR))
assert OPERATOR_ID, "Operator ID not set in environment variables"

OPERATOR_STATUS_UPDATE_INTERVAL = 1.0  # seconds
OPERATOR_METRICS_UPDATE_INTERVAL = 1.0  # seconds


dependencies_funcs: list[Callable[[], Generator[None, None, None]]] = []


def dependencies(
    func: Callable[[], Generator[None, None, None]],
) -> Callable[[], Generator[None, None, None]]:
    dependencies_funcs.append(func)
    return func


def _kernel_accepts_trigger(func: Callable[..., Any]) -> bool:
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if param.name == "trigger":
            return True
    return False


def _call_kernel_sync(
    kernel_func: Callable[..., BytesMessage | None],
    inputs: BytesMessage | None,
    parameters: dict[str, Any],
    trigger: TriggerInvocation | None = None,
    accepts_trigger: bool = False,
) -> BytesMessage | None:
    if trigger is not None and accepts_trigger:
        return kernel_func(inputs, parameters, trigger=trigger)
    return kernel_func(inputs, parameters)


async def _call_kernel_async(
    kernel_func: Callable[..., Coroutine[Any, Any, BytesMessage | None]],
    inputs: BytesMessage | None,
    parameters: dict[str, Any],
    trigger: TriggerInvocation | None = None,
    accepts_trigger: bool = False,
) -> BytesMessage | None:
    if trigger is not None and accepts_trigger:
        return await kernel_func(inputs, parameters, trigger=trigger)
    return await kernel_func(inputs, parameters)


async def receive_pipeline(msg: NATSMsg) -> Pipeline:
    await msg.ack()

    try:
        event = RuntimePipeline.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        raise
    return Pipeline.from_pipeline(event)


class RunnableKernel(ABC):
    _kernel_accepts_trigger_arg: bool = False

    @abstractmethod
    async def run_kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
        trigger: TriggerInvocation | None = None,
    ) -> BytesMessage | None:
        pass


class AsyncOperatorInterface(RunnableKernel):
    @abstractmethod
    async def kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
        trigger: TriggerInvocation | None = None,
    ) -> BytesMessage | None:
        pass

    async def run_kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
        trigger: TriggerInvocation | None = None,
    ) -> BytesMessage | None:
        return await _call_kernel_async(
            self.kernel,
            inputs,
            parameters,
            trigger=trigger,
            accepts_trigger=self._kernel_accepts_trigger_arg,
        )


class OperatorInterface(RunnableKernel):
    @abstractmethod
    def kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
        trigger: TriggerInvocation | None = None,
    ) -> BytesMessage | None:
        pass

    async def run_kernel(
        self,
        inputs: BytesMessage | None,
        parameters: dict[str, Any],
        trigger: TriggerInvocation | None = None,
    ) -> BytesMessage | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            _call_kernel_sync,
            self.kernel,
            inputs,
            parameters,
            trigger,
            self._kernel_accepts_trigger_arg,
        )


class OperatorMixin(RunnableKernel):
    # Provided by OperatorInterface/AsyncOperatorInterface concrete subclasses
    kernel: Callable[..., Any]

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
        self.params_psub: JetStreamContext.PullSubscription | None = None
        self.trigger_sub = None
        self._has_triggers: bool = False
        self._trigger_map: dict[str, OperatorSpecTrigger] = {}
        self._kernel_lock = asyncio.Lock()
        self._kernel_accepts_trigger_arg = _kernel_accepts_trigger(self.kernel)

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
        self.initialize_triggers()

        # Setup KV stores
        self.metrics_kv = KeyValueLoop[OperatorMetrics](
            self.nc,
            self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.METRICS,
            update_interval=OPERATOR_METRICS_UPDATE_INTERVAL,
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
            update_interval=OPERATOR_STATUS_UPDATE_INTERVAL,
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
        self.val.status = OperatorStatus.RUNNING
        await self.operator_kv.update_now()

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._tracking_timer)
                tg.start_soon(self.run)
                tg.start_soon(self.consume_params)
                tg.start_soon(self.consume_triggers)
                await self._shutdown_event.wait()
                tg.cancel_scope.cancel()
        except BaseExceptionGroup as eg:
            logger.exception(f"Task group encountered exceptions: {eg}")

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

    def initialize_triggers(self):
        assert self.info, "Operator info not initialized"
        self._has_triggers = bool(self.info.triggers)
        if self._has_triggers:
            self._trigger_map = {
                trigger.name: trigger for trigger in self.info.triggers or []
            }

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

    async def handle_parameter_update(self, msg: NATSMsg, js: JetStreamContext):
        """Handler for processing parameter update messages."""
        try:
            update = RuntimeOperatorParameterUpdate.model_validate_json(msg.data)
            # Use the parameter collection's update method
            self.parameters.update_value(update.name, update.value)

            # Also update the operator info parameter list for consistency
            if self.info:
                self.info.update_parameter_value(update.name, update.value)

            # Publish only the updated parameter instead of all parameters
            updated_param = self.parameters.parameters.get(update.name)
            if updated_param and self.info:
                logger.info(f"'{update.name}' updated to {update.value}")
                create_task_with_ref(
                    self._task_refs,
                    publish_operator_parameter_ack(
                        js, self.info.canonical_id, updated_param
                    ),
                )

        except (ValidationError, KeyError) as e:
            logger.error(f"Parameter update failed: {e}")
            await msg.term()
            return

        await msg.ack()

    async def consume_params(self):
        if not self.js:
            raise ValueError("JetStream context not initialized")
        if not self.info:
            raise ValueError("Operator info not initialized")

        create_consumer = partial(
            create_operator_parameter_consumer, self.js, self.info.canonical_id
        )
        self.params_psub = await create_consumer()

        await consume_messages(
            self.params_psub,
            self.handle_parameter_update,
            self.js,
            num_msgs=1,
            create_consumer=create_consumer,
        )

    async def handle_trigger_request(self, msg: NATSMsg):
        if not self.info:
            logger.warning("Not initialized yet")
            return

        try:
            request = TriggerInvocationRequest.model_validate_json(msg.data)
        except ValidationError:
            _err = "Invalid trigger request"
            logger.warning(_err)
            await respond_trigger(msg, TriggerInvocationResponseStatus.ERROR, _err)
            return

        trigger_spec = self._trigger_map.get(request.trigger)
        if not trigger_spec:
            _err = (
                f"Trigger '{request.trigger}' not found in spec for operator {self.info.image} "
                f"available triggers: {self.info.triggers}"
            )
            logger.warning(_err)
            await respond_trigger(msg, TriggerInvocationResponseStatus.ERROR, _err)
            return

        invocation = TriggerInvocation(
            canonical_operator_id=self.info.canonical_id,
            trigger=request.trigger,
        )

        drain_all = trigger_spec.mode == TriggerInvocationMode.DRAIN
        create_task_with_ref(self._task_refs, self._run_trigger(invocation, drain_all))
        await respond_trigger(
            msg, TriggerInvocationResponseStatus.OK, "Trigger accepted"
        )

    async def _run_trigger(self, invocation: TriggerInvocation, drain_all: bool):
        """Handle an out-of-band trigger request."""
        assert self.messenger, "Messenger not initialized"
        logger.info(f"Trigger received: {invocation.trigger}")
        while not self._shutdown_event.is_set():
            try:
                (
                    processed_msg,
                    before_kernel,
                    after_kernel,
                ) = await self._execute_kernel_with_timing(
                    None, invocation, track_metrics=True
                )
            except Exception as e:
                logger.exception(
                    f"Error while handling trigger {invocation.trigger}: {e}"
                )
                if self.val:
                    self.val.add_error(str(e))
                    if self.operator_kv:
                        await self.operator_kv.update_now()
                return

            tasks = await self._handle_processed_message(
                processed_msg,
                incoming_msg=None,
                tracking=None,
                before_kernel=before_kernel,
                after_kernel=after_kernel,
            )
            for task in tasks:
                await task

            if not drain_all or not processed_msg:
                return

    async def consume_triggers(self):
        if not self.nc:
            raise ValueError("NATS client not initialized")
        if not self.info:
            raise ValueError("Operator info not initialized")

        subject = f"{SUBJECT_OPERATORS_TRIGGERS}.{self.info.canonical_id}.>"
        self.trigger_sub = await self.nc.subscribe(
            subject, cb=self.handle_trigger_request
        )
        await self._shutdown_event.wait()

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

        if self.messenger:
            logger.info(f"Stopping messenger {self.messenger}...")
            await self.messenger.stop()

        if self.params_psub:
            await self.params_psub.unsubscribe()
            logger.info("Unsubscribed from parameters stream")

        if self.trigger_sub:
            await self.trigger_sub.unsubscribe()
            logger.info("Unsubscribed from trigger subject")

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

        if not has_input and self._has_triggers:
            logger.info("Operator is trigger-only. Main loop waiting for shutdown.")
            await self._shutdown_event.wait()
            return

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

            try:
                (
                    processed_msg,
                    before_kernel,
                    after_kernel,
                ) = await self._execute_kernel_with_timing(
                    msg, track_metrics=timing_this_iter
                )
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

            # if we were previously in error state and successfully processed a message
            # we need to publish that we are running again
            if error_state and processed_msg:
                error_state = False
                self.val.clear_errors()
                await self.operator_kv.update_now()

            tasks.extend(
                await self._handle_processed_message(
                    processed_msg,
                    incoming_msg=msg,
                    tracking=_tracking,
                    before_kernel=before_kernel if timing_this_iter else None,
                    after_kernel=after_kernel if timing_this_iter else None,
                )
            )
            for task in tasks:
                create_task_with_ref(self._task_refs, task)

    async def _tracking_timer(self):
        """Task that periodically sets the tracking flag."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self._tracking_interval)
            self._tracking_ready.set()

    async def _publish_pipeline_metrics(self, tracking: TrackingMetadatas | None):
        """These are the metrics from the tracking information
        that should be sent through the full pipeline."""
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return

        if not tracking:
            logger.warning(
                "Attempt to publish failing because tracking is non-existent. "
            )
            return

        await publish_pipeline_metrics(self.js, tracking)

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
            msg.header.tracking = TrackingMetadatas()
        msg.header.tracking.metadatas.append(meta)
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

        await self._publish_pipeline_metrics(msg.header.tracking)

    async def _execute_kernel_with_timing(
        self,
        inputs: BytesMessage | None,
        trigger: TriggerInvocation | None = None,
        track_metrics: bool = False,
    ) -> tuple[BytesMessage | None, datetime | None, datetime | None]:
        """Run kernel under lock, optionally collecting timing."""
        before_kernel = datetime.now() if track_metrics else None
        async with self._kernel_lock:
            processed_msg = await self.run_kernel(
                inputs, self.parameters.values, trigger=trigger
            )
        after_kernel = datetime.now() if track_metrics else None
        return processed_msg, before_kernel, after_kernel

    async def _handle_processed_message(
        self,
        processed_msg: BytesMessage | None,
        incoming_msg: BytesMessage | None,
        tracking: TrackingMetadatas | None,
        before_kernel: datetime | None,
        after_kernel: datetime | None,
    ) -> list[Coroutine[Any, Any, Any]]:
        tasks: list[Coroutine[Any, Any, Any]] = []
        timing_available = before_kernel is not None and after_kernel is not None

        if processed_msg:
            processed_msg.header.tracking = tracking
            if timing_available:
                processed_msg = self._update_metrics(
                    processed_msg, before_kernel, after_kernel
                )
                if self.metrics:
                    self.metrics.timing.before_kernel = before_kernel
                    self.metrics.timing.after_kernel = after_kernel

            if self.messenger and self.messenger.output_ports:
                await self.messenger.send(processed_msg)
                if timing_available and self.metrics:
                    self.metrics.timing.after_send = datetime.now()
            elif processed_msg.header.tracking:
                tasks.append(
                    self._publish_pipeline_metrics(processed_msg.header.tracking)
                )
                if timing_available and self.metrics:
                    self.metrics.timing.after_send = datetime.now()
        elif timing_available and incoming_msg:
            tasks.append(
                self._update_and_publish_pipeline_metrics(
                    incoming_msg, before_kernel, after_kernel
                )
            )
            if self.metrics:
                self.metrics.timing.before_kernel = before_kernel
                self.metrics.timing.after_kernel = after_kernel
                self.metrics.timing.after_send = datetime.now()

        return tasks


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
