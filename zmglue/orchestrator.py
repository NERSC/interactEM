from collections.abc import Callable
from threading import Event, Thread
from typing import Any, Optional
from uuid import uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.fixtures import PIPELINE
from zmglue.logger import get_logger
from zmglue.models import (
    BaseMessage,
    CommBackend,
    ErrorMessage,
    PipelineMessage,
    Protocol,
    URIConnectMessage,
    URIConnectResponseMessage,
    URILocation,
    URIUpdateMessage,
)
from zmglue.models.messages import (
    GetConnectionsMessage,
    GetConnectionsResponseMessage,
    OKMessage,
    PutPipelineNodeMessage,
)
from zmglue.models.uri import URI, ZMQAddress
from zmglue.pipeline import Pipeline
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("forchestrator", "DEBUG")

DEFAULT_ORCHESTRATOR_SOCKET_ADDRESS: str = (
    f"tcp://?interface={cfg.ORCHESTRATOR_INTERFACE}&hostname=localhost&port={cfg.ORCHESTRATOR_PORT}"
)
DEFAULT_ORCHESTRATOR_URI = URI(
    id=uuid4(),
    hostname="localhost",
    location=URILocation.orchestrator,
    comm_backend=CommBackend.ZMQ,
    query={"address": [DEFAULT_ORCHESTRATOR_SOCKET_ADDRESS]},
)


class Orchestrator:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = Socket(
            SocketInfo(
                type=zmq.REP,
                addresses=DEFAULT_ORCHESTRATOR_URI.query["address"],  # type: ignore
                bind=True,
                parent_id=DEFAULT_ORCHESTRATOR_URI.id,
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
            PutPipelineNodeMessage: self.handle_put_pipeline_node,
        }
        self.pipeline = Pipeline.from_pipeline(PIPELINE)
        self._running = Event()
        self.thread: Optional[Thread] = None

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

    def handle_put_pipeline_node(self, msg: BaseMessage) -> BaseMessage:
        if not isinstance(msg, PutPipelineNodeMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        uris = self.pipeline.put_node(msg)
        return OKMessage(message="All good :)")

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
        self._running.set()
        while self._running.is_set():
            socks = dict(self.poller.poll(1000))
            if self.socket._socket in socks:
                request = self.socket.recv_model()
                logger.debug(f"Received: {request}")
                response = self.process_message(request)
                logger.debug(f"Sending: {response}")
                self.socket.send_model(response)
            else:
                logger.debug("No messages received.")

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Orchestrator is already running.")
            return
        self.thread = Thread(target=self.run)
        self.thread.start()
        logger.info("Orchestrator started.")

    def stop(self):
        if not self._running.is_set():
            logger.warning("Orchestrator is not running.")
            return
        self._running.clear()
        if self.thread:
            self.thread.join()
        self.shutdown()

    def shutdown(self):
        logger.info("Shutting down orchestrator...")
        if self.socket._socket:
            self.socket._socket.close()
        self.context.term()
        logger.info("Orchestrator shut down successfully.")
