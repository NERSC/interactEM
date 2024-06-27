import time
from abc import ABC, abstractmethod
from functools import wraps
from threading import Thread
from typing import Any, Callable, Dict, Optional, Type

from zmglue.agentclient import AgentClient
from zmglue.logger import get_logger
from zmglue.messengers.base import BaseMessenger
from zmglue.messengers.zmq import ZmqMessenger
from zmglue.models import CommBackend, IdType, OperatorJSON
from zmglue.models.base import OperatorID
from zmglue.models.messages import BaseMessage, DataMessage
from zmglue.pipeline import Pipeline

logger = get_logger("operator", "DEBUG")

BACKEND_TO_MESSENGER: Dict[CommBackend, Type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}


class Operator(ABC):
    def __init__(
        self,
        id: IdType,
    ):
        self.id = id
        self.pipeline: Pipeline | None = None
        self.info: OperatorJSON | None = None
        self.client = AgentClient(id=id)
        self.messenger_thread: Thread | None = None

    @property
    def input_queue(self) -> str:
        return str(self.id)

    def start(self):
        while self.pipeline is None:
            response = self.client.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)

        self.info = self.pipeline.get_operator(self.id)
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

        comm_backend = self.info.uri.comm_backend
        messenger_cls = BACKEND_TO_MESSENGER.get(comm_backend)
        if messenger_cls is None:
            raise ValueError(f"Invalid communications backend: {comm_backend}")

        self.messenger = messenger_cls(self)
        logger.info(f"Starting messenger {self.messenger}...")

        # TODO: client should not go in here, because it is not threadsafe
        # currently works but won't if we use client a lot in the messenger
        self.messenger_thread = Thread(
            target=self.messenger.start,
            name="messenger_thread",
            args=(self.client, self.pipeline),
        )
        self.messenger_thread.start()

        while not self.messenger.ready:
            logger.info(f"Waiting for messenger to be wired up properly...")
            time.sleep(1)

        self.run_operator()

    def run_operator(self):
        if self.messenger.input_ports:
            while True:
                message = self.messenger.recv(self.input_queue)
                if message:
                    logger.info(f"Received message: {message} on {self.id}")
                    self.operate(message)
        elif not self.messenger.input_ports:
            while True:
                self.operate(None)

    def operate(self, message: BaseMessage | None):
        processed_message = self.kernel(message)
        self.messenger.send(processed_message, str(self.id))

    @abstractmethod
    def kernel(
        self,
        inputs: Optional[BaseMessage],
    ) -> BaseMessage:
        pass


KernelFn = Callable[
    [BaseMessage | None],
    BaseMessage,
]


def operator(
    func: Optional[KernelFn] = None,
    start: bool = True,
) -> Any:
    def decorator(func: KernelFn) -> Callable[[OperatorID], Operator]:
        @wraps(func)
        def wrapper(operator_id: OperatorID):
            name = func.__name__

            @wraps(func)
            def kernel(_, *args, **kwargs):
                return func(*args, **kwargs)

            class_name = f"{name.capitalize()}Operator"
            OpClass = type(class_name, (Operator,), {"kernel": kernel})

            obj = OpClass(operator_id)

            if start:
                obj.start()

            return obj

        return wrapper

    if func is not None:
        return decorator(func)

    return decorator
