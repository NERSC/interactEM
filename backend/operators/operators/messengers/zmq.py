import asyncio

import nats
import nats.js
import nats.js.errors
import zmq
from core.constants import BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
from core.logger import get_logger
from core.models import BaseMessage, IdType, PortJSON, PortType
from core.models.base import OperatorID, PortID, Protocol
from core.models.pipeline import InputJSON, OutputJSON
from core.models.ports import PortStatus, PortVal
from core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from core.pipeline import Pipeline
from nats.js import JetStreamContext
from zmq.asyncio import Context

from ..zsocket import Socket, SocketInfo
from .base import BaseMessenger

logger = get_logger("messenger", "DEBUG")


class ZmqMessenger(BaseMessenger):
    def __init__(
        self,
        operator_id: OperatorID,
        js: JetStreamContext,
    ):
        self.input_infos: dict[PortID, InputJSON] = {}
        self.input_sockets: dict[PortID, Socket] = {}
        self.output_infos: dict[PortID, OutputJSON] = {}
        self.output_sockets: dict[PortID, Socket] = {}
        self.port_vals: dict[PortID, PortVal] = {}
        self._context: Context = Context.instance()
        self._id: OperatorID = operator_id
        self.js: JetStreamContext = js
        self.update_kv_task: asyncio.Task | None = None

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

    async def recv(self, src: IdType) -> BaseMessage | None:
        for socket in self.input_sockets.values():
            msg = await socket.recv(copy=False)
            if isinstance(msg, zmq.Frame):
                return BaseMessage.model_validate_json(msg.bytes)
            elif isinstance(msg, bytes):
                return BaseMessage.model_validate_json(msg)
            else:
                logger.error("Received an unknown message format: %s", msg)
                return None


    async def send(self, message: BaseMessage, dst: IdType):
        logger.info("Sending...")
        for socket in self.output_sockets.values():
            logger.info(f"Sending to {socket.info.addresses}")
            await socket.send(message.model_dump_json().encode())

    async def start(self, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")

        # TODO: make this a util (also present in orchestrator)
        try:
            self.kv = await self.js.key_value(BUCKET_OPERATORS)
        except nats.js.errors.BucketNotFoundError:
            bucket_cfg = nats.js.api.KeyValueConfig(
                bucket=BUCKET_OPERATORS, ttl=BUCKET_OPERATORS_TTL
            )
            self.kv = await self.js.create_key_value(config=bucket_cfg)

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.setup_outputs(pipeline))
                tg.create_task(self.setup_inputs(pipeline))
        except* Exception as e:
            for ex in e.exceptions:
                logger.error(f"Failed to setup operator {self._id}: {ex}")

        self.update_kv_task = asyncio.create_task(self.update_kv())


    async def update_kv(self):
        while True:
            fut = []
            for port_id, val in self.port_vals.items():
                fut.append(self.kv.put(str(port_id), val.model_dump_json().encode()))
            await asyncio.gather(*fut)
            await asyncio.sleep(1)

    def add_socket(self, port_info: PortJSON):
        if port_info.port_type == PortType.output:
            socket_info = SocketInfo(
                type=zmq.PUSH,
                bind=True,
                parent_id=port_info.id,
            )
            sockets = self.output_sockets
        else:
            socket_info = SocketInfo(
                type=zmq.PULL,
                bind=False,
                parent_id=port_info.id,
            )
            sockets = self.input_sockets

        socket = Socket(info=socket_info, context=self._context)
        sockets[port_info.id] = socket

    async def setup_inputs(self, pipeline: Pipeline):
        for input in pipeline.get_operator_inputs(self._id).values():
            self.input_infos[input.id] = input

        for info in self.input_infos.values():
            self.add_socket(info)

        async def get_addresses(
            pipeline: Pipeline, port_id: PortID
        ) -> list[ZMQAddress]:
            addresses = []

            async for pred in pipeline.get_predecessors_async(port_id):
                while True:
                    try:
                        val = await self.kv.get(str(pred))
                        if not val.value:
                            raise nats.js.errors.KeyNotFoundError
                        port_val = PortVal.model_validate_json(val.value)
                        uri = port_val.uri
                        addrs = uri.query.get("address", [])
                        if addrs:
                            addresses.extend(
                                [
                                    ZMQAddress.from_address(addr)
                                    for addr in addrs
                                    if addr
                                ]
                            )
                        break
                    except nats.js.errors.KeyNotFoundError:
                        logger.info(
                            f"Waiting for address for port {port_id} from {pred}..."
                        )
                        await asyncio.sleep(1)

            return addresses

        async def get_addr_and_connect(
            socket: Socket, pipeline: Pipeline, port_id: PortID
        ):
            socket.info.addresses = await get_addresses(pipeline, port_id)
            logger.info(f"Connecting to {socket.info.addresses} on port {port_id}")
            socket.bind_or_connect()

        try:
            async with asyncio.TaskGroup() as tg:
                for port_id, socket in self.input_sockets.items():
                    tg.create_task(get_addr_and_connect(socket, pipeline, port_id))
        except* Exception as e:
            for ex in e.exceptions:
                logger.error(f"Failed to setup operator {self._id}: {ex}")

    async def setup_outputs(self, pipeline: Pipeline):
        for output in pipeline.get_operator_outputs(self._id).values():
            self.output_infos[output.id] = output

        for info in self.output_infos.values():
            self.add_socket(info)

        for port_id, socket in self.output_sockets.items():
            address = ZMQAddress(
                protocol=Protocol.tcp, hostname="localhost", interface="lo"
            )
            socket.update_addresses([address])
            updated, port = socket.bind_or_connect()
            info = self.output_infos[port_id]
            addresses = [a.to_address() for a in socket.info.addresses]

            # TODO: change hostname to environment variable
            uri = URI(
                id=port_id,
                location=URILocation.port,
                hostname="localhost",
                query={"address": addresses},
                comm_backend=CommBackend.ZMQ,
            )
            val = PortVal(uri=uri, status=PortStatus.IDLE)
            await self.kv.put(str(port_id), val.model_dump_json().encode())
            self.port_vals[port_id] = val

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
