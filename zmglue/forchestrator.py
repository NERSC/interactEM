import json
import uuid
from multiprocessing import Pipe
from typing import Any, Callable, Type, cast
from uuid import uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.types import (
    MESSAGE_TYPE_TO_MODEL,
    BaseMessage,
    EdgeJSON,
    IdType,
    MessageType,
    NodeJSON,
    NodeType,
    PipelineJSON,
    PipelineMessage,
    PortType,
    Protocol,
    URIAssignMessage,
    URIBase,
    URIConnectMessage,
    URIMessage,
    URIShmem,
    URIZmq,
)

logger = get_logger("forchestrator", "DEBUG")

NODE_0 = NodeJSON(
    id=uuid4(),
    image="zero",
    type=NodeType.Operator,
    params={"hello": "world"},
)

NODE_1 = NodeJSON(
    id=uuid4(),
    image="one",
    type=NodeType.Operator,
    params={"yo": "whattup"},
)

EDGE = EdgeJSON(
    type=PortType.Binary,
    start=NODE_0.id,
    stop=NODE_1.id,
)

PIPELINE = PipelineJSON(
    id=uuid4(),
    nodes=[NODE_0, NODE_1],
    edges=[EDGE],
)

URI_STORE: dict[NodeJSON, URIBase] = {}


def generate_uri_shmem(msg: URIMessage) -> URIShmem | None:
    try:
        return URIShmem(
            **msg.model_dump(), uri=f"{msg.protocol}://{uuid4()}", path=uuid4()
        )
    except ValidationError as e:
        logger.error(f"Error validating shmem URI request: {e}")
        return None


def generate_uri_zmq(msg: URIMessage) -> URIZmq | None:
    try:
        uri = URIZmq(**msg.model_dump())
        uri.uri = f"{msg.protocol}://{uuid4()}"
        return uri
    except ValidationError as e:
        logger.error(f"Error validating ZMQ URI request: {e}")
        return None


def generate_uri(msg: URIMessage) -> URIBase | None:
    handler = URI_HANDLER_MAP.get(msg.protocol)
    return handler(msg) if handler else None


URI_HANDLER_MAP: dict[Protocol, Callable[[URIMessage], URIBase | None]] = {
    Protocol.Zmq: generate_uri_zmq,
    Protocol.Shmem: generate_uri_shmem,
}


def get_existing_uri(node: NodeJSON) -> URIBase | None:
    return URI_STORE.get(node)


def handle_pipeline_request(msg: BaseMessage) -> PipelineMessage | None:
    if not isinstance(msg, PipelineMessage):
        logger.error(f"Invalid message type: {msg}")
        return None
    return PipelineMessage(pipeline=PIPELINE)


def convert_raw_msg_to_model(msg: dict[str, Any]) -> BaseMessage | None:

    msg_type = MessageType(msg.get("type"))
    if not msg_type:
        logger.error(f"No message type found in message: {msg}")
        return None

    Model = MESSAGE_TYPE_TO_MODEL.get(msg_type)
    if not Model:
        logger.error(f"No model type for message: {msg}")
        return None

    try:
        return Model(**msg)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return None


def handle_uri_assign_request(msg: BaseMessage) -> URIAssignMessage | None:
    if not isinstance(msg, URIAssignMessage):
        logger.error(f"Invalid message type: {msg}")
        return None

    uri = generate_uri(msg)
    if not uri:
        logger.error(f"Could not generate URI for msg: {msg}")
        return None

    return URIAssignMessage(**uri.model_dump())


def handle_uri_connect_request(msg: BaseMessage) -> URIConnectMessage | None:
    if not isinstance(msg, URIConnectMessage):
        logger.error(f"Invalid message type: {msg}")
        return None

    uri = get_existing_uri(msg)
    if not uri:
        logger.error(f"No URI found for node: {msg}")
        return None

    return URIConnectMessage(**uri.model_dump())


def process_message(msg: BaseMessage) -> BaseMessage | None:
    handler = MESSAGE_HANDLER_MAP.get(type(msg))

    if not handler:
        logger.error(f"No handler for message type: {msg.type}")
        return None

    return handler(msg)


MESSAGE_HANDLER_MAP: dict[
    Type[BaseMessage], Callable[[BaseMessage], BaseMessage | None]
] = {
    PipelineMessage: handle_pipeline_request,
    URIAssignMessage: handle_uri_assign_request,
    URIConnectMessage: handle_uri_connect_request,
}

if __name__ == "__main__":
    logger.info("Fake orchestrator starting...")
    context = zmq.Context()
    rep_socket = context.socket(zmq.REP)
    logger.info(f"Binding to port {cfg.ORCHESTRATOR_PORT}")
    rep_socket.bind(f"tcp://*:{cfg.ORCHESTRATOR_PORT}")

    poller = zmq.Poller()
    poller.register(rep_socket, zmq.POLLIN)

    while True:
        socks = dict(poller.poll(timeout=1000))  # Timeout in milliseconds
        if socks.get(rep_socket) == zmq.POLLIN:
            request = rep_socket.recv_json()
            if isinstance(request, str):
                request = json.loads(request)
            logger.info(f"Received: {request}")
            if not isinstance(request, dict):
                logger.error(f"Received non-dict: {request}")
                continue
            model = convert_raw_msg_to_model(request)
            reply = {}
            if model:
                reply = process_message(model)
                if not reply:
                    logger.error(f"Error processing message: {model}")
                    rep_socket.send_json({})
                else:
                    rep_socket.send_json(reply.model_dump_json())
                logger.info(f"Sent: {reply}")
            else:
                rep_socket.send_json(reply)
            # Process request and send response
        else:
            logger.info("No messages received.")
