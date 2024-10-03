import asyncio
import multiprocessing
from datetime import datetime
from typing import cast
from uuid import UUID

import zmq
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js import JetStreamContext
from nats.js.errors import KeyNotFoundError
from nats.js.kv import KeyValue

from core.constants import (
    BUCKET_METRICS,
    BUCKET_METRICS_TTL,
    BUCKET_OPERATORS,
    BUCKET_OPERATORS_TTL,
)
from core.logger import get_logger
from core.models import PortJSON, PortType
from core.models.base import OperatorID, PortID, Protocol
from core.models.messages import (
    BytesMessage,
    InputPortTrackingMetadata,
    MessageHeader,
    MessageSubject,
    OutputPortTrackingMetadata,
)
from core.models.pipeline import InputJSON, OutputJSON
from core.models.ports import PortStatus, PortVal
from core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from core.nats import create_bucket_if_doesnt_exist
from core.pipeline import Pipeline

from ..zsocket import Context, Socket, SocketInfo
from .base import (
    BaseMessenger,
)

logger = get_logger("messenger", "DEBUG")

class ZmqInputPort:
    async def __init__(
        self,
        js: JetStreamContext,
        info: InputJSON,
        parallelism: int,
        shutdown_event: asyncio.Event,
        upstream_port_ids: list[PortID],
    ):
        self.id = info.id
        self.info = info
        self.parallelism = parallelism
        self.js = js
        self._shutdown_event = shutdown_event
        self.processes: list[multiprocessing.Process] = []
        self.metrics_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.operator_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
        )
        self.upstream_ports: list[PortID] = upstream_port_ids
        self.watcher_task = asyncio.create_task(self.upstream_connection_watcher())
        self.manager = multiprocessing.Manager()
        self.val = PortVal(id=self.id, status=PortStatus.IDLE)
        self.upstream_port_map: dict[PortID, list[ZMQAddress]] = {}

    async def start_processes(self):
        for parallel_idx in range(self.parallelism):
            self.processes.append(
                multiprocessing.Process(
                    target=self.worker,
                    args=(
                        self.id,
                        parallel_idx,
                        self.metrics_queue,
                        self.upstream_port_map,
                    ),
                    daemon=True,
                )
            )
            self.processes[-1].start()

    async def start(self):
        for process in self.processes:
            process.join()
            process.kill()

        for upstream_port_id in self.upstream_ports:
            self.upstream_port_map[
                upstream_port_id
            ] = await self.get_upstream_addresses(upstream_port_id)

        await self.start_processes()

        upstream_task = asyncio.create_task(self.upstream_connection_watcher())
        asyncio.gather(upstream_task)

    @staticmethod
    async def recv_loop(recv_socket: Socket, send_socket: Socket):
        id = recv_socket.info.parent_id
        while True:
            msg_parts = await recv_socket.recv_multipart()
            if len(msg_parts) != 2:
                logger.error(
                    "Received an unexpected number of message parts: %s", len(msg_parts)
                )
                return None
            recv_socket.metrics.recv_count += 1
            _header, _data = msg_parts
            recv_socket.metrics.recv_bytes += len(_header) + len(_data)

            if isinstance(_header, zmq.Message):
                header = MessageHeader.model_validate_json(_header.bytes)
                _data = cast(zmq.Message, _data)
                msg = BytesMessage(header=header, data=_data.bytes)
            elif isinstance(_header, bytes):
                header = MessageHeader.model_validate_json(_header)
                _data = cast(bytes, _data)
                msg = BytesMessage(header=header, data=_data)
            else:
                logger.error("Received an unexpected message type: %s", type(_header))
                continue

            if header.subject != MessageSubject.BYTES:
                logger.error(
                    "Received an unexpected message subject: %s", header.subject
                )
                continue

            if header.tracking is not None:
                header.tracking.append(
                    InputPortTrackingMetadata(
                        id=id, time_after_header_validate=datetime.now()
                    )
                )
            send_socket.send_multipart(
                [msg.header.model_dump_json().encode(), msg.data]
            )

    @staticmethod
    async def update_metrics_task(
        socket: Socket, metrics_queue: multiprocessing.Queue, parallel_idx: int
    ):
        while True:
            metrics = socket.metrics.model_dump()
            metrics_queue.put((parallel_idx, metrics))
            await asyncio.sleep(1)

    @staticmethod
    async def async_worker(
        id: PortID,
        parallel_idx: int,
        metrics_queue: multiprocessing.Queue,
        upstream_port_addresses: dict[PortID, list[ZMQAddress]],
    ):
        context = Context.instance()
        sock_info = SocketInfo(type=zmq.PULL, bind=False, parent_id=id)
        recv_socket = context.socket(info=sock_info)
        send_socket = context.socket(
            info=SocketInfo(type=zmq.PUSH, bind=False, parent_id=id)
        )
        send_socket_addr = ZMQAddress(
            protocol=Protocol.ipc,
            hostname="hello",
        )
        send_socket.update_address_map(
            id,
            [send_socket_addr],
        )

        for upstream_port, addrs in upstream_port_addresses.items():
            recv_socket.update_address_map(upstream_port, addrs)
            recv_socket.bind_or_connect()

        recv_task = asyncio.create_task(
            ZmqInputPort.recv_loop(recv_socket, send_socket)
        )
        metrics_task = asyncio.create_task(
            ZmqInputPort.update_metrics_task(recv_socket, metrics_queue, parallel_idx)
        )
        asyncio.gather(recv_task, metrics_task)

    @staticmethod
    def worker(
        id: PortID,
        parallel_idx: int,
        metrics_queue: multiprocessing.Queue,
        upstream_port_addresses: dict[PortID, list[ZMQAddress]],
    ):
        asyncio.run(
            ZmqInputPort.async_worker(
                id,
                parallel_idx,
                metrics_queue,
                upstream_port_addresses,
            )
        )

    async def get_upstream_addresses(self, upstream_port: PortID) -> list[ZMQAddress]:
        while True:
            try:
                val = await self.operator_kv.get(str(upstream_port))
                if not val.value:
                    raise KeyNotFoundError
                port_val = PortVal.model_validate_json(val.value)
                uri = port_val.uri
                if not uri:
                    await asyncio.sleep(1)
                    continue
                addrs = uri.query.get("address", [])
                addresses = [ZMQAddress.from_address(addr) for addr in addrs]
                return addresses
            except KeyNotFoundError:
                await asyncio.sleep(1)

    async def upstream_connection_watcher(self):
        if len(self.upstream_ports) == 0:
            return
        logger.info(
            f"Starting upstream connection watcher, watching: {self.upstream_ports}"
        )
        watchers: dict[UUID, KeyValue.KeyWatcher] = {}
        for port_id in self.upstream_ports:
            watchers[port_id] = await self.operator_kv.watch(
                port_id, ignore_deletes=False, include_history=False
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
                except NatsTimeoutError:
                    continue
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
                if val.uri is None:
                    logger.warning(f"URI not found for port {key}")
                    ids_to_disconnect = self.upstream_port_map[key]
                    for id in ids_to_disconnect:
                        self.input_sockets[id].disconnect(key)
                    continue
                addrs = val.uri.query.get("address", [])
                if not addrs:
                    logger.warning(f"No addresses found for port {key}")
                    continue
                addrs = [ZMQAddress.from_address(addr) for addr in addrs]
                for id in self.upstream_port_map[key]:
                    if self.input_sockets[id].info.address_map.get(key) != addrs:
                        self.input_sockets[id].reconnect(key, addrs)

            # If shutdown is requested, cancel all pending tasks
            if self._shutdown_event.is_set():
                for task in update_tasks:
                    task.cancel()

        logger.info("Upstream connection watcher shutting down")


class ZmqMessenger(BaseMessenger):
    def __init__(
        self,
        operator_id: OperatorID,
        js: JetStreamContext,
    ):
        self.inputs: dict[PortID, ZmqInputPort] = {}
        self.input_infos: dict[PortID, InputJSON] = {}
        self.output_infos: dict[PortID, OutputJSON] = {}
        self.output_sockets: dict[PortID, Socket] = {}
        self.port_vals: dict[PortID, PortVal] = {}
        # Upstream Port -> these ports

        self._context: Context = Context.instance()

        self._id: OperatorID = operator_id
        self.js: JetStreamContext = js
        self.update_kv_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self.recv_queue: asyncio.Queue[BytesMessage] = asyncio.Queue()
        self.recv_socket: Socket = self._context.socket(
            info=SocketInfo(
                type=zmq.PULL,
                bind=True,
                parent_id=operator_id,
                address_map={
                    self._id: [ZMQAddress(protocol=Protocol.ipc, hostname="hello")]
                },
            )
        )
        self.recv_socket.bind_or_connect()

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
            header, data = await self.recv_socket.recv_multipart()
            header = MessageHeader.model_validate_json(header)
            return BytesMessage(header=header, data=data)
        except zmq.Again:
            return None

    async def send(self, message: BytesMessage):
        msg_futures = []
        for socket in self.output_sockets.values():
            if message.header.tracking is not None:
                meta = OutputPortTrackingMetadata(
                    id=socket.info.parent_id, time_before_send=datetime.now()
                )
                message.header.tracking.append(meta)
            data = message.data
            header = message.header.model_dump_json().encode()
            msg_futures.append(self._send_and_update_metrics(socket, [header, data]))
        await asyncio.gather(*msg_futures)

    async def _send_and_update_metrics(self, socket: Socket, messages: list[bytes]):
        await socket.send_multipart(messages)
        socket.metrics.send_count += 1
        socket.metrics.send_bytes += sum(len(part) for part in messages)

    async def start(self, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")
        self.metrics_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_METRICS, BUCKET_METRICS_TTL
        )

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

    async def stop(self):
        self._shutdown_event.set()
        logger.info("Stopping zmq messenger...")
        if self.update_kv_task:
            await self.update_kv_task

        for input in self.inputs.values():
            input.shutdown()
        for socket in self.output_sockets.values():
            socket.close()

    async def update_kv(self):
        while not self._shutdown_event.is_set():
            fut = []
            for val in self.port_vals.values():
                fut.append(
                    self.operator_kv.put(str(val.id), val.model_dump_json().encode())
                )
            all_sockets = list(self.input_sockets.values()) + list(
                self.output_sockets.values()
            )
            for socket in all_sockets:
                fut.append(
                    self.metrics_kv.put(
                        f"{self._id}.{socket.info.parent_id}",
                        socket.metrics.model_dump_json().encode(),
                    )
                )
            await asyncio.gather(*fut)
            await asyncio.sleep(1)
        logger.info(f"Operator {self._id} shutting down, deleting KV...")
        logger.info("Removing ports from KV store...")
        logger.info(f"Deleting keys: {self.port_vals.keys()}")
        fut = [
            self.operator_kv.delete(str(port_id)) for port_id in self.port_vals.keys()
        ]
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
            logger.error(
                "Input ports are not supported inside zmq messenger. They belong in ZmqInputPort."
            )
            return

        socket = self._context.socket(info=socket_info)
        sockets[port_info.id] = socket


    async def setup_inputs(self, pipeline: Pipeline):

        for input in pipeline.get_operator_inputs(self._id).values():
            upstream_port_ids = pipeline.get_predecessors(input.id)
            self.inputs[input.id] = ZmqInputPort(
                js=self.js,
                info=input,
                parallelism=1,
                shutdown_event=self._shutdown_event,
                upstream_port_ids=upstream_port_ids,
            )



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
            val = PortVal(id=port_id, uri=uri, status=PortStatus.IDLE)
            await self.operator_kv.put(str(val.id), val.model_dump_json().encode())
            self.port_vals[port_id] = val

    # TODO: implement
    @property
    def ready(self):
        return True
