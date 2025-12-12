from collections import deque
from dataclasses import dataclass, field
from typing import Any

import msgspec
import zmq
from distiller_streaming.client import SharedStateClient
from distiller_streaming.emitter import BatchEmitter
from distiller_streaming.models import BatchedFrames
from distiller_streaming.util import unpack_sparse_array

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import dependencies, operator

logger = get_logger()

DEFAULT_PUB_ADDRESS = "tcp://localhost:7082"
DEFAULT_DATA_PORT = 17000


@dataclass
class SocketManager:
    """Manages ZMQ socket connections for data reception."""

    _override_context: zmq.Context | None = None
    _override_socket: zmq.Socket | None = None
    _override_address: str | None = None

    def get_override_socket(self, address: str) -> zmq.Socket | None:
        """Return a PULL socket connected to the override data address."""
        if not address:
            return None

        if self._override_socket and self._override_address == address:
            return self._override_socket

        self._close_override()

        self._override_context = zmq.Context()
        self._override_socket = self._override_context.socket(zmq.PULL)
        if not self._override_socket:
            return None

        self._override_socket.setsockopt(zmq.LINGER, 0)
        self._override_socket.setsockopt(zmq.RCVTIMEO, 1000)
        self._override_socket.connect(address)
        self._override_address = address
        logger.info("Connected override data socket to %s", address)
        return self._override_socket

    def _close_override(self) -> None:
        """Close override socket and context."""
        if self._override_socket:
            self._override_socket.close()
            self._override_socket = None
        if self._override_context:
            self._override_context.term()
            self._override_context = None
        self._override_address = None

    def shutdown(self) -> None:
        """Clean up all socket resources."""
        self._close_override()


@dataclass
class EmitterManager:
    """Manages BatchEmitter queue and iteration."""

    _cache: deque[BatchEmitter] = field(default_factory=deque)
    _active: BatchEmitter | None = None

    def add(self, emitter: BatchEmitter) -> None:
        """Add an emitter to the queue."""
        self._cache.append(emitter)

    def has_active(self) -> bool:
        """Check if there's an active emitter."""
        return self._active is not None

    def activate_next(self) -> bool:
        """Activate the next emitter from the cache if available."""
        if self._active is None and self._cache:
            self._active = self._cache.popleft()
            logger.info(
                "Started processing emitter (Scan: %d, Frames: %d)",
                self._active.scan_number,
                self._active.total_frames,
            )
            return True
        return False

    def get_next_batch(self) -> BytesMessage | None:
        """Get the next batch from the active emitter."""
        if not self._active:
            return None

        try:
            return self._active.get_next_batch_message()
        except StopIteration:
            logger.info(
                "Finished emitter (Scan: %d, Frames: %d)",
                self._active.scan_number,
                self._active.total_frames,
            )
            self._active = None
            return None

    def clear(self) -> None:
        """Clear all emitters."""
        self._cache.clear()
        self._active = None


@dataclass
class DistillerGrabberState:
    """Encapsulates all state for the distiller grabber operator."""

    state_client: SharedStateClient | None = None
    socket_manager: SocketManager = field(default_factory=SocketManager)
    emitter_manager: EmitterManager = field(default_factory=EmitterManager)
    current_pub_address: str | None = None

    def initialize(self, pub_address: str) -> None:
        """Initialize the state client."""
        logger.info("Initializing SharedStateClient (pub: %s)...", pub_address)
        self.state_client = SharedStateClient(pub_address=pub_address)
        self.current_pub_address = pub_address
        self.state_client.start()
        logger.info("SharedStateClient started.")

    def update_pub_address(self, new_address: str) -> None:
        """Update the publisher address if changed."""
        if new_address != self.current_pub_address and self.state_client:
            logger.info(
                "Pub address changed from '%s' to '%s'. Updating client.",
                self.current_pub_address,
                new_address,
            )
            self.state_client.update_pub_address(new_address)
            self.current_pub_address = new_address

    def get_data_socket(
        self, override_enabled: bool, override_addr: str
    ) -> zmq.Socket | None:
        """Get the appropriate data socket based on configuration."""
        if override_enabled:
            return self.socket_manager.get_override_socket(override_addr)
        if self.state_client:
            return self.state_client.get_data_socket()
        return None

    def shutdown(self) -> None:
        """Clean up all resources."""
        logger.info("Shutting down operator dependencies...")
        if self.state_client:
            logger.info("Shutting down SharedStateClient...")
            self.state_client.shutdown()
            self.state_client = None
            logger.info("SharedStateClient shut down.")

        self.socket_manager.shutdown()
        self.emitter_manager.clear()
        self.current_pub_address = None
        logger.info("Operator dependencies shut down.")


# Single state instance
_state: DistillerGrabberState | None = None


def _receive_raw_message(socket: zmq.Socket) -> bytes | None:
    """Non-blocking receive of a raw message from the socket."""
    try:
        return socket.recv(flags=zmq.NOBLOCK)
    except zmq.Again:
        return None


def _decode_batched_frames(raw_message: bytes) -> BatchedFrames | None:
    """Decode BatchedFrames from raw message bytes."""
    try:
        return msgspec.msgpack.decode(raw_message, type=BatchedFrames)
    except msgspec.DecodeError:
        return None


def _decode_sparse_array(
    raw_message: bytes, scan_number: int, batch_size_mb: float
) -> BatchEmitter | None:
    """Try to unpack a SparseArray from raw message bytes."""
    try:
        sparse_array = unpack_sparse_array(raw_message)
        scan_num = sparse_array.metadata.get("scan_number", scan_number)
        logger.info(
            "Received SparseArray dataset (Scan: %d, Shape: %s, Frames: %d)",
            scan_num,
            sparse_array.scan_shape,
            sparse_array.num_scans,
        )
        return BatchEmitter(
            sparse_array=sparse_array,
            scan_number=scan_num,
            batch_size_mb=batch_size_mb,
        )
    except Exception as e:
        logger.warning("Failed to unpack SparseArray: %s", e)
        return None


@dependencies
def setup_and_teardown():
    global _state
    _state = DistillerGrabberState()
    _state.initialize(DEFAULT_PUB_ADDRESS)

    yield

    if _state:
        _state.shutdown()
        _state = None


@operator
def grabber(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global _state

    if not _state or not _state.state_client:
        logger.error("State not initialized.")
        return None

    # Update pub address if changed
    new_pub_address = str(parameters.get("pub_address", DEFAULT_PUB_ADDRESS))
    _state.update_pub_address(new_pub_address)

    # First priority: drain active emitter
    _state.emitter_manager.activate_next()
    if _state.emitter_manager.has_active():
        result = _state.emitter_manager.get_next_batch()
        if result:
            return result
        # Emitter finished, try to activate next
        _state.emitter_manager.activate_next()
        if _state.emitter_manager.has_active():
            return _state.emitter_manager.get_next_batch()

    # Second priority: receive new data from socket
    override_enabled = bool(parameters.get("override_data_enable", False))
    override_addr = str(
        parameters.get("override_data_addr", f"tcp://localhost:{DEFAULT_DATA_PORT}")
    )
    enable_sparse_array = bool(parameters.get("enable_sparse_array", False))
    batch_size_mb = float(parameters.get("batch_size_mb", 1.0))

    data_socket = _state.get_data_socket(override_enabled, override_addr)
    if not data_socket:
        return None

    raw_message = _receive_raw_message(data_socket)
    if raw_message is None:
        return None

    # Try to decode BatchedFrames (streaming format)
    batch = _decode_batched_frames(raw_message)
    if batch:
        return batch.to_bytes_message()

    # Optionally try SparseArray format (full dataset)
    if enable_sparse_array:
        emitter = _decode_sparse_array(raw_message, 0, batch_size_mb)
        if emitter:
            _state.emitter_manager.add(emitter)
            _state.emitter_manager.activate_next()
            return _state.emitter_manager.get_next_batch()

    return None
