import asyncio
from collections.abc import Awaitable
from uuid import UUID

import nats
import nats.errors
import nats.js
import nats.js.errors
import nats.js.kv
import zmq
from nats.js import JetStreamContext
from nats.js.errors import BucketNotFoundError

from core.constants import BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
from core.logger import get_logger
from core.models import PortJSON, PortType
from core.models.base import OperatorID, PortID, Protocol
from core.models.pipeline import InputJSON, OutputJSON
from core.models.ports import PortStatus, PortVal
from core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from core.pipeline import Pipeline

from ..messengers.base import BytesMessage
from ..zsocket import Context, Socket, SocketInfo
from .base import BaseMessenger, MessageHeader, MessageSubject

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
        # Upstream Port -> these ports
        self.upstream_port_map: dict[PortID, list[PortID]] = {}
        self._context: Context = Context.instance()
        self._id: OperatorID = operator_id
        self.js: JetStreamContext = js
        self.update_kv_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self.recv_queue: asyncio.Queue[BytesMessage] = asyncio.Queue()

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

    async def recv(self) -> BytesMessage | None:
        try:
            return self.recv_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        msg_coros: list[Awaitable[list[bytes]]] = [
            self._recv_and_update_metrics(socket)
            for socket in self.input_sockets.values()
        ]

        msgs = await asyncio.gather(*msg_coros)

        all_messages: list[BytesMessage] = []

        for msg_parts in msgs:
            if len(msg_parts) != 2:
                logger.error(
                    "Received an unexpected number of message parts: %s", len(msg_parts)
                )
                return None

            header, data = msg_parts

            if isinstance(header, zmq.Message):
                header = MessageHeader.model_validate_json(header.bytes)
            elif isinstance(header, bytes):
                header = MessageHeader.model_validate_json(header)
            else:
                logger.error("Received an unexpected message type: %s", type(header))
                continue

            if header.subject != MessageSubject.BYTES:
                logger.error(
                    "Received an unexpected message subject: %s", header.subject
                )
                continue

            msg = (
                BytesMessage(header=header, data=data.bytes)
                if isinstance(data, zmq.Message)
                else BytesMessage(header=header, data=data)
            )
            all_messages.append(msg)

        if not all_messages:
            logger.warning("No messages were received from any socket.")
            return None

        tasks = [self.recv_queue.put(msg) for msg in all_messages[1:]]
        await asyncio.gather(*tasks)
        return all_messages[0]

    async def _recv_and_update_metrics(self, socket: Socket) -> list[bytes]:
        # TODO: handle timeout
        msg_parts = await socket.recv_multipart()
        socket.metrics.recv_count += 1
        socket.metrics.recv_bytes += sum(len(part) for part in msg_parts)
        return msg_parts

    async def send(self, message: BytesMessage):
        msg_futures = []
        for socket in self.output_sockets.values():
            data = message.data
            header = message.header.model_dump_json().encode()
            msg_futures.append(socket.send_multipart([header, data]))
        await asyncio.gather(*msg_futures)

    async def start(self, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")

        # TODO: make this a util (also present in orchestrator)
        try:
            self.kv = await self.js.key_value(BUCKET_OPERATORS)
        except BucketNotFoundError:
            bucket_cfg = nats.js.api.KeyValueConfig(
                bucket=BUCKET_OPERATORS, ttl=BUCKET_OPERATORS_TTL
            )
            self.kv = await self.js.create_key_value(config=bucket_cfg)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self.setup_outputs(pipeline), self.setup_inputs(pipeline)
                ),
                timeout=10,
            )
        except asyncio.TimeoutError as e:
            logger.info(f"Failed to setup zmq messenger within timeout: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to setup zmq messenger: {e}")
            raise e

        self.update_kv_task = asyncio.create_task(self.update_kv())
        self.watcher_task = asyncio.create_task(self.upstream_connection_watcher())

    async def stop(self):
        self._shutdown_event.set()
        logger.info("Stopping zmq messenger...")
        if self.update_kv_task:
            await self.update_kv_task

        if self.watcher_task:
            await self.watcher_task

        for socket in self.input_sockets.values():
            socket.close()
        for socket in self.output_sockets.values():
            socket.close()

    async def upstream_connection_watcher(self):
        upstream_ports = list(self.upstream_port_map.keys())
        if len(upstream_ports) == 0:
            return
        logger.info(f"Starting upstream connection watcher, watching: {upstream_ports}")
        watchers: dict[UUID, nats.js.kv.KeyValue.KeyWatcher] = {}
        for key in upstream_ports:
            watchers[key] = await self.kv.watch(
                key, ignore_deletes=False, include_history=False
            )

        state: dict[UUID, bytes | None] = {}
        while not self._shutdown_event.is_set():
            update_tasks = [
                asyncio.create_task(watcher.updates(timeout=1))
                for watcher in watchers.values()
            ]

            for task in asyncio.as_completed(update_tasks):
                try:
                    msg = await task  # Await the result of the completed task
                except nats.errors.TimeoutError:
                    pass
                if not msg:
                    continue
                key, val = UUID(msg.key), msg.value
                if key not in state:
                    state[key] = val
                if val == state[key]:
                    continue
                if val is None or val == b"":
                    logger.warning(f"Key {key} has been deleted")
                    ids_to_disconnect = self.upstream_port_map[key]
                    for id in ids_to_disconnect:
                        self.input_sockets[id].disconnect(key)
                    state[key] = val
                    continue
                state[key] = val
                val = PortVal.model_validate_json(val)
                addrs = val.uri.query.get("address", [])
                if not addrs:
                    logger.warning(f"No addresses found for port {key}")
                    continue
                addrs = [ZMQAddress.from_address(addr) for addr in addrs]
                for id in self.upstream_port_map[key]:
                    self.input_sockets[id].reconnect(key, addrs)

            # If shutdown is requested, cancel all pending tasks
            if self._shutdown_event.is_set():
                for task in update_tasks:
                    task.cancel()

        logger.info("Upstream connection watcher shutting down")

    async def update_kv(self):
        while not self._shutdown_event.is_set():
            fut = []
            for port_id, val in self.port_vals.items():
                fut.append(self.kv.put(str(port_id), val.model_dump_json().encode()))
            await asyncio.gather(*fut)
            await asyncio.sleep(1)
        logger.info(f"Operator {self._id} shutting down, deleting KV...")
        logger.info("Removing ports from KV store...")
        logger.info(f"Deleting keys: {self.port_vals.keys()}")
        fut = [self.kv.delete(str(port_id)) for port_id in self.port_vals.keys()]
        await asyncio.gather(*fut)
        logger.info("KV store cleanup complete")

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

        socket = self._context.socket(info=socket_info)
        sockets[port_info.id] = socket

    async def setup_inputs(self, pipeline: Pipeline):
        for input in pipeline.get_operator_inputs(self._id).values():
            self.input_infos[input.id] = input

        for info in self.input_infos.values():
            self.add_socket(info)

        for port_id in self.input_sockets.keys():
            predecessors = pipeline.get_predecessors(port_id)
            for pred in predecessors:
                if self.upstream_port_map.get(pred) is None:
                    self.upstream_port_map[pred] = []
                self.upstream_port_map[pred].append(port_id)

        for upstream_port, port_ids in self.upstream_port_map.items():
            addrs = await self.get_upstream_addresses(upstream_port)
            for port in port_ids:
                self.input_sockets[port].update_address_map(upstream_port, addrs)
                self.input_sockets[port].bind_or_connect()

    async def get_upstream_addresses(self, upstream_port: PortID) -> list[ZMQAddress]:
        while True:
            try:
                val = await self.kv.get(str(upstream_port))
                if not val.value:
                    raise nats.js.errors.KeyNotFoundError
                port_val = PortVal.model_validate_json(val.value)
                uri = port_val.uri
                addrs = uri.query.get("address", [])
                addresses = [ZMQAddress.from_address(addr) for addr in addrs]
                return addresses
            except nats.js.errors.KeyNotFoundError:
                await asyncio.sleep(1)

    async def setup_outputs(self, pipeline: Pipeline):
        for output in pipeline.get_operator_outputs(self._id).values():
            self.output_infos[output.id] = output

        for info in self.output_infos.values():
            self.add_socket(info)

        for port_id, socket in self.output_sockets.items():
            # TODO: make interface/hostname configurable
            address = ZMQAddress(
                protocol=Protocol.tcp, hostname="localhost", interface="lo"
            )
            socket.update_address_map(port_id, [address])
            socket.bind_or_connect()
            info = self.output_infos[port_id]
            addresses = [a.to_address() for a in socket.info.address_map[port_id]]

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

    # TODO: implement
    @property
    def ready(self):
        return True
