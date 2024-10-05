import asyncio
import multiprocessing
from datetime import datetime
from enum import Enum
from typing import cast
from uuid import UUID

import zmq
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js import JetStreamContext
from nats.js.errors import KeyNotFoundError
from nats.js.kv import KeyValue
from pydantic import BaseModel, ValidationError

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
from core.models.ports import PortMetrics, PortStatus, PortVal
from core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from core.nats import create_bucket_if_doesnt_exist
from core.pipeline import Pipeline

from ..zsocket import Context, Socket, SocketInfo
from .base import BaseMessenger

logger = get_logger("messenger", "DEBUG")

class InternalInputPortSocks(str, Enum):
    DATA = "data"
    METRICS = "metrics"
    CONNECTIONS = "connections"


class InternalMessageType(str, Enum):
    RECONNECT = "reconnect"
    DISCONNECT = "disconnect"
    STOP = "stop"
    METRICS = "metrics"


class InternalMessageBase(BaseModel):
    type: InternalMessageType


class ReconnectMessage(InternalMessageBase):
    type: InternalMessageType = InternalMessageType.RECONNECT
    id: PortID  # ID to reconnect
    addresses: list[ZMQAddress]  # addresses to reconnect to


class DisconnectMessage(InternalMessageBase):
    type: InternalMessageType = InternalMessageType.DISCONNECT
    id: PortID  # ID to disconnect


class StopMessage(InternalMessageBase):
    type: InternalMessageType = InternalMessageType.STOP


class MetricsMessage(InternalMessageBase):
    type: InternalMessageType = InternalMessageType.METRICS
    metrics: PortMetrics
    parallel_idx: int


def get_internal_input_socket_addr(
    id: PortID, type: InternalInputPortSocks
) -> ZMQAddress:
    if type == InternalInputPortSocks.DATA:
        return ZMQAddress(protocol=Protocol.ipc, endpoint=type.value)
    else:
        return ZMQAddress(protocol=Protocol.ipc, endpoint=type.value + str(id))


class ZmqInputPortWorker:
    def __init__(
        self,
        id: PortID,
        parallel_idx: int,
        upstream_port_addresses: dict[PortID, list[ZMQAddress]],
    ):
        self.port_id = id
        self.parallel_idx = parallel_idx
        self.upstream_port_addresses = upstream_port_addresses
        self.stop_event = asyncio.Event()

    async def start(self):
        await self.setup_sockets()
        recv_task = asyncio.create_task(self.recv_loop())
        connection_task = asyncio.create_task(self.handle_connections())
        metrics_task = asyncio.create_task(self.update_metrics_task())
        await asyncio.wait_for(self.stop_event.wait(), timeout=None)
        await asyncio.gather(recv_task, metrics_task, connection_task)
        self.shutdown()

    def shutdown(self):
        self.recv_socket.close()
        self.send_socket.close()
        self.connection_socket.close()
        self.metrics_socket.close()

    async def setup_sockets(self):
        self.context = Context.instance()

        # Recv data externally and send to operator
        self.recv_socket = self.context.socket(
            info=SocketInfo(type=zmq.PULL, bind=False, port_id=self.port_id)
        )
        self.recv_socket.setsockopt(zmq.RCVTIMEO, 1000)
        for upstream_port, addrs in self.upstream_port_addresses.items():
            self.recv_socket.update_address_map(upstream_port, addrs)

        self.recv_socket.bind_or_connect()

        self.send_socket = self.context.socket(
            info=SocketInfo(type=zmq.PUSH, bind=False, port_id=self.port_id)
        )
        addr = get_internal_input_socket_addr(self.port_id, InternalInputPortSocks.DATA)
        self.send_socket.update_address_map(self.port_id, [addr])
        self.send_socket.bind_or_connect()

        # Subscriber socket to receive reconnection signals
        self.connection_socket = self.context.socket(
            info=SocketInfo(type=zmq.SUB, bind=False, port_id=self.port_id)
        )
        addr = get_internal_input_socket_addr(
            self.port_id, InternalInputPortSocks.CONNECTIONS
        )
        self.connection_socket.update_address_map(self.port_id, [addr])
        self.connection_socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.connection_socket.setsockopt(zmq.RCVTIMEO, 1000)
        self.connection_socket.bind_or_connect()

        # Metrics publisher
        self.metrics_socket = self.context.socket(
            info=SocketInfo(type=zmq.PUB, bind=False, port_id=self.port_id)
        )
        addr = get_internal_input_socket_addr(
            self.port_id, InternalInputPortSocks.METRICS
        )
        self.metrics_socket.update_address_map(self.port_id, [addr])
        self.metrics_socket.bind_or_connect()

    async def update_metrics_task(self):
        while not self.stop_event.is_set():
            metrics = self.recv_socket.metrics
            msg = MetricsMessage(metrics=metrics, parallel_idx=self.parallel_idx)
            await self.metrics_socket.send(msg.model_dump_json().encode())
            await asyncio.sleep(1)

    async def handle_connections(self):
        while not self.stop_event.is_set():
            try:
                msg = await self.connection_socket.recv()
            except zmq.Again:
                continue
            valid_msg = InternalMessageBase.model_validate_json(msg)
            if valid_msg.type == InternalMessageType.RECONNECT:
                logger.info(f"Received reconnect message for port {self.port_id}")
                valid_msg = ReconnectMessage.model_validate_json(msg)
                self.recv_socket.reconnect(valid_msg.id, valid_msg.addresses)

            if valid_msg.type == InternalMessageType.DISCONNECT:
                logger.info(f"Received disconnect message for port {self.port_id}")
                valid_msg = DisconnectMessage.model_validate_json(msg)
                self.recv_socket.disconnect(valid_msg.id)

            if valid_msg.type == InternalMessageType.STOP:
                logger.info(f"Received stop message for port {self.port_id}")
                self.stop_event.set()
                break

        logger.info(f"Exiting handle_connections for port {self.port_id}")

    async def recv_loop(self):
        while not self.stop_event.is_set():
            try:
                msg_parts = await self.recv_socket.recv_multipart()
            except zmq.Again:
                continue
            if len(msg_parts) != 2:
                logger.error(
                    "Received an unexpected number of message parts: %s", len(msg_parts)
                )
                return None
            self.recv_socket.metrics.recv_count += 1
            _header, _data = msg_parts
            self.recv_socket.metrics.recv_bytes += len(_header) + len(_data)

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
                        id=self.port_id, time_after_header_validate=datetime.now()
                    )
                )
            self.send_socket.send_multipart(
                [msg.header.model_dump_json().encode(), msg.data]
            )


class ZmqInputPort:
    def __init__(
        self,
        operator_id: OperatorID,
        js: JetStreamContext,
        info: InputJSON,
        parallelism: int,
        shutdown_event: asyncio.Event,
        upstream_port_ids: list[PortID],
    ):
        self.operator_id = operator_id
        self.js = js
        self.info = info
        self.parallelism = parallelism
        self._shutdown_event = shutdown_event
        self.port_id = info.id
        self.upstream_port_ids = upstream_port_ids

        self.context = Context.instance()
        self.setup_sockets()
        self.processes: list[multiprocessing.Process] = []

        self.val = PortVal(id=self.port_id, status=PortStatus.IDLE)
        self.upstream_port_map: dict[PortID, list[ZMQAddress]] = {}

    async def start(self):
        self.operator_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
        )
        self.metrics_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_METRICS, BUCKET_METRICS_TTL
        )
        for upstream_port_id in self.upstream_port_ids:
            self.upstream_port_map[
                upstream_port_id
            ] = await self.get_upstream_addresses(upstream_port_id)

        self.workers = [
            ZmqInputPortWorker(
                id=self.port_id,
                parallel_idx=i,
                upstream_port_addresses=self.upstream_port_map,
            )
            for i in range(self.parallelism)
        ]

        for worker in self.workers:
            self.processes.append(
                multiprocessing.Process(
                    target=self.start_worker,
                    args=(worker,),
                    daemon=True,
                )
            )
            # start the last process appended
            self.processes[-1].start()

        self.watcher_task = asyncio.create_task(self.upstream_connection_watcher())
        # self.metrics_task = asyncio.create_task(self.update_metrics())

    def setup_sockets(self):
        # Subscriber socket to receive reconnection signals
        self.connection_socket = self.context.socket(
            info=SocketInfo(type=zmq.PUB, bind=True, port_id=self.port_id)
        )
        addr = get_internal_input_socket_addr(
            self.port_id, InternalInputPortSocks.CONNECTIONS
        )
        self.connection_socket.update_address_map(self.port_id, [addr])
        self.connection_socket.bind_or_connect()

        # Metrics publisher
        self.metrics_socket = self.context.socket(
            info=SocketInfo(type=zmq.SUB, bind=True, port_id=self.port_id)
        )
        addr = get_internal_input_socket_addr(
            self.port_id, InternalInputPortSocks.METRICS
        )
        self.metrics_socket.update_address_map(self.port_id, [addr])
        self.metrics_socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.metrics_socket.setsockopt(zmq.RCVTIMEO, 1000)
        self.metrics_socket.bind_or_connect()

    def start_worker(self, worker: ZmqInputPortWorker):
        asyncio.run(worker.start())

    async def stop(self):
        await self.connection_socket.send(StopMessage().model_dump_json().encode())
        for process in self.processes:
            logger.info(f"Waiting for process {process} to join.")
            process.join()
            logger.info(f"Process {process} joined.")

        # await asyncio.gather(self.watcher_task, self.metrics_task)
        self.metrics_socket.close()
        self.connection_socket.close()

    async def update_metrics(self):
        state: dict[int, PortMetrics | None] = {
            idx: None for idx in range(self.parallelism)
        }
        while not self._shutdown_event.is_set():
            try:
                msg = await self.metrics_socket.recv()
            except zmq.Again:
                continue
            valid_msg = MetricsMessage.model_validate_json(msg)
            if valid_msg.parallel_idx not in state:
                logger.warning(
                    f"Received metrics for unknown parallel index: {valid_msg.parallel_idx}"
                )
                await asyncio.sleep(1)
                continue

            state[valid_msg.parallel_idx] = valid_msg.metrics
            if any(metric is None for metric in state.values()):
                continue
            try:
                _ = PortMetrics.combine(list(state.values()))  # type: ignore (type checker doesnt see "any")
            except ValueError as e:
                logger.error(f"Failed to combine metrics: {e}")
                continue
            # await self.metrics_kv.put(
            #     f"{self.operator_id}.{self.port_id}", total.model_dump_json().encode()
            # )
            state = {idx: None for idx in range(self.parallelism)}
            await asyncio.sleep(1)

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
        if not self.upstream_port_ids:
            return

        logger.info(
            f"Starting upstream connection watcher, watching: {self.upstream_port_ids}"
        )
        watchers = await self._initialize_watchers()
        state = {}

        while not self._shutdown_event.is_set():
            update_tasks = [
                asyncio.create_task(watcher.updates(timeout=1))
                for watcher in watchers.values()
            ]
            for task in asyncio.as_completed(update_tasks):
                try:
                    msg = await task
                except NatsTimeoutError:
                    continue
                if not msg:
                    continue
                await self._handle_kv_update(msg, state)

            if self._shutdown_event.is_set():
                for task in update_tasks:
                    task.cancel()

        logger.info("Upstream connection watcher shutting down")

    async def _initialize_watchers(self) -> dict[UUID, KeyValue.KeyWatcher]:
        watchers = {}
        for port_id in self.upstream_port_ids:
            watchers[port_id] = await self.operator_kv.watch(
                port_id, ignore_deletes=False, include_history=False
            )
        return watchers

    async def _handle_kv_update(
        self, msg: KeyValue.Entry, state: dict[UUID, bytes | None]
    ):
        key, val = UUID(msg.key), msg.value
        if key not in state:
            state[key] = val
        if val == state[key]:
            return
        if val is None or val == b"":
            logger.warning(
                f"Port ID {key} has been deleted, sending disconnect to workers."
            )
            await self.connection_socket.send(
                DisconnectMessage(id=key).model_dump_json().encode()
            )
            state[key] = val
            self.upstream_port_map[key] = []
            return
        state[key] = val
        try:
            port_val = PortVal.model_validate_json(val)
        except ValidationError as e:
            logger.error(f"Failed to validate port value: {e}")
            return
        if port_val.uri is None:
            logger.warning(
                f"URI not found for port ID {key}, sending disconnect to workers."
            )
            await self.connection_socket.send(
                DisconnectMessage(id=key).model_dump_json().encode()
            )

            return
        addrs = port_val.uri.query.get("address", [])
        if not addrs:
            logger.warning(f"No addresses found for port {key}")
            return
        addrs = [ZMQAddress.from_address(addr) for addr in addrs]
        if self.upstream_port_map[key] != addrs:
            logger.info(
                f"Sending reconnect message to workers for port {key} with addresses {addrs}"
            )
            await self.connection_socket.send(
                ReconnectMessage(id=key, addresses=addrs).model_dump_json().encode()
            )
            self.upstream_port_map[key] = addrs

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
        self.operator_id: OperatorID = operator_id
        self.js: JetStreamContext = js
        self.update_kv_task: asyncio.Task | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self.recv_queue: asyncio.Queue[BytesMessage] = asyncio.Queue()
        self.recv_socket: Socket = self._context.socket(
            info=SocketInfo(
                type=zmq.PULL,
                bind=True,
                port_id=operator_id,
                address_map={
                    self.operator_id: [
                        get_internal_input_socket_addr(
                            self.operator_id, InternalInputPortSocks.DATA
                        )
                    ]
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
            self.recv_socket.metrics.recv_count += 1
            self.recv_socket.metrics.recv_bytes += len(header) + len(data)
            header = MessageHeader.model_validate_json(header)
            return BytesMessage(header=header, data=data)
        except zmq.Again:
            return None

    async def send(self, message: BytesMessage):
        msg_futures = []
        for socket in self.output_sockets.values():
            if message.header.tracking is not None:
                meta = OutputPortTrackingMetadata(
                    id=socket.info.port_id, time_before_send=datetime.now()
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
        logger.info(f"Setting up operator {self.operator_id}...")
        self.operator_kv = await create_bucket_if_doesnt_exist(
            self.js, BUCKET_OPERATORS, BUCKET_OPERATORS_TTL
        )
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
            await input.stop()

        for socket in self.output_sockets.values():
            socket.close()

    async def update_kv(self):
        while not self._shutdown_event.is_set():
            fut = []

            fut.append(
                self.metrics_kv.put(
                    f"{self.operator_id}.{self.recv_socket.info.port_id}",
                    self.recv_socket.metrics.model_dump_json().encode(),
                )
            )

            for val in self.port_vals.values():
                fut.append(
                    self.operator_kv.put(str(val.id), val.model_dump_json().encode())
                )

            for socket in self.output_sockets.values():
                fut.append(
                    self.metrics_kv.put(
                        f"{self.operator_id}.{socket.info.port_id}",
                        socket.metrics.model_dump_json().encode(),
                    )
                )
            await asyncio.gather(*fut)
            await asyncio.sleep(0.5)
        logger.info(f"Deleting keys: {self.port_vals.keys()} from KV store")
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
                port_id=port_info.id,
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
        for input in pipeline.get_operator_inputs(self.operator_id).values():
            self.input_infos[input.id] = input
            upstream_port_ids = pipeline.get_predecessors(input.id)
            self.inputs[input.id] = ZmqInputPort(
                self.operator_id,
                js=self.js,
                info=input,
                parallelism=4,
                shutdown_event=self._shutdown_event,
                upstream_port_ids=upstream_port_ids,
            )
            self.port_vals[input.id] = PortVal(id=input.id, status=PortStatus.IDLE)
        asyncio.gather(*[input.start() for input in self.inputs.values()])

    async def setup_outputs(self, pipeline: Pipeline):
        for output in pipeline.get_operator_outputs(self.operator_id).values():
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
