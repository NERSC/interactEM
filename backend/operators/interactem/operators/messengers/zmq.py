import asyncio
from collections.abc import Awaitable
from datetime import datetime
from uuid import UUID

import nats
import nats.errors
import nats.js
import nats.js.errors
import nats.js.kv
import zmq
from nats.js import JetStreamContext

from interactem.core.logger import get_logger
from interactem.core.models import PortJSON, PortType
from interactem.core.models.base import IdType, OperatorID, PortID, Protocol
from interactem.core.models.messages import (
    BytesMessage,
    InputPortTrackingMetadata,
    MessageHeader,
    MessageSubject,
    OutputPortTrackingMetadata,
)
from interactem.core.models.pipeline import InputJSON, OutputJSON
from interactem.core.models.ports import PortMetrics, PortStatus, PortVal
from interactem.core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from interactem.core.nats.kv import InteractemBucket, KeyValueLoop
from interactem.core.pipeline import Pipeline

from ..config import cfg
from ..zsocket import Context, Socket, SocketInfo
from .base import (
    BaseMessenger,
)

logger = get_logger()


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
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self.recv_queue: asyncio.Queue[BytesMessage] = asyncio.Queue()
        self.port_kv: KeyValueLoop[PortVal] | None = None
        self.metrics_kv_loop: KeyValueLoop[PortMetrics] | None = None

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

        msg_coros: list[Awaitable[tuple[IdType, list[bytes]]]] = [
            self._recv_and_update_metrics(socket)
            for socket in self.input_sockets.values()
        ]

        id_msgs = await asyncio.gather(*msg_coros)
        all_messages: list[BytesMessage] = []

        for id, msg_parts in id_msgs:
            if len(msg_parts) == 2:
                _header, _data = msg_parts
            elif len(msg_parts) == 3:
                _, _header, _data = msg_parts
            else:
                logger.error(
                    "Received an unexpected number of message parts: %s", len(msg_parts)
                )
                return None

            if isinstance(_header, zmq.Message):
                header = MessageHeader.model_validate_json(_header.bytes)
            elif isinstance(_header, bytes):
                header = MessageHeader.model_validate_json(_header)
            else:
                logger.error("Received an unexpected message type: %s", type(_header))
                continue

            if header.subject != MessageSubject.BYTES:
                logger.error(
                    "Received an unexpected message subject: %s", header.subject
                )
                continue

            msg = (
                BytesMessage(header=header, data=_data.bytes)
                if isinstance(_data, zmq.Message)
                else BytesMessage(header=header, data=_data)
            )
            if header.tracking is not None:
                header.tracking.append(
                    InputPortTrackingMetadata(
                        id=id, time_after_header_validate=datetime.now()
                    )
                )
            all_messages.append(msg)

        if not all_messages:
            logger.warning("No messages were received from any socket.")
            return None

        tasks = [self.recv_queue.put(msg) for msg in all_messages[1:]]
        # TODO: possibly create tasks instead
        await asyncio.gather(*tasks)
        return all_messages[0]

    async def _recv_and_update_metrics(
        self, socket: Socket
    ) -> tuple[IdType, list[bytes]]:
        # TODO: handle timeout
        msg_parts = await socket.recv_multipart()
        socket.metrics.recv_count += 1
        socket.metrics.recv_bytes += sum(len(part) for part in msg_parts)
        return socket.info.parent_id, msg_parts

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
            things_to_send = [header, data]

            if socket.info.type == zmq.PUB:
                # TODO: handle multiple subjects (if needed)
                subject = socket.info.subjects[0]
                things_to_send.insert(0, subject)

            msg_futures.append(self._send_and_update_metrics(socket, things_to_send))
        # TODO: look into creating tasks
        await asyncio.gather(*msg_futures)

    async def _send_and_update_metrics(self, socket: Socket, messages: list[bytes]):
        await socket.send_multipart(messages)
        socket.metrics.send_count += 1
        socket.metrics.send_bytes += sum(len(part) for part in messages)

    async def start(self, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")

        # Initialize KeyValueLoop for operators and metrics
        self.port_kv = KeyValueLoop[PortVal](
            nc=self.js._nc,
            js=self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.OPERATORS,
            update_interval=1.0,
            data_model=PortVal,
        )
        await self.port_kv.start()
        self.operator_kv = await self.port_kv.get_bucket()

        self.metrics_kv_loop = KeyValueLoop[PortMetrics](
            nc=self.js._nc,
            js=self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.METRICS,
            update_interval=1.0,
            data_model=PortMetrics,
        )
        await self.metrics_kv_loop.start()
        self.metrics_kv = await self.metrics_kv_loop.get_bucket()

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

        self.port_kv.cleanup_callbacks.append(
            lambda: logger.info(f"Operator {self._id} shutting down, deleting KV...")
        )
        self.watcher_task = asyncio.create_task(self.upstream_connection_watcher())

    async def stop(self):
        self._shutdown_event.set()
        logger.info("Stopping zmq messenger...")

        if self.port_kv:
            await self.port_kv.stop()

        if self.metrics_kv_loop:
            await self.metrics_kv_loop.stop()

        if self.watcher_task:
            self.watcher_task.cancel()
            try:
                await self.watcher_task
            except asyncio.CancelledError:
                pass

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
            watchers[key] = await self.operator_kv.watch(
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

    def add_socket(self, port_info: PortJSON):
        if port_info.port_type == PortType.output:
            socket_info = SocketInfo(
                type=zmq.PUB,
                subjects=[b"data"],
                bind=True,
                parent_id=port_info.id,
            )
            sockets = self.output_sockets
        else:
            socket_info = SocketInfo(
                type=zmq.SUB,
                subjects=[b"data"],
                bind=False,
                parent_id=port_info.id,
            )
            sockets = self.input_sockets

        socket = self._context.socket(info=socket_info)
        sockets[port_info.id] = socket

    async def setup_inputs(self, pipeline: Pipeline):
        if not self.port_kv:
            raise RuntimeError("Port KeyValueLoop is not initialized.")

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
                port_val = PortVal(
                    id=port,
                    status=PortStatus.IDLE,
                )
                self.port_vals[port] = port_val
                # Register this input port with the KeyValueLoop
                self.port_kv.add_or_update_value(str(port), port_val)

    async def get_upstream_addresses(self, upstream_port: PortID) -> list[ZMQAddress]:
        if not self.port_kv:
            raise RuntimeError("Port KeyValueLoop is not initialized.")
        while True:
            try:
                port_val = await self.port_kv.get_val(upstream_port)
                if port_val is None:
                    await asyncio.sleep(1)
                    continue
                uri = port_val.uri
                if not uri:
                    await asyncio.sleep(1)
                    continue
                addrs = uri.query.get("address", [])
                addresses = [ZMQAddress.from_address(addr) for addr in addrs]
                return addresses
            except nats.js.errors.KeyNotFoundError:
                await asyncio.sleep(1)

    async def setup_outputs(self, pipeline: Pipeline):
        if not self.port_kv:
            raise RuntimeError("Port KeyValueLoop is not initialized.")
        if not self.metrics_kv_loop:
            raise RuntimeError("Metrics KeyValueLoop is not initialized.")

        for output in pipeline.get_operator_outputs(self._id).values():
            self.output_infos[output.id] = output

        for info in self.output_infos.values():
            self.add_socket(info)

        for port_id, socket in self.output_sockets.items():
            address = ZMQAddress(
                protocol=Protocol.tcp,
                hostname=cfg.ZMQ_BIND_HOSTNAME,
                interface=cfg.ZMQ_BIND_INTERFACE,
            )
            socket.update_address_map(port_id, [address])
            socket.bind_or_connect()
            info = self.output_infos[port_id]
            addresses = [a.to_address() for a in socket.info.address_map[port_id]]

            uri = URI(
                id=port_id,
                location=URILocation.port,
                hostname=cfg.ZMQ_BIND_HOSTNAME,
                query={"address": addresses},
                comm_backend=CommBackend.ZMQ,
            )
            self.port_vals[port_id] = PortVal(
                id=port_id, uri=uri, status=PortStatus.IDLE
            )

            self.port_kv.add_or_update_value(
                str(port_id), lambda port_id=port_id: self.port_vals[port_id]
            )

        await self.port_kv.update_now()

        def get_metrics_for_all_sockets() -> dict[str, PortMetrics]:
            metrics_data = {}
            all_sockets = list(self.input_sockets.values()) + list(
                self.output_sockets.values()
            )
            for socket in all_sockets:
                key = f"{self._id}.{socket.info.parent_id}"
                metrics_data[key] = socket.metrics
            return metrics_data

        # Register metrics update function, occurs before a KV update
        self.metrics_kv_loop.before_update_callbacks.append(
            lambda: self._update_metrics(get_metrics_for_all_sockets())
        )

    async def _update_metrics(self, metrics_dict: dict[str, PortMetrics]) -> None:
        if self.metrics_kv_loop:
            for key, metrics in metrics_dict.items():
                self.metrics_kv_loop.add_or_update_value(key, metrics)

    # TODO: implement
    @property
    def ready(self):
        return True
