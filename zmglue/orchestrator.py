from collections.abc import Callable
from typing import Any
from uuid import uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.fixtures import PIPELINE
from zmglue.logger import get_logger
from zmglue.pipeline import Pipeline
from zmglue.types import (
    BaseMessage,
    ErrorMessage,
    PipelineMessage,
    ProtocolZmq,
    URIConnectMessage,
    URIConnectResponseMessage,
    URILocation,
    URIUpdateMessage,
    URIZmq,
)
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("forchestrator", "DEBUG")


DEFAULT_ORCHESTRATOR_URI = URIZmq(
    id=uuid4(),
    location=URILocation.orchestrator,
    transport_protocol=ProtocolZmq.tcp,
    hostname="localhost",
    hostname_bind="*",
    port=cfg.ORCHESTRATOR_PORT,
)


class Orchestrator:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = Socket(
            SocketInfo(
                type=zmq.REP,
                uris=[DEFAULT_ORCHESTRATOR_URI],
                bind=True,
            ),
            self.context,
        )
        self.socket.bind_or_connect()
        self.poller = zmq.Poller()
        self.poller.register(self.socket._socket, zmq.POLLIN)
        self.message_handlers: dict[type[BaseMessage], Callable[[BaseMessage], Any]] = {
            PipelineMessage: self.handle_pipeline_request,
            URIUpdateMessage: self.handle_uri_update_request,
            URIConnectMessage: self.handle_uri_connect_request,
        }
        self.pipeline = Pipeline.from_pipeline(PIPELINE)

    def handle_pipeline_request(self, msg: BaseMessage) -> PipelineMessage:
        if not isinstance(msg, PipelineMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        logger.debug(f"Received pipeline request for node {msg.node_id}")
        logger.debug(f"Pipeline: {self.pipeline.to_json()}")
        try:
            return PipelineMessage(pipeline=self.pipeline.to_json())
        except ValidationError as e:
            logger.error(f"Error validating pipeline request: {e}")
            raise e

    def handle_uri_update_request(self, msg: BaseMessage):
        if not isinstance(msg, URIUpdateMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        logger.info(f"Received URI update request from {msg.id}.")
        self.pipeline.update_uri(msg)
        return msg

    def handle_uri_connect_request(self, msg: BaseMessage) -> BaseMessage:
        if not isinstance(msg, URIConnectMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        uris = self.pipeline.get_connections(msg)

        logger.debug(f"Found URIs: {uris}")
        return URIConnectResponseMessage(connections=uris)

    def process_message(self, msg: BaseMessage) -> BaseMessage:
        handler = self.message_handlers.get(type(msg))
        err_msg: str | None = None

        if not handler:
            err_msg = f"No handler for message subject: {msg.subject}"
            logger.error(err_msg)
            return ErrorMessage(message=err_msg)

        try:
            return handler(msg)
        except ValidationError as e:
            err_msg = (
                f"Validation error processing message: {[err for err in e.errors()]}"
            )
        except ValueError as e:
            err_msg = f"Error processing message: {e}"
        except Exception as e:
            err_msg = f"Unknown error processing message: {e}"

        logger.error(err_msg)
        return ErrorMessage(message=err_msg)

    def run(self):
        logger.info("Orchestrator starting...")
        while True:
            socks = dict(self.poller.poll(1000))
            if self.socket._socket in socks:
                request = self.socket.recv_model()
                logger.debug(f"Received: {request}")
                response = self.process_message(request)
                logger.debug(f"Sending: {response}")
                self.socket.send_model(response)
            else:
                logger.debug("No messages received.")