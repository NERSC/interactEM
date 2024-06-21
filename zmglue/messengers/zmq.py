import time
from collections import deque
from enum import Enum
from queue import Queue
from typing import Any, Deque
from uuid import UUID

import zmq

from zmglue.agentclient import AgentClient
from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import URI, BaseMessage, IdType, PortJSON, PortType
from zmglue.models.base import OperatorID, PortID
from zmglue.models.messages import PutPipelineNodeMessage
from zmglue.models.pipeline import InputJSON, OutputJSON
from zmglue.models.uri import ZMQAddress
from zmglue.pipeline import Pipeline
from zmglue.zsocket import Socket, SocketInfo

from .base import BaseMessenger

logger = get_logger("messenger", "DEBUG")


class ZmqMessenger(BaseMessenger):

    def __init__(
        self,
        operator,
    ):
        self.input_infos: dict[PortID, InputJSON] = {}
        self.input_sockets: dict[PortID, Socket] = {}
        self.output_infos: dict[PortID, OutputJSON] = {}
        self.output_sockets: dict[PortID, Socket] = {}
        self._context: zmq.SyncContext = operator.client.context
        self._id: OperatorID = UUID(operator.id)
        self.input_deque: Deque[BaseMessage] = deque()
        self.output_deque: Deque[BaseMessage] = deque()
        logger.name = f"messenger-{self._id}"

    @property
    def type(self):
        return "zmq"

    def recv(self, src: IdType) -> BaseMessage | None:
        try:
            message = self.input_deque.popleft()
            return message
        except IndexError:
            return None

    def send(self, message: BaseMessage, dst: IdType):
        self.output_deque.append(message)

    def start(self, client: AgentClient, pipeline: Pipeline):
        self._setup(client, pipeline)

    def _add_socket(self, port_info: PortJSON):

        if port_info.port_type == PortType.output:
            bind = True
            socket_type = zmq.PUSH
        else:
            bind = False
            socket_type = zmq.PULL

        addr = ZMQAddress.from_uri(port_info.uri.to_uri())

        socket = Socket(
            SocketInfo(
                type=socket_type,
                bind=bind,
                addresses=addr,  # type: ignore (coerced into list)
                parent_id=port_info.id,
            ),
            self._context,
        )

        if port_info.port_type == PortType.output:
            self.output_sockets[port_info.id] = socket
        else:
            self.input_sockets[port_info.id] = socket

    def _setup_inputs(self, agent_client: AgentClient, pipeline: Pipeline):
        for input in pipeline.get_operator_inputs(self._id).values():
            self.input_infos[input.id] = input

        for info in self.input_infos.values():
            self._add_socket(info)

        for port_id, socket in self.input_sockets.items():
            socket.info.addresses = self._get_addresses(agent_client, pipeline, port_id)
            logger.info(f"Connecting to {socket.info.addresses} on port {port_id}")
            socket.bind_or_connect()
            info = self.input_infos[port_id]
            info.connected = True

            while True:
                try:
                    agent_client.put_pipeline_node(PutPipelineNodeMessage(node=info))
                except ValueError as e:
                    logger.error(f"Failed to update info: {e}")
                    time.sleep(1)
                    continue
                break

    def _get_addresses(
        self, agent_client: AgentClient, pipeline: Pipeline, port_id: PortID
    ) -> list[ZMQAddress]:
        """Retrieve a list of ZMQAddress objects for the given port_id."""
        addresses: list[ZMQAddress] = []
        expected_num_addr = len(pipeline.get_predecessors(port_id))

        while len(addresses) < expected_num_addr:
            uris = agent_client.get_connect_uris(port_id)
            for uri in uris:
                addrs = uri.query.get("address", [])
                if addrs:
                    addresses.extend(
                        [ZMQAddress.from_address(addr) for addr in addrs if addr]
                    )

            # Filter out any incomplete addresses
            addresses = [addr for addr in addresses if addr.hostname]

            if len(addresses) < expected_num_addr:
                logger.info("Waiting for all addresses to become available...")
                time.sleep(1)

        return addresses

    def _setup_outputs(self, agent_client: AgentClient, pipeline: Pipeline):
        for output in pipeline.get_operator_outputs(self._id).values():
            self.output_infos[output.id] = output

        for info in self.output_infos.values():
            self._add_socket(info)

        for port_id, socket in self.output_sockets.items():
            info = self.output_infos[port_id]
            updated, port = socket.bind_or_connect()
            info.connected = True

            if updated:
                addresses = [a.to_address() for a in socket.info.addresses]
                info.uri.query["address"] = addresses

                while True:
                    try:
                        agent_client.put_pipeline_node(
                            PutPipelineNodeMessage(node=info)
                        )
                    except ValueError as e:
                        logger.error(f"Failed to update info: {e}")
                        time.sleep(1)
                        continue
                    break

    def _setup(self, agent_client: AgentClient, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")
        self._setup_outputs(agent_client, pipeline)
        self._setup_inputs(agent_client, pipeline)

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

    def _readiness_check(self):
        print([socket.info.connected for socket in self.input_sockets.values()])
        return all(
            [socket.info.connected for socket in self.input_sockets.values()]
            + [socket.info.connected for socket in self.output_sockets.values()]
            + [info.connected for info in self.output_infos.values()]
            + [info.connected for info in self.input_infos.values()]
        )

    @property
    def ready(self):
        return self._readiness_check()
