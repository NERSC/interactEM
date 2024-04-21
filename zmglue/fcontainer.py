import argparse
import json
import socket as libsocket
import sys
import time
from sqlite3 import connect
from typing import Optional
from uuid import UUID, uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.pipeline import Pipeline
from zmglue.types import (
    PipelineMessage,
    Protocol,
    ProtocolZmq,
    URIAssignMessage,
    URIConnectMessage,
    URIMessage,
    URIZmq,
)
from zmglue.utils import find_free_port
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("container", "DEBUG")


class AgentClient:
    def __init__(self, node_id: UUID, port_id: UUID):
        self.context = zmq.Context()
        self.node_id = node_id
        self.port_id = port_id
        self.socket = Socket(
            SocketInfo(
                type=zmq.REQ,
                uris=[
                    URIZmq(
                        node_id=node_id,  # TODO: these should be optional
                        port_id=port_id,  # TODO: these should be optional
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        port=cfg.AGENT_PORT,
                    )
                ],
                bind=False,
            ),
            self.context,
            logger,
        )
        self.socket.bind_or_connect()

    def get_uri_assignment(
        self,
        node_id: UUID,
        port_id: UUID,
        port: int,
        hostname: str,
        hostname_bind: Optional[str] = None,
        interface: Optional[str] = None,
    ) -> URIAssignMessage:
        uri_request = URIAssignMessage(
            node_id=node_id,
            protocol=Protocol.Zmq,
            transport_protocol=ProtocolZmq.tcp,
            port_id=port_id,
            hostname=hostname,
            hostname_bind=hostname_bind,
            interface=interface,
            port=port,
        )

        logger.info(f"Asking agent for a URI: {uri_request}")
        self.socket.send_model(uri_request)
        response = self.socket.recv_model()
        if not isinstance(response, URIAssignMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")

        logger.info(f"Received URI assignment: {response}")
        return response

    def get_my_pipeline(self) -> PipelineMessage:
        self.socket.send_model(PipelineMessage(node_id=self.node_id))
        response = self.socket.recv_model()
        if not isinstance(response, PipelineMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")
        return response

    def get_connect_uri(self, node_id: UUID, port_id: UUID) -> URIMessage:
        input_connect_uri_request = URIConnectMessage(
            node_id=node_id,
            protocol=Protocol.Zmq,
            transport_protocol=ProtocolZmq.tcp,
            port_id=port_id,
        )

        attempt_counter = 0
        while True:
            logger.info(
                f"Asking for input connection URI...{input_connect_uri_request}"
            )
            self.socket.send_model(input_connect_uri_request)
            response = self.socket.recv_model()
            if attempt_counter > 5:
                raise ValueError("Invalid response")

            if not isinstance(response, URIConnectMessage):
                logger.error(f"Received invalid response: {response}")
                attempt_counter += 1
                time.sleep(1)
                continue

            break
        return response


class Container:
    def __init__(self, node_id: UUID, port_id: UUID):
        logger.name = f"container-{node_id}"
        self.node_id = node_id
        self.port_id = port_id
        self.context = zmq.Context()
        self.agent_client = AgentClient(node_id, port_id)
        self.pipeline: Optional[Pipeline] = None
        self.connect_socket: Optional[Socket] = None
        self.bind_socket: Optional[Socket] = None
        self.poller = zmq.Poller()

    def run(self):
        while self.pipeline is None:
            response = self.agent_client.get_my_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)
            else:
                time.sleep(1)

        self.setup_sockets()

        while self.pipeline is not None:
            if self.connect_socket:
                socks = dict(self.poller.poll(timeout=100))
                if socks.get(self.connect_socket._socket) == zmq.POLLIN:
                    msg = self.connect_socket.recv_string()
                    logger.info(f"Received: {msg}")
            if self.bind_socket:
                msg = "Aloha"
                self.bind_socket.send_string(msg)
                logger.info(f"Sent: {msg}")
            time.sleep(1)

    def setup_sockets(self):
        if self.pipeline is None:
            raise ValueError("Pipeline not set")

        if self.pipeline.get_successors(self.node_id):
            self.bind_socket = Socket(
                SocketInfo(
                    type=zmq.PUSH,
                    bind=True,
                ),
                self.context,
                logger,
            )

            port, hostname = find_free_port()
            interface = None
            hostname_bind = None
            logger.info(f"Found port {port} on {hostname}")
            if cfg.CONTAINER_INTERFACE:
                logger.debug(f"Setting interface to: {cfg.CONTAINER_INTERFACE}")
                interface = cfg.CONTAINER_INTERFACE

            bind_uri = None
            while True:
                try:
                    bind_uri = self.agent_client.get_uri_assignment(
                        self.node_id,
                        self.port_id,
                        port,
                        hostname,
                        hostname_bind=hostname_bind,
                        interface=interface,
                    )
                except ValueError as e:
                    logger.error(e)
                    logger.info("Retrying...")
                    time.sleep(1)
                    continue
                break
            self.bind_socket.update_uri(URIZmq(**bind_uri.model_dump()))
            logger.debug(f"Binding to {bind_uri}")
            self.bind_socket.bind_or_connect()

        if self.pipeline.get_predecessors(self.node_id):
            self.connect_socket = Socket(
                SocketInfo(
                    type=zmq.PULL,
                    bind=False,
                ),
                self.context,
                logger,
            )

            connect_uri = None

            while True:
                try:
                    connect_uri = self.agent_client.get_connect_uri(
                        self.node_id, self.port_id
                    )
                except ValueError as e:
                    logger.error(e)
                    logger.info("Retrying...")
                    time.sleep(1)
                    continue
                break

            self.connect_socket.update_uri(URIZmq(**connect_uri.model_dump()))
            self.connect_socket.bind_or_connect()
            self.poller.register(self.connect_socket._socket, zmq.POLLIN)


parser = argparse.ArgumentParser()
parser.add_argument("--node-id", type=UUID, required=True)
parser.add_argument("--port-id", type=UUID, required=True)
args = parser.parse_args()


if __name__ == "__main__":
    node_id: UUID = args.node_id
    port_id: UUID = args.port_id
    Container(node_id, port_id).run()
