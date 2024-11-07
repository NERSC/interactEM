import asyncio
import json
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
from nats.js.api import (
    ConsumerConfig,
    DeliverPolicy,
    StreamConfig,
    StreamInfo,
)
from nats.js.kv import KeyValue
from pydantic import ValidationError

from core.constants import (
    BUCKET_METRICS,
    BUCKET_METRICS_TTL,
    BUCKET_OPERATORS,
    BUCKET_OPERATORS_TTL,
    OPERATOR_ID_ENV_VAR,
    STREAM_METRICS,
    STREAM_OPERATORS,
    STREAM_PARAMETERS,
    STREAM_PARAMETERS_UPDATE,
)
from core.logger import get_logger
from core.models import CommBackend, OperatorJSON, PipelineJSON
from core.models.messages import BytesMessage, OperatorTrackingMetadata
from core.models.operators import OperatorMetrics, OperatorTiming
from core.nats import create_bucket_if_doesnt_exist, create_or_update_stream
from core.pipeline import Pipeline

from .config import cfg
from .messengers.base import (
    BaseMessenger,
)
from .messengers.zmq import ZmqMessenger

logger = get_logger("operator", "DEBUG")

BACKEND_TO_MESSENGER: dict[CommBackend, type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}

OPERATOR_ID = os.getenv(OPERATOR_ID_ENV_VAR)


dependencies_funcs: list[Callable[[], Generator[None, None, None]]] = []


def dependencies(
    func: Callable[[], Generator[None, None, None]],
) -> Callable[[], Generator[None, None, None]]:
    dependencies_funcs.append(func)
    return func


async def receive_pipeline(msg: NATSMsg) -> Pipeline | None:
    await msg.ack()

    try:
        event = PipelineJSON.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        return None
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
        self.id = UUID(OPERATOR_ID)
        if not self.id:
            raise ValueError("Operator ID not set")
        self.messenger: BaseMessenger | None = None
        self.pipeline: Pipeline | None = None
        self.info: OperatorJSON | None = None
        self.nc: NATSClient | None = None
        self.js: JetStreamContext | None = None
        self.operators_kv: KeyValue | None = None
        self.messenger_task: asyncio.Task | None = None
        self.update_kv_task: asyncio.Task | None = None
        self.parameters: dict[str, Any] = {}
        self.metrics: OperatorMetrics = OperatorMetrics(
            id=self.id, timing=OperatorTiming()
        )
        self.metrics_stream: StreamInfo | None = None
        self.run_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._dependencies = []

    @property
    def input_queue(self) -> str:
        return str(self.id)

    async def start(self):
        logger.info(f"Starting operator {self.id}...")
        await self.execute_dependencies_startup()
        await self.setup_signal_handlers()
        await self.connect_to_nats()
        try:
            await self.initialize_pipeline()
        except ValueError as e:
            logger.error(e)
            self._shutdown_event.set()
            return
        await self.setup_key_value_store()
        await self.initialize_messenger()
        if not self.messenger:
            raise ValueError("Messenger not initialized")
        await self.messenger.start(self.pipeline)
        self.update_kv_task = asyncio.create_task(self.update_kv())
        self.run_task = asyncio.create_task(self.run())
        self.consume_params_task = asyncio.create_task(self.consume_params())
        await self._shutdown_event.wait()
        await self.shutdown()

    async def execute_dependencies_startup(self):
        for func in dependencies_funcs:
            gen = func()
            self._dependencies.append(gen)
            await gen.__next__() if asyncio.iscoroutinefunction(func) else next(gen)

    async def connect_to_nats(self):
        logger.info(f"Connecting to NATS at {cfg.NATS_SERVER_URL}...")
        self.nc = await nats.connect(
            servers=[str(cfg.NATS_SERVER_URL)], name=f"operator-{self.id}"
        )
        logger.info("Connected to NATS...")
        self.js = self.nc.jetstream()
        stream_cfg = StreamConfig(
            name=STREAM_METRICS,
            description="A stream for message metrics.",
            subjects=[f"{STREAM_METRICS}.>"],
        )
        self.metrics_stream = await create_or_update_stream(stream_cfg, self.js)

        stream_cfg = StreamConfig(
            name=STREAM_PARAMETERS,
            description="A stream for operator parameters.",
            subjects=[f"{STREAM_PARAMETERS}.>"],
        )
        self.params_stream = await create_or_update_stream(stream_cfg, self.js)

        retries = 10
        while retries > 0:
            try:
                self.params_psub = await self.js.pull_subscribe(
                    stream=STREAM_PARAMETERS,
                    subject=f"{STREAM_PARAMETERS}.{self.id}.>",
                    config=ConsumerConfig(
                        description=f"operator-{self.id}",
                        # Use to get the last message for each parameter
                        deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
                    ),
                )
                break
            # This happens when consumer is already attached to this stream
            # Shouldn't happen in production (UIDs are unique), but happens if
            # spawning test pipelines one after another quickly
            except nats.js.errors.BadRequestError as e:
                if e.code == 400 and e.err_code == 10100:
                    logger.warning(f"Consumer name weirdness: {e}. Retrying...")
                    retries -= 1
                    await asyncio.sleep(1)
                    if retries == 0:
                        raise e
                    continue

    async def initialize_pipeline(self):
        logger.info(
            f"Subscribing to stream '{STREAM_OPERATORS}' for operator {self.id}..."
        )
        # TODO: look at policies on this stream
        consumer_cfg = ConsumerConfig(
            description=f"operator-{self.id}",
            deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
        )
        if not self.js:
            raise ValueError("JetStream context not initialized")
        psub = await self.js.pull_subscribe(
            stream=STREAM_OPERATORS,
            subject=f"{STREAM_OPERATORS}.{self.id}",
            config=consumer_cfg,
        )
        try:
            msg = await psub.fetch(1)
        except nats.errors.TimeoutError:
            raise ValueError("No pipeline message received")
        self.pipeline = await receive_pipeline(msg[0])
        if self.pipeline is None:
            raise ValueError("Pipeline not found")
        await psub.unsubscribe()
        self.info = self.pipeline.get_operator(self.id)
        if self.info.parameters is not None:
            self.parameters = {p.name: p.default for p in self.info.parameters}
        logger.info(f"Operator {self.id} initialized with parameters {self.parameters}")
        asyncio.create_task(self.publish_parameters())
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

    async def publish_parameters(self):
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return
        tasks = []
        for name, val in self.parameters.items():
            logger.info(
                f"Publishing {name}, {val} on subject: {STREAM_PARAMETERS_UPDATE}.{self.id}.{name}"
            )
            tasks.append(
                asyncio.create_task(
                    self.js.publish(
                        subject=f"{STREAM_PARAMETERS_UPDATE}.{self.id}.{name}",
                        payload=str(val).encode(),
                    )
                )
            )
        logger.info(f"Published parameters for operator {self.id}...")
        await asyncio.gather(*tasks)

    async def consume_params(self):
        while not self._shutdown_event.is_set():
            try:
                await self.params_psub.consumer_info()
            except Exception as e:
                logger.info(f"Consumer info error: {e}")
            try:
                msgs = await self.params_psub.fetch(20, timeout=1)
            except nats.errors.TimeoutError:
                continue

            if not msgs:
                continue

            # Only use the last parameter from frontend
            for msg in msgs:
                if not msg.data:
                    logger.warning(f"Received empty message for operator {self.id}")
                    await msg.term()  # terminate sending this message
                    continue

                parameter_name = msg.subject.split(".")[-1]
                if parameter_name not in self.parameters:
                    logger.warning(
                        f"Received message for unknown parameter {parameter_name}"
                    )
                    continue
                try:
                    # We want to update, not overwrite
                    # TODO: we need some way of validating parameters and typing them
                    self.parameters.update(json.loads(msg.data.decode()))
                    logger.info(
                        f"Updating {parameter_name} to {self.parameters[parameter_name]}..."
                    )
                    asyncio.create_task(msg.ack())
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding param update: {e}")
                    await msg.term()
                    pass
            asyncio.create_task(self.publish_parameters())

    async def update_kv(self):
        while not self._shutdown_event.is_set():
            try:
                timing = OperatorTiming.model_validate(self.metrics.timing)
                metrics = OperatorMetrics(id=self.id, timing=timing)
            except ValidationError:
                await asyncio.sleep(1)
                continue
            await self.metrics_kv.put(str(self.id), metrics.model_dump_json().encode())
            await asyncio.sleep(1)

    async def setup_key_value_store(self):
        logger.info(f"Setting up Key-Value store for operator {self.id}...")
        if not self.js:
            raise ValueError("JetStream context not initialized")
        self.operators_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
        )
        self.metrics_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_METRICS, BUCKET_METRICS_TTL
        )

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
        if not self.messenger:
            raise ValueError("Messenger not initialized")
        has_input_op = True if len(self.messenger.input_ports) > 0 else False
        loop_counter = 0
        while not self._shutdown_event.is_set():
            coros: list[Coroutine] = []
            msg = None
            _tracking = None

            if has_input_op:
                msg = await self.messenger.recv()
                if not msg:
                    continue
                _tracking = msg.header.tracking

            inject_tracking: bool = loop_counter % 100 == 0 and not has_input_op
            timing = inject_tracking or _tracking is not None
            before_kernel = datetime.now() if timing else None
            processed_msg = await self.run_kernel(msg, self.parameters)
            after_kernel = datetime.now() if timing else None

            if processed_msg:
                processed_msg.header.tracking = _tracking
                if timing:
                    self._update_metrics(processed_msg, before_kernel, after_kernel)
                if self.messenger.output_ports:
                    await self.messenger.send(processed_msg)
                elif timing:
                    coros.append(self._publish_metrics(processed_msg))

            if not processed_msg and _tracking:
                coros.append(
                    self._update_and_publish_metrics(msg, before_kernel, after_kernel)
                )

            if timing:
                self.metrics.timing.after_send = datetime.now()
                self.metrics.timing.before_kernel = before_kernel
                self.metrics.timing.after_kernel = after_kernel

            if coros:
                # TODO: possibly create tasks instead
                await asyncio.gather(*coros)

            loop_counter += 1

    async def _publish_metrics(self, msg: BytesMessage):
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return
        if not msg or not msg.header.tracking:
            logger.warning("Message or tracking data incomplete...")
            return
        await self.js.publish(
            subject=f"{STREAM_METRICS}.operators",
            payload=msg.header.model_dump_json().encode(),
        )

    def _update_metrics(
        self,
        msg: BytesMessage | None,
        before_kernel: datetime | None,
        after_kernel: datetime | None,
    ) -> BytesMessage | None:
        if not msg or not before_kernel or not after_kernel:
            logger.warning("Message or tracking data incomplete...")
            return

        meta = OperatorTrackingMetadata(
            id=self.id,
            time_before_operate=before_kernel,
            time_after_operate=after_kernel,
        )
        if msg.header.tracking is None:
            msg.header.tracking = []
        msg.header.tracking.append(meta)
        return msg

    async def _update_and_publish_metrics(
        self,
        msg: BytesMessage | None,
        before_kernel: datetime | None,
        after_kernel: datetime | None,
    ):
        if not self.js:
            logger.warning("JetStream context not initialized...")
            return

        msg = self._update_metrics(msg, before_kernel, after_kernel)
        if not msg:
            return

        await self._publish_metrics(msg)

class Operator(OperatorMixin, OperatorInterface):
    pass

class AsyncOperator(OperatorMixin, AsyncOperatorInterface):
    pass


Parameters = dict[str, Any]

KernelFn = Callable[
    [BytesMessage | None, Parameters],
    BytesMessage | None,
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
    func: KernelFn | None = None,
    start: bool = False,
) -> Any:
    def decorator(func: KernelFn) -> Callable[[], Operator]:
        @wraps(func)
        def wrapper():
            @wraps(func)
            async def kernel(_, *args, **kwargs):
                return await func(*args, **kwargs)

            name = func.__name__
            class_name = f"{name.capitalize()}Operator"
            OpClass = type(class_name, (AsyncOperator,), {"kernel": kernel})

            obj = OpClass()

            if start:
                asyncio.create_task(obj.start())

            return obj

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator
