import time
from threading import Thread
from typing import Dict, Type
from uuid import UUID

from zmglue.agentclient import AgentClient
from zmglue.logger import get_logger
from zmglue.messengers.base import BaseMessenger
from zmglue.messengers.zmq import ZmqMessenger
from zmglue.models import CommBackend, IdType, OperatorJSON
from zmglue.models.messages import BaseMessage, DataMessage
from zmglue.pipeline import Pipeline

logger = get_logger("operator", "DEBUG")

BACKEND_TO_MESSENGER: Dict[CommBackend, Type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}


class Operator:
    def __init__(
        self,
        id: IdType,
    ):
        self.id = id
        self.messenger: BaseMessenger | None = None
        self.pipeline: Pipeline | None = None
        self.info: OperatorJSON | None = None
        self.client = AgentClient(id=id)
        self.messenger_thread: Thread | None = None

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

        _id = str(self.id)
        if _id == "12345678-1234-1234-1234-1234567890ab":
            logger.warning("Running dummy operator")
            while True:
                self.messenger.send(DataMessage(data=b"Hello, World!"), _id)
        else:
            while True:
                message = self.messenger.recv(_id)
                if message:
                    logger.info(f"Received message: {message} on {self.id}")
                    processed_message = self.operate(message)
                    self.messenger.send(processed_message, _id)
                else:
                    time.sleep(1)

    def operate(self, message: BaseMessage) -> BaseMessage:
        if self.processing_function:
            return self.processing_function(message)
        else:
            raise NotImplementedError("No processing function defined")

    def set_processing_function(self, func):
        self.processing_function = func
