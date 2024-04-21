import json
import uuid
from multiprocessing import Pipe, Value
from typing import Any, Callable, Dict, Optional, Type, cast
from uuid import uuid4

import networkx as nx
import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.fixtures import PIPELINE
from zmglue.logger import get_logger
from zmglue.pipeline import Pipeline
from zmglue.types import (
    MESSAGE_SUBJECT_TO_MODEL,
    BaseMessage,
    EdgeJSON,
    ErrorMessage,
    IdType,
    MessageSubject,
    NodeJSON,
    NodeType,
    PipelineJSON,
    PipelineMessage,
    PortJSON,
    PortType,
    Protocol,
    ProtocolZmq,
    URIAssignMessage,
    URIBase,
    URIConnectMessage,
    URIMessage,
    URIShmem,
    URIZmq,
)
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("forchestrator", "DEBUG")


def generate_uri_zmq(msg: URIMessage) -> URIZmq:
    try:
        uri = URIZmq(**msg.model_dump())
        uri.uri = f"{msg.protocol.value}://{uuid4()}"
        return uri
    except ValidationError as e:
        logger.error(f"Error validating ZMQ URI request: {e}")
        raise e


def generate_uri_shmem(msg: URIMessage) -> URIShmem:
    try:
        return URIShmem(
            **msg.model_dump(), uri=f"{msg.protocol}://{uuid4()}", path=uuid4()
        )
    except ValidationError as e:
        logger.error(f"Error validating shmem URI request: {e}")
        raise e


def generate_uri(msg: URIMessage) -> URIBase:
    handler = URI_HANDLER_MAP.get(msg.protocol)
    if not handler:
        raise ValueError(f"No handler for protocol: {msg.protocol}")

    return handler(msg)


URI_HANDLER_MAP: dict[Protocol, Callable[[URIMessage], URIBase]] = {
    Protocol.Zmq: generate_uri_zmq,
    Protocol.Shmem: generate_uri_shmem,
}


class Orchestrator:
    def __init__(self):
        self.uri_store: Dict[IdType, URIBase] = {}
        self.context = zmq.Context()
        self.socket = Socket(
            SocketInfo(
                type=zmq.REP,
                uris=[
                    URIZmq(
                        node_id=uuid4(),  # TODO: these should be optional
                        port_id=uuid4(),  # TODO: these should be optional
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        hostname_bind="*",
                        port=cfg.ORCHESTRATOR_PORT,
                    )
                ],
                bind=True,
            ),
            self.context,
            logger,
        )
        self.socket.bind_or_connect()
        self.poller = zmq.Poller()
        self.poller.register(self.socket._socket, zmq.POLLIN)
        self.message_handlers: dict[
            Type[BaseMessage], Callable[[BaseMessage], BaseMessage]
        ] = {
            PipelineMessage: self.handle_pipeline_request,
            URIAssignMessage: self.handle_uri_assign_request,
            URIConnectMessage: self.handle_uri_connect_request,
        }
        self.pipeline = Pipeline.from_pipeline(PIPELINE)

    def get_existing_uri(self, node: NodeJSON) -> URIBase | None:
        logger.info(self.uri_store.get(node.id))
        return self.uri_store.get(node.id)

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

    def handle_uri_assign_request(self, msg: BaseMessage) -> URIAssignMessage:
        if not isinstance(msg, URIAssignMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        if msg.node_id in self.uri_store:
            logger.info(f"URI already exists for node {msg.node_id}")
            return URIAssignMessage(**self.uri_store[msg.node_id].model_dump())

        uri = generate_uri(msg)
        self.store_uri(uri)
        return URIAssignMessage(**uri.model_dump())

    def handle_uri_connect_request(self, msg: BaseMessage) -> URIConnectMessage:
        if not isinstance(msg, URIConnectMessage):
            raise ValueError(f"Invalid message subject: {msg}")

        predecessors = self.pipeline.get_predecessors(msg.node_id)
        if not predecessors:
            raise ValueError(f"No predecessors found for node {msg.node_id}")

        predecessor = predecessors[0]  # TODO: make it possible to have multiple edges
        uri = self.uri_store.get(predecessor)

        if uri:
            logger.info(f"Found URI for predecessor node {predecessor}: {uri}")
            return URIConnectMessage(**uri.model_dump())
        else:
            raise ValueError(f"No URI found for predecessor node {predecessor}")

    def store_uri(self, msg: URIBase) -> None:
        self.uri_store[msg.node_id] = msg

    def process_message(self, msg: BaseMessage) -> BaseMessage:
        handler = self.message_handlers.get(type(msg))
        err_msg: Optional[str] = None

        if not handler:
            err_msg = f"No handler for message subject: {msg.subject}"
            logger.error(err_msg)
            return ErrorMessage(message=err_msg)

        try:
            return handler(msg)
        except ValidationError as e:
            err_msg = f"Validation error processing message: {e}"
        except ValueError as e:
            err_msg = f"Error processing message: {e}"
        except Exception as e:
            err_msg = f"Unknown error processing message: {e}"

        logger.error(err_msg)
        return ErrorMessage(message=err_msg)

    def run(self):
        logger.info("Orchestrator starting...")
        while True:
            socks = dict(self.poller.poll(1000))  # Timeout in milliseconds
            if self.socket._socket in socks:
                request = self.socket.recv_model()
                logger.debug(f"Received: {request}")
                response = self.process_message(request)
                logger.debug(f"Sending: {response}")
                self.socket.send_model(response)
            else:
                logger.debug("No messages received.")


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.run()
