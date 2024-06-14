from collections import deque
from enum import Enum
from queue import Queue
from typing import Deque
from uuid import UUID

import zmq

from zmglue.agentclient import AgentClient
from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import (
    BaseMessage,
    IdType,
    PortJSON,
    PortType,
    URIBase,
    URIUpdateMessage,
    URIZmq,
)
from zmglue.models.base import OperatorID
from zmglue.pipeline import Pipeline
from zmglue.utils import find_free_port
from zmglue.zsocket import Socket, SocketInfo

from .base import BaseMessenger

logger = get_logger("messenger", "DEBUG")

CLIENT_URI = URIZmq.from_uri(cfg.AGENT_URI)


class ZmqMessenger(BaseMessenger):

    def __init__(
        self,
        operator_id: OperatorID,
        context: zmq.SyncContext = zmq.Context(),
    ):
        self.input_sockets: dict[IdType, Socket] = {}
        self.output_sockets: dict[IdType, Socket] = {}
        self._context = context
        self._id: OperatorID = operator_id
        self.input_deque: Deque[BaseMessage] = deque()
        self.output_deque: Deque[BaseMessage] = deque()

    def recv(self, src: IdType) -> BaseMessage | None:
        try:
            message = self.input_deque.popleft()
            return message
        except IndexError:
            return None

    def send(self, message: BaseMessage, dst: IdType):
        self.output_deque.append(message)

    def start(self, client: AgentClient, pipeline: Pipeline):
        self._add_sockets_from_pipeline(pipeline)
        self._connect(client)

    def _add_socket(self, port_info: PortJSON):
        bind = False
        socket_type = zmq.PULL

        if port_info.port_type == PortType.output:
            bind = True
            socket_type = zmq.PUSH

        if port_info.uri is None:
            uris = []
        else:
            uris = [port_info.uri]

        socket = Socket(
            SocketInfo(
                type=socket_type,
                bind=bind,
                uris=uris,
            ),
            self._context,
        )

        if port_info.port_type == PortType.output:
            self.output_sockets[port_info.id] = socket
        else:
            self.input_sockets[port_info.id] = socket

    def _add_sockets_from_pipeline(self, pipeline: Pipeline):

        operator_id = self._id

        for input in pipeline.get_operator_inputs(operator_id).values():
            self._add_socket(input)

        for output in pipeline.get_operator_outputs(operator_id).values():
            self._add_socket(output)

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

    def _recv_from_sockets(self):
        while True:
            for port_id, socket in self.input_sockets.items():
                try:
                    message = socket.recv_model(zmq.DONTWAIT)
                    self.input_deque.append(message)
                except zmq.Again:  # no more messages
                    pass
                except zmq.ZMQError as e:
                    logger.error(f"Failed to receive message on port {port_id}: {e}")
                finally:
                    continue

    def _send_to_sockets(self):
        while True:
            for port_id, socket in self.output_sockets.items():
                try:
                    message = self.output_deque.popleft()
                    socket.send_model(message, zmq.DONTWAIT)
                except IndexError:
                    pass
                except zmq.Again:
                    logger.info("Timeout sending message.")
                    self.output_deque.appendleft(message)
                except zmq.ZMQError as e:
                    logger.info(f"Failed to send message on port {port_id}: {e}.")
