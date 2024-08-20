import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any

import nats
import nats.js
import nats.js.errors
from core.constants import (
    BUCKET_OPERATORS,
    BUCKET_OPERATORS_TTL,
    STREAM_OPERATORS,
)
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


DEFAULT_NATS_ADDRESS = "nats://host.containers.internal:4222"


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

    @property
    def input_queue(self) -> str:
        return str(self.id)

    async def start(self):
        logger.info(f"Starting operator {self.id}...")
        self.nc = await nats.connect(
            servers=[DEFAULT_NATS_ADDRESS], name=f"operator-{self.id}"
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

        await self.messenger.start(self.pipeline)
        await self.run()

    async def run(self):
        if not self.messenger:
            raise ValueError("Messenger not initialized")
        if self.messenger.input_ports:
            while True:
                await asyncio.sleep(1)
                message = await self.messenger.recv(self.input_queue)
                if message:
                    logger.info(f"Received message: {message} on {self.id}")
                    await self.operate(message)
        elif not self.messenger.input_ports:
            while True:
                await asyncio.sleep(1)
                await self.operate(None)

    async def operate(self, message: BaseMessage | None):
        if self.messenger is None:
            raise ValueError("Messenger not initialized")
        processed_message = self.kernel(message)
        print(processed_message)
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
    start: bool = True,
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
