import logging
from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any, Optional, Self

import zmq
from pydantic import BaseModel, ValidationError, model_validator

from zmglue.logger import get_logger
from zmglue.models import MESSAGE_SUBJECT_TO_MODEL, BaseMessage
from zmglue.models.base import AgentID, OperatorID, OrchestratorID, PortID, Protocol
from zmglue.models.uri import ZMQAddress

logger = get_logger("socket", "INFO")


class SocketMetrics(BaseModel):
    send_count: int = 0
    send_bytes: int = 0
    send_timeouts: int = 0
    recv_count: int = 0
    recv_bytes: int = 0
    recv_timeouts: int = 0


class SocketInfo(BaseModel):
    type: int  # zmq.SocketType
    addresses: Sequence[ZMQAddress] = []
    parent_id: Optional[OperatorID | PortID | AgentID | OrchestratorID] = None
    bind: bool
    options: dict[zmq.SocketOption, Any] = {}
    connected: bool = False

    @model_validator(mode="before")
    @classmethod
    def coerce_into_address_model(cls, values: dict[str, Any]) -> dict[str, Any]:
        addresses = values.get("addresses", [])

        # If addresses is a single string or ZMQAddress, convert it to a list
        if isinstance(addresses, (str, ZMQAddress)):
            addresses = [addresses]
        elif not isinstance(addresses, list):
            raise ValueError("addresses must be a list, string, or ZMQAddress")

        validated_addresses: Sequence[ZMQAddress] = []
        for addr in addresses:
            if isinstance(addr, str):
                try:
                    addr = ZMQAddress.from_address(addr)
                except ValidationError as e:
                    raise ValueError(f"Address isn't a proper ZeroMQ address: {e}")
            elif not isinstance(addr, ZMQAddress):
                raise ValueError(
                    "Each address must be a string or a ZMQAddress instance"
                )
            validated_addresses.append(addr)

        values["addresses"] = validated_addresses
        return values

    @model_validator(mode="after")
    def check_bind_and_ports(self):
        if self.bind and len(self.addresses) > 1:
            raise ValueError("If bind is True, len(addresses) must be <= 1")
        return self


def disable_send_methods(cls):
    def not_supported(*args, **kwargs):
        raise NotImplementedError("This socket does not support sending.")

    methods = ["send_json", "send_string", "send_pyobj", "send_bytes", "send_model"]
    for name in methods:
        setattr(cls, name, not_supported)
    return cls


def disable_recv_methods(cls):
    def not_supported(*args, **kwargs):
        raise NotImplementedError("This socket does not support receiving.")

    methods = ["recv_json", "recv_string", "recv_pyobj", "recv_bytes", "recv_model"]
    for name in methods:
        setattr(cls, name, not_supported)
    return cls


class Socket:
    def __init__(self, info: SocketInfo, context: zmq.SyncContext):
        self.info: SocketInfo = info
        self._socket: zmq.SyncSocket = context.socket(info.type)
        self._metrics: SocketMetrics = SocketMetrics()

    def _configure(self):
        if self.info.options:
            logger.info("Setting socket options")
        for opt, val in self.info.options.items():
            self._socket.set(opt, val)

    def update_addresses(self, addresses: Sequence[ZMQAddress]) -> None:
        self.info.addresses = addresses

    def bind_or_connect(self) -> tuple[bool, int | None]:
        self._configure()
        if not self.info.addresses:
            logger.error("No addresses provided")
            raise ValueError("No addresses provided")

        if self.info.bind:
            return self._bind() or (False, None)
        else:
            return (False, self._connect())

    def _bind(self) -> tuple[bool, int | None] | None:
        if len(self.info.addresses) > 1:
            raise ValueError("Can't bind to multiple addresses...")

        addr = self.info.addresses[0]
        if addr.protocol == Protocol.tcp:
            return self._bind_tcp()
        else:
            self._socket.bind(addr.to_bind_address())
            self.info.connected = True

    def _bind_tcp(self) -> tuple[bool, int | None]:
        addr = self.info.addresses[0]
        bind_addr = addr.to_bind_address()
        updated = False
        if not addr.port:
            port = self._socket.bind_to_random_port(bind_addr)
            self.info.addresses[0].port = port
            updated = True
        else:
            self._socket.bind(bind_addr)
            port = addr.port
        self.info.connected = True
        logger.info(
            f"Socket on {self.info.parent_id} bound to port: {port} on {addr.hostname}"
        )
        return updated, port

    def _connect(self):
        for addr in self.info.addresses:
            addr = addr.to_connect_address()
            self._socket.connect(addr)
        self.info.connected = True

    @staticmethod
    def on_send(method: Callable[..., None]) -> Callable[..., Any]:
        @wraps(method)
        def wrapper(self: "Socket", obj: Any, flags: int = 0) -> Any:
            try:
                result = method(self, obj, flags)
            except zmq.Again:
                logger.error("Timeout sending message")
                self._metrics.send_timeouts += 1
                return zmq.Again
            self._metrics.send_count += 1
            return result

        return wrapper

    @staticmethod
    def on_recv(method: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(method)
        def wrapper(self: "Socket", flags: int = 0) -> Any:
            try:
                result = method(self, flags)
            except zmq.Again:
                logger.error("Timeout receiving message")
                self._metrics.recv_timeouts += 1
                return zmq.Again
            self._metrics.recv_count += 1
            return result

        return wrapper

    @on_send
    def send_json(self, obj: dict, flags: int = 0) -> None:
        self._socket.send_json(obj, flags)

    @on_send
    def send_string(self, obj: str, flags: int = 0) -> None:
        self._socket.send_string(obj, flags)

    @on_send
    def send_pyobj(self, obj: Any, flags: int = 0) -> None:
        self._socket.send_pyobj(obj, flags)

    @on_send
    def send_bytes(self, obj: bytes, flags: int = 0) -> None:
        self._socket.send(obj, flags)

    @on_recv
    def recv_json(self, flags: int = 0) -> Any:
        return self._socket.recv_json(flags)

    @on_recv
    def recv_string(self, flags: int = 0) -> str:
        return self._socket.recv_string(flags)

    @on_recv
    def recv_pyobj(self, flags: int = 0) -> Any:
        return self._socket.recv_pyobj(flags)

    @on_recv
    def recv_bytes(self, flags: int = 0) -> bytes:
        return self._socket.recv(flags)

    @on_send
    def send_model(self, obj: BaseMessage, flags: int = 0) -> Any:
        payload = obj.model_dump_json()
        self._socket.send_string(payload, flags)

    @on_recv
    def recv_model(self, flags: int = 0) -> BaseMessage:
        payload = self._socket.recv(flags)
        logger.debug(f"Received message: {payload}")
        try:
            subject = BaseMessage.model_validate_json(payload)
        except ValidationError as e:
            logger.info(f"Error deserializing the MessageSubject: {e}")
            raise e

        subject = subject.subject

        model_class = MESSAGE_SUBJECT_TO_MODEL.get(subject)

        if not model_class:
            raise ValueError(f"Unsupported MessageSubject: {subject}")

        try:
            return model_class.model_validate_json(payload)
        except ValidationError as e:
            logger.info(f"Error deserializing the {model_class.__name__}: {e}")
            raise

    def close(self):
        self._socket.close()
