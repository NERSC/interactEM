import asyncio
import signal
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any

import nats
import nats.js
import nats.js.errors
from core.constants import BUCKET_OPERATORS, BUCKET_OPERATORS_TTL, STREAM_OPERATORS
from core.logger import get_logger
from core.models import CommBackend, IdType, OperatorJSON, PipelineJSON
from core.models.base import OperatorID
from core.models.messages import BaseMessage
from core.pipeline import Pipeline
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy
from nats.js.kv import KeyValue
from pydantic import ValidationError

from .config import cfg
from .messengers.base import BaseMessenger
from .messengers.zmq import ZmqMessenger

logger = get_logger("operator", "DEBUG")

BACKEND_TO_MESSENGER: dict[CommBackend, type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}


async def receive_pipeline(msg: NATSMsg, js: JetStreamContext) -> Pipeline | None:
    await msg.ack()

    try:
        event = PipelineJSON.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        return None
    return Pipeline.from_pipeline(event)


class Operator(ABC):
    def __init__(
        self,
        id: IdType,
    ):
        self.id = id
        self.messenger: BaseMessenger | None = None
        self.pipeline: Pipeline | None = None
        self.info: OperatorJSON | None = None
        self.nc: NATSClient | None = None
        self.js: JetStreamContext | None = None
        self.kv: KeyValue | None = None
        self.messenger_task: asyncio.Task | None = None
        self.run_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    @property
    def input_queue(self) -> str:
        return str(self.id)

    async def start(self):
        logger.info(f"Starting operator {self.id}...")
        logger.info(f"Connecting to NATS at {cfg.NATS_SERVER_URL}...")
        self.nc = await nats.connect(
            servers=[str(cfg.NATS_SERVER_URL)], name=f"operator-{self.id}"
        )
        logger.info("Connected to NATS...")
        self.js = self.nc.jetstream()
        consumer_cfg = ConsumerConfig(
            description=f"operator-{self.id}",
            deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
        )
        psub = await self.js.pull_subscribe(
            stream=STREAM_OPERATORS,
            subject=f"{STREAM_OPERATORS}.{self.id}",
            config=consumer_cfg,
        )
        msg = await psub.fetch(1)
        self.pipeline = await receive_pipeline(msg[0], self.js)
        if self.pipeline is None:
            raise ValueError("Pipeline not found")

        # TODO: make this a util (also present in orchestrator)
        try:
            self.kv = await self.js.key_value(BUCKET_OPERATORS)
        except nats.js.errors.BucketNotFoundError:
            bucket_cfg = nats.js.api.KeyValueConfig(
                bucket=BUCKET_OPERATORS, ttl=BUCKET_OPERATORS_TTL
            )
            self.kv = await self.js.create_key_value(config=bucket_cfg)

        self.info = self.pipeline.get_operator(self.id)
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

        comm_backend = CommBackend.ZMQ
        messenger_cls = BACKEND_TO_MESSENGER.get(comm_backend)
        if messenger_cls is None:
            raise ValueError(f"Invalid communications backend: {comm_backend}")

        self.messenger = messenger_cls(self.id, self.js)
        logger.info(f"Starting messenger {self.messenger}...")

        await self.setup_signal_handlers()
        await self.messenger.start(self.pipeline)
        self.run_task = asyncio.create_task(self.run())
        await self._shutdown_event.wait()
        await self.shutdown()

    async def shutdown(self):
        logger.info(f"Shutting down operator {self.id}...")
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
        if self.messenger.input_ports:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(1)
                message = await self.messenger.recv(self.input_queue)
                if message:
                    logger.info(f"Received message: {message} on {self.id}")
                    await self.operate(message)
        elif not self.messenger.input_ports:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(1)
                await self.operate(None)

    async def operate(self, message: BaseMessage | None):
        if self.messenger is None:
            raise ValueError("Messenger not initialized")
        processed_message = self.kernel(message)
        print(processed_message)
        if self.messenger.output_ports:
            await self.messenger.send(processed_message, str(self.id))

    @abstractmethod
    def kernel(
        self,
        inputs: BaseMessage | None,
    ) -> BaseMessage:
        pass


KernelFn = Callable[
    [BaseMessage | None],
    BaseMessage,
]


def operator(
    func: KernelFn | None = None,
    start: bool = False,
) -> Any:
    def decorator(func: KernelFn) -> Callable[[OperatorID], Operator]:
        @wraps(func)
        def wrapper(operator_id: OperatorID):
            @wraps(func)
            def kernel(_, *args, **kwargs):
                return func(*args, **kwargs)

            name = func.__name__
            class_name = f"{name.capitalize()}Operator"
            OpClass = type(class_name, (Operator,), {"kernel": kernel})

            obj = OpClass(operator_id)

            if start:
                asyncio.create_task(obj.start())

            return obj

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator
