import logging
from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any, Optional

import zmq
from pydantic import BaseModel, ValidationError, model_validator

from zmglue.logger import get_logger
from zmglue.models import MESSAGE_SUBJECT_TO_MODEL, BaseMessage
from zmglue.models.base import AgentID, OperatorID, OrchestratorID, PortID
from zmglue.models.uri import ZMQAddress

logger = get_logger(__name__, "DEBUG")


class SocketMetrics(BaseModel):
    send_count: int = 0
    send_bytes: int = 0
    send_timeouts: int = 0
    recv_count: int = 0
    recv_bytes: int = 0
    recv_timeouts: int = 0


class SocketInfo(BaseModel):
    type: int  # zmq.SocketType
    addresses: list[str | ZMQAddress] = []
    parent_id: Optional[OperatorID | PortID | AgentID | OrchestratorID] = None
    bind: bool
    options: dict[zmq.SocketOption, Any] = {}

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

    def update_addresses(self, addresses: list[str | ZMQAddress]) -> None:
        self.info.addresses = addresses

    def bind_or_connect(self):
        self._configure()
        if not self.info.addresses:
            logger.error("No addresses provided")
            return False
        for addr in self.info.addresses:
            if not isinstance(addr, ZMQAddress):
                try:
                    addr = ZMQAddress.from_address(addr)
                except ValidationError as e:
                    logger.error(f"Address isn't a proper ZeroMQ address: {e}")
                    raise e

            if self.info.bind:
                addr = addr.to_bind_address()
                self._socket.bind(addr)
                logger.info(f"Bound to {addr}")
            else:
                addr = addr.to_connect_address()
                self._socket.connect(addr)
                logger.info(f"Connected to {addr}")

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
