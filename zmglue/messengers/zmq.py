import time
from uuid import UUID

import zmq

from zmglue.agentclient import AgentClient
from zmglue.logger import get_logger
from zmglue.models import BaseMessage, IdType, PortJSON, PortType
from zmglue.models.base import OperatorID, PortID, Protocol
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
        self._id: OperatorID = operator.id

        # Sockets for receiving/sending messages inside operator
        self.input_recv_socket: Socket = Socket(
            info=SocketInfo(
                type=zmq.PULL,
                bind=True,
                addresses=[ZMQAddress(protocol=Protocol.inproc, endpoint="recv")],
            ),
            context=self._context,
        )
        self.output_send_socket: Socket = Socket(
            info=SocketInfo(
                type=zmq.PUSH,
                bind=True,
                addresses=[ZMQAddress(protocol=Protocol.inproc, endpoint="send")],
            ),
            context=self._context,
        )

        # Sockets for receiving/sending message to operator
        self.input_send_socket: Socket = Socket(
            info=SocketInfo(
                type=zmq.PUSH,
                bind=False,
                addresses=[ZMQAddress(protocol=Protocol.inproc, endpoint="recv")],
            ),
            context=self._context,
        )

        self.output_recv_socket: Socket = Socket(
            info=SocketInfo(
                type=zmq.PULL,
                bind=False,
                addresses=[ZMQAddress(protocol=Protocol.inproc, endpoint="send")],
            ),
            context=self._context,
        )

        self.input_recv_socket.bind_or_connect()
        self.output_send_socket.bind_or_connect()
        self.input_send_socket.bind_or_connect()
        self.output_recv_socket.bind_or_connect()

        logger.name = f"messenger-{self._id}"

    def __del__(self):
        # TODO: implement cleanup
        pass

    @property
    def input_ports(self) -> list[InputJSON]:
        return list(self.input_infos.values())

    @property
    def output_ports(self) -> list[OutputJSON]:
        return list(self.output_infos.values())

    @property
    def type(self):
        return "zmq"

    def recv(self, src: IdType) -> BaseMessage | None:
        try:
            message = self.input_recv_socket.recv_model(flags=zmq.DONTWAIT)
            return message
        except zmq.Again:
            return None

    def send(self, message: BaseMessage, dst: IdType):
        while True:
            try:
                # blocking send
                self.output_send_socket.send_model(message)
                break
            except zmq.Again:
                logger.error(f"{self._id} timeout, retrying...")
                continue

    def start(self, client: AgentClient, pipeline: Pipeline):
        self._setup(client, pipeline)
        while True:
            self._recv_external()
            self._send_external()

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

    def _recv_external(self):
        for port_id, socket in self.input_sockets.items():
            try:
                message = socket.recv_model(flags=zmq.DONTWAIT)
            except zmq.Again:
                continue
            except zmq.ZMQError as e:
                logger.error(f"Failed to receive message on port {port_id}: {e}")

            try:
                self.input_send_socket.send_model(message)
            except zmq.Again:
                logger.error("Timeout on message send.")
                continue
            except zmq.ZMQError as e:
                logger.error(f"Failed to send message to operator: {e}")

    def _send_external(self):
        # TODO: Same message on all output sockets--probably not the way
        # TODO: should we only have one output socket per operator?
        try:
            message = self.output_recv_socket.recv_model(zmq.DONTWAIT)
        except zmq.Again:
            return
        except zmq.ZMQError as e:
            logger.error(f"Failed to receive message: {e}")
            return

        resend: list[UUID] = list(self.output_sockets.keys())
        while resend:
            for port_id in resend:
                try:
                    self.output_sockets[port_id].send_model(message)
                    resend.remove(port_id)
                except zmq.Again:
                    continue
                except zmq.ZMQError as e:
                    logger.error(f"Failed to send message on port {port_id}: {e}")

    def _readiness_check(self):
        # TODO: we should probably have this information in one place rather than in two
        # we could also have inproc sockets that could send to a central place to inform
        # agentclient (and rest of network) that we are ready
        return all(
            [socket.info.connected for socket in self.input_sockets.values()]
            + [socket.info.connected for socket in self.output_sockets.values()]
            + [info.connected for info in self.output_infos.values()]
            + [info.connected for info in self.input_infos.values()]
        )

    @property
    def ready(self):
        return self._readiness_check()
