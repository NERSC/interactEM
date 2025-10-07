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

from interactem.core.constants import PORTS
from interactem.core.logger import get_logger
from interactem.core.models.base import IdType, Protocol
from interactem.core.models.kvs import PortStatus, PortVal
from interactem.core.models.messages import (
    BytesMessage,
    InputPortTrackingMetadata,
    MessageHeader,
    MessageSubject,
    OutputPortTrackingMetadata,
)
from interactem.core.models.metrics import PortMetrics
from interactem.core.models.runtime import (
    RuntimeInput,
    RuntimeOperatorID,
    RuntimeOutput,
    RuntimePort,
    RuntimePortID,
)
from interactem.core.models.uri import URI, CommBackend, URILocation, ZMQAddress
from interactem.core.nats.kv import InteractemBucket, KeyValueLoop
from interactem.core.pipeline import Pipeline

from ..config import cfg
from ..zsocket import Context, Socket, SocketInfo
from .base import (
    BaseMessenger,
)

PORTS_KV_UPDATE_INTERVAL = 1.0  # seconds
METRICS_KV_UPDATE_INTERVAL = 1.0


logger = get_logger()

UpstreamPortID = RuntimePortID
ThisOperatorPortID = RuntimePortID


class ZmqMessenger(BaseMessenger):
    def __init__(
        self,
        operator_id: RuntimeOperatorID,
        js: JetStreamContext,
    ):
        self._input_ports: dict[RuntimePortID, RuntimeInput] = {}
        self.input_sockets: dict[RuntimePortID, Socket] = {}
        self._output_ports: dict[RuntimePortID, RuntimeOutput] = {}
        self.output_sockets: dict[RuntimePortID, Socket] = {}
        self.port_vals: dict[RuntimePortID, PortVal] = {}
        # Upstream Port -> these ports
        self.upstream_port_map: dict[UpstreamPortID, list[ThisOperatorPortID]] = {}
        self._context: Context = Context.instance()
        self._id: RuntimeOperatorID = operator_id
        self.js: JetStreamContext = js
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self.recv_queue: asyncio.Queue[BytesMessage] = asyncio.Queue()
        self.port_kv_loop: KeyValueLoop[PortVal] | None = None
        self.port_metrics_kv_loop: KeyValueLoop[PortMetrics] | None = None

    def __del__(self):
        # TODO: implement cleanup
        pass

    @property
    def input_ports(self) -> list[RuntimeInput]:
        return list(self._input_ports.values())

    @property
    def output_ports(self) -> list[RuntimeOutput]:
        return list(self._output_ports.values())

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
            raw_meta = None

            if len(msg_parts) == 2:
                _header, _data = msg_parts
            elif len(msg_parts) == 3:
                _header, raw_meta, _data = msg_parts
            else:
                return None

            # Decode header JSON
            if isinstance(_header, zmq.Message):
                header = MessageHeader.model_validate_json(_header.bytes)
            elif isinstance(_header, bytes):
                header = MessageHeader.model_validate_json(_header)
            else:
                continue

            # If meta was sent separately as bytes, restore it
            if raw_meta is not None:
                if isinstance(raw_meta, zmq.Message):
                    header.meta = raw_meta.bytes
                else:
                    header.meta = raw_meta

            if header.subject != MessageSubject.BYTES:
                logger.error(
                    "Received an unexpected message subject: %s", header.subject
                )
                continue

            if isinstance(_data, zmq.Message):
                msg = BytesMessage(header=header, data=_data.bytes)
            else:
                msg = BytesMessage(header=header, data=_data)

            # Tracking update
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
        return socket.info.port_id, msg_parts

    async def send(self, message: BytesMessage):
        msg_futures = []
        data = message.data
        should_copy_header = len(self.output_ports) > 1
        for socket in self.output_sockets.values():
            if should_copy_header:
                header = message.header.model_copy()
            else:
                header = message.header

            if header.tracking is not None:
                time_before_send = datetime.now()
                meta = OutputPortTrackingMetadata(
                    id=socket.info.port_id, time_before_send=time_before_send
                )
                header.tracking.append(meta)

            # --- Separate meta if it's bytes ---
            raw_meta = None
            if isinstance(header.meta, bytes):
                raw_meta = header.meta
                header_json = header.model_dump_json(exclude={"meta"}).encode()
            else:
                header_json = header.model_dump_json().encode()

            # --- Build multipart message ---
            if raw_meta is not None:
                things_to_send = [header_json, raw_meta, data]
            else:
                things_to_send = [header_json, data]

            msg_futures.append(self._send_and_update_metrics(socket, things_to_send))
        # TODO: look into creating tasks
        await asyncio.gather(*msg_futures)

    async def _send_and_update_metrics(self, socket: Socket, messages: list[bytes]):
        await socket.send_multipart(messages)
        socket.metrics.send_count += 1
        socket.metrics.send_bytes += sum(len(part) for part in messages)

    async def start(self, pipeline: Pipeline):
        logger.info(f"Setting up operator {self._id}...")

        # Initialize KeyValueLoop for ports and port metrics
        self.port_kv_loop = KeyValueLoop[PortVal](
            nc=self.js._nc,
            js=self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.STATUS,
            update_interval=PORTS_KV_UPDATE_INTERVAL,
            data_model=PortVal,
        )
        await self.port_kv_loop.start()
        self.port_kv_bucket = await self.port_kv_loop.get_bucket()

        self.port_metrics_kv_loop = KeyValueLoop[PortMetrics](
            nc=self.js._nc,
            js=self.js,
            shutdown_event=self._shutdown_event,
            bucket=InteractemBucket.METRICS,
            update_interval=METRICS_KV_UPDATE_INTERVAL,
            data_model=PortMetrics,
        )
        await self.port_metrics_kv_loop.start()

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

        # Register socket metrics update function
        self.port_metrics_kv_loop.before_update_callbacks.append(
            lambda: self._update_metrics(self.get_metrics_for_all_sockets())
        )

        self.port_kv_loop.cleanup_callbacks.append(
            lambda: logger.info(
                f"Operator {self._id} shutting down, deleting port watcher KV loop..."
            )
        )
        self.watcher_task = asyncio.create_task(self.upstream_connection_watcher())

    def get_metrics_for_all_sockets(self) -> list[PortMetrics]:
        metrics: list[PortMetrics] = [
            s.metrics for s in self.input_sockets.values()
        ] + [s.metrics for s in self.output_sockets.values()]
        return metrics

    async def stop(self):
        self._shutdown_event.set()
        logger.info("Stopping zmq messenger...")

        if self.port_kv_loop:
            await self.port_kv_loop.stop()

        if self.port_metrics_kv_loop:
            await self.port_metrics_kv_loop.stop()

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
        """
        Watch for changes in upstream port addresses and update input sockets accordingly.
        """
        upstream_port_ids = list(self.upstream_port_map.keys())
        if len(upstream_port_ids) == 0:
            return
        logger.info(
            f"Starting upstream connection watcher, watching: {upstream_port_ids}"
        )
        watchers: dict[UpstreamPortID, nats.js.kv.KeyValue.KeyWatcher] = {}
        for id in upstream_port_ids:
            # TODO: use port.key() instead of constructing the key manually
            watchers[id] = await self.port_kv_bucket.watch(
                f"{PORTS}.{id}", ignore_deletes=False, include_history=False
            )

        state: dict[UpstreamPortID, bytes | None] = {}
        while not self._shutdown_event.is_set():
            update_tasks = [
                asyncio.create_task(watcher.updates(timeout=1))
                for watcher in watchers.values()
            ]

            for task in asyncio.as_completed(update_tasks):
                try:
                    msg = await task
                except nats.errors.TimeoutError:
                    pass
                if not msg:
                    continue
                id, val = UUID(msg.key.removeprefix(PORTS)), msg.value
                if id not in state:
                    state[id] = val
                if val == state[id]:
                    continue
                if val is None or val == b"":
                    logger.warning(f"Port ID {id} has been removed, disconnecting...")
                    ids_to_disconnect = self.upstream_port_map[id]
                    for id in ids_to_disconnect:
                        self.input_sockets[id].disconnect(id)
                    state[id] = val
                    continue
                state[id] = val
                val = PortVal.model_validate_json(val)
                if val.uri is None:
                    logger.warning(f"URI not found for port {id}")
                    ids_to_disconnect = self.upstream_port_map[id]
                    for id in ids_to_disconnect:
                        self.input_sockets[id].disconnect(id)
                    continue
                addrs = val.uri.query.get("address", [])
                if not addrs:
                    logger.warning(f"No addresses found for port {id}")
                    continue
                addrs = [ZMQAddress.from_address(addr) for addr in addrs]
                for my_id in self.upstream_port_map[id]:
                    if self.input_sockets[my_id].info.address_map.get(id) != addrs:
                        self.input_sockets[my_id].reconnect(id, addrs)

            # If shutdown is requested, cancel all pending tasks
            if self._shutdown_event.is_set():
                for task in update_tasks:
                    task.cancel()

        logger.info("Upstream connection watcher shutting down")

    def add_input_socket(self, port_info: RuntimePort):
        socket_info = SocketInfo(
            type=zmq.PULL,
            bind=False,
            port_id=port_info.id,
            canonical_port_id=port_info.canonical_id,
            operator_id=port_info.operator_id,
        )
        socket = self._context.socket(info=socket_info)
        self.input_sockets[port_info.id] = socket

    def add_output_socket(self, port_info: RuntimePort):
        socket_info = SocketInfo(
            type=zmq.PUSH,
            bind=True,
            port_id=port_info.id,
            canonical_port_id=port_info.canonical_id,
            operator_id=port_info.operator_id,
        )
        socket = self._context.socket(info=socket_info)
        self.output_sockets[port_info.id] = socket

    async def setup_inputs(self, pipeline: Pipeline):
        if not self.port_kv_loop:
            raise RuntimeError("Port KeyValueLoop is not initialized.")

        for input in pipeline.get_operator_inputs(self._id).values():
            self._input_ports[input.id] = input

        for info in self._input_ports.values():
            self.add_input_socket(info)

        for port_id in self.input_sockets.keys():
            predecessors: list[UpstreamPortID] = pipeline.get_predecessors(port_id)
            for pred_id in predecessors:
                if self.upstream_port_map.get(pred_id) is None:
                    self.upstream_port_map[pred_id] = []
                self.upstream_port_map[pred_id].append(port_id)

        for upstream_port_id, my_port_ids in self.upstream_port_map.items():
            # TODO: this should be a non-blocking call
            addrs = await self.get_upstream_addresses(upstream_port_id)
            for id in my_port_ids:
                self.input_sockets[id].update_address_map(upstream_port_id, addrs)
                self.input_sockets[id].bind_or_connect()
                port_val = PortVal(
                    id=id,
                    canonical_id=self._input_ports[id].canonical_id,
                    status=PortStatus.IDLE,
                )
                self.port_vals[id] = port_val

                # register the port in the KeyValueLoop
                self.port_kv_loop.add_or_update_value(port_val.key(), port_val)

    async def get_upstream_addresses(
        self, upstream_port: UpstreamPortID
    ) -> list[ZMQAddress]:
        if not self.port_kv_loop:
            raise RuntimeError("Port KeyValueLoop is not initialized.")

        while True:
            try:
                upstream_key = PORTS + f".{upstream_port}"
                port_val = await self.port_kv_loop.get_val(upstream_key)
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
        if not self.port_kv_loop:
            raise RuntimeError("Port KeyValueLoop is not initialized.")
        if not self.port_metrics_kv_loop:
            raise RuntimeError("Metrics KeyValueLoop is not initialized.")

        for output in pipeline.get_operator_outputs(self._id).values():
            self._output_ports[output.id] = output

        for output_port in self._output_ports.values():
            self.add_output_socket(output_port)

        # Bind all output sockets and publish their addresses
        for port_id, socket in self.output_sockets.items():
            address = ZMQAddress(
                protocol=Protocol.tcp,
                hostname=cfg.ZMQ_BIND_HOSTNAME,
                interface=cfg.ZMQ_BIND_INTERFACE,
            )
            socket.update_address_map(port_id, [address])
            socket.bind_or_connect()
            port = self._output_ports[port_id]
            addresses = [a.to_address() for a in socket.info.address_map[port_id]]

            uri = URI(
                id=port_id,
                location=URILocation.port,
                hostname=cfg.ZMQ_BIND_HOSTNAME,
                query={"address": addresses},
                comm_backend=CommBackend.ZMQ,
            )
            val = PortVal(
                id=port_id,
                canonical_id=port.canonical_id,
                uri=uri,
                status=PortStatus.IDLE,
            )
            self.port_vals[port_id] = val
            # Register the port in the KeyValueLoop
            self.port_kv_loop.add_or_update_value(val.key(), val)

        await self.port_kv_loop.update_now()

    async def _update_metrics(self, metrics: list[PortMetrics]) -> None:
        if not self.port_metrics_kv_loop:
            return

        for metric in metrics:
            self.port_metrics_kv_loop.add_or_update_value(metric.key(), metric)

    # TODO: implement
    @property
    def ready(self):
        return True
