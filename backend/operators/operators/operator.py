import asyncio
import os
import signal
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
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
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.kv import KeyValue
from pydantic import ValidationError

from core.constants import (
    BUCKET_METRICS,
    BUCKET_METRICS_TTL,
    BUCKET_OPERATORS,
    BUCKET_OPERATORS_TTL,
    OPERATOR_ID_ENV_VAR,
    STREAM_OPERATORS,
)
from core.logger import get_logger
from core.models import CommBackend, OperatorJSON, PipelineJSON
from core.models.operators import OperatorMetrics, OperatorTiming
from core.nats import create_bucket_if_doesnt_exist
from core.pipeline import Pipeline

from .config import cfg
from .messengers.base import BaseMessenger, BytesMessage
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


async def receive_pipeline(msg: NATSMsg, js: JetStreamContext) -> Pipeline | None:
    await msg.ack()

    try:
        event = PipelineJSON.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        return None
    return Pipeline.from_pipeline(event)


class Operator(ABC):
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
        self.metrics: OperatorMetrics = OperatorMetrics(
            id=self.id, timing=OperatorTiming()
        )
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

    async def initialize_pipeline(self):
        logger.info(
            f"Subscribing to stream {STREAM_OPERATORS} for operator {self.id}..."
        )
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
        self.pipeline = await receive_pipeline(msg[0], self.js)
        if self.pipeline is None:
            raise ValueError("Pipeline not found")
        self.info = self.pipeline.get_operator(self.id)
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

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
            msg = None
            timing: bool = loop_counter % 100 == 0
            if timing:
                self.metrics.timing.before_recv = datetime.now()
            if has_input_op:
                msg = await self.messenger.recv()
                if not msg:
                    continue
            if timing:
                self.metrics.timing.before_kernel = datetime.now()
            processed_msg = self.kernel(msg)
            if timing:
                self.metrics.timing.after_kernel = datetime.now()
            if self.messenger.output_ports and processed_msg:
                await self.messenger.send(processed_msg)
            if timing:
                self.metrics.timing.after_send = datetime.now()
            loop_counter += 1

    @abstractmethod
    def kernel(
        self,
        inputs: BytesMessage | None,
    ) -> BytesMessage | None:
        pass


KernelFn = Callable[
    [BytesMessage | None],
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
