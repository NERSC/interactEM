from collections import deque
from enum import Enum
from queue import Queue
from typing import Deque
from uuid import UUID

import zmq

from zmglue.agentclient import AgentClient
from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.pipeline import Pipeline
from zmglue.types import (
    BaseMessage,
    IdType,
    PortJSON,
    PortType,
    URIBase,
    URIUpdateMessage,
    URIZmq,
)
from zmglue.utils import find_free_port
from zmglue.zsocket import Socket, SocketInfo

from .base import BaseMessenger

logger = get_logger("messenger", "DEBUG")


class QueueType(str, Enum):
    input = "input"
    output = "output"


QueueMap = dict[QueueType, dict[IdType, Queue[BaseMessage]]]


CLIENT_URI = URIZmq.from_uri(cfg.AGENT_URI)


class ZmqMessenger(BaseMessenger):
    OUTPUT_SOCKET_TYPE = zmq.PUSH
    INPUT_SOCKET_TYPE = zmq.PULL

    def __init__(
        self,
        node_id: UUID,
        context: zmq.SyncContext = zmq.Context(),
        logger: Logger = logger,
    ):
        self.input_sockets: dict[IdType, Socket] = {}
        self.output_sockets: dict[IdType, Socket] = {}
        self._context = context
        self.pipeline: Pipeline | None = None
        self._id: UUID = node_id
        self._agent_client = AgentClient(id=node_id, context=self._context)
        self._poller = zmq.Poller()
        self.queues: QueueMap = {}

    def recv(self, src: IdType):
        self._recv_from_sockets()

    def send(self, message: BaseMessage, dst: IdType):
        socket = self.output_sockets.get(dst)
        if not socket:
            raise ValueError(f"Socket not found for destination {dst}")
        socket.send_model(message)

    def start(self):
        self._get_my_pipeline()
        self._add_sockets_from_pipeline()
        self._connect(self._agent_client)

    def _get_my_pipeline(self):
        while self.pipeline is None:
            response = self._agent_client.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)
            else:
                time.sleep(1)

    def _add_socket(
        self, port_id: IdType, is_output: bool, uris: list[URIBase] | None = None
    ):
        socket = Socket(
            SocketInfo(
                type=self.OUTPUT_SOCKET_TYPE if is_output else self.INPUT_SOCKET_TYPE,
                bind=is_output,
                uris=uris or [],
            ),
            self._context,
        )
        if is_output:
            self.output_sockets[port_id] = socket
        else:
            self.input_sockets[port_id] = socket

    def _add_sockets_from_pipeline(self):
        pipeline = self.pipeline

        if pipeline is None:
            raise ValueError("Pipeline not found")

        node_id = self._id

        for id, input in pipeline.get_operator_inputs(node_id).items():
            self._add_socket(input.id, is_output=False)
            self.queues[QueueType.input][input.id] = Queue()

        for id, output in pipeline.get_operator_outputs(node_id).items():
            self._add_socket(output.id, is_output=True, uris=[output.uri])
            self.queues[QueueType.output][output.id] = Queue()

    def _connect(self, agent_client: AgentClient):

        for port_id, socket in self.output_sockets.items():
            uris = socket.info.uris
            updates: list[URIBase] = []
            for uri in uris:
                bind_port = find_free_port()
                logger.debug(f"Found port {bind_port} for {uri}")
                uri.port = bind_port
                update = agent_client.update_uri(
                    URIUpdateMessage(
                        **uri.model_dump(),
                    )
                )
                updates.append(URIBase(**update.model_dump()))
            socket.update_uris(updates)
            socket.bind_or_connect()  # TODO: error handling

        for port_id, socket in self.input_sockets.items():
            uris = agent_client.get_connect_uris(port_id)
            socket.update_uris(uris)
            socket.bind_or_connect()  # TODO: error handling
            self._poller.register(socket._socket, zmq.POLLIN)

    def _recv_from_sockets(self):
        polled_sockets = dict(self._poller.poll(100))
        if not polled_sockets:
            return
        for port_id, socket in self.input_sockets.items():
            while True:
                if (
                    socket._socket in polled_sockets
                    and polled_sockets[socket._socket] == zmq.POLLIN
                ):
                    try:
                        message = socket.recv_model(zmq.DONTWAIT)
                        self.queues[QueueType.input][port_id].put(message)
                        logger.debug(f"Message received and queued on port {port_id}.")
                    except zmq.Again:  # no more messages
                        break
                    except zmq.ZMQError as e:
                        logger.error(
                            f"Failed to receive message on port {port_id}: {e}"
                        )
                        break
                else:
                    # If the socket is not ready, move to the next one
                    break
