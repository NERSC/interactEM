import logging
from typing import Any, Sequence, Tuple

import zmq
from pydantic import BaseModel, ValidationError, model_validator

from zmglue.types import MESSAGE_SUBJECT_TO_MODEL, BaseMessage, URIZmq


class SocketInfo(BaseModel):
    type: int  # zmq.SocketType
    uris: Sequence[URIZmq] = []
    bind: bool
    options: Sequence[Tuple[int, int | str | bytes]] = []

    @model_validator(mode="after")
    def check_bind_and_ports(self):
        if self.bind and len(self.uris) > 1:
            raise ValueError("If bind is True, len(uris) must be <= 1")
        return self


class Socket:
    def __init__(self, info: SocketInfo, context: zmq.Context, logger: logging.Logger):
        self.info: SocketInfo = info
        self._logger = logger
        self._socket: zmq.Socket = context.socket(info.type)
        self._configure()

    def _configure(self):
        for option in self.info.options:
            self._socket.set(option[0], option[1])

    def update_uri(self, uri: URIZmq):
        self.info.uris = [uri]

    def bind_or_connect(self):
        for uri in self.info.uris:
            if self.info.bind:
                if uri.interface:
                    addr = uri.to_interface_address()
                elif uri.hostname_bind:
                    addr = uri.to_bind_address()
                self._socket.bind(addr)
                self._logger.info(f"Bound to {addr}")
            else:
                addr = uri.to_connect_address()
                self._socket.connect(addr)
                self._logger.info(f"Connected to {addr}")

    def send_json(self, obj: dict, flags: int = 0) -> None:
        self._socket.send_json(obj, flags)

    def send_string(self, obj: str, flags: int = 0) -> None:
        self._socket.send_string(obj, flags)

    def send_pyobj(self, obj: Any, flags: int = 0) -> None:
        self._socket.send_pyobj(obj, flags)

    def send_bytes(self, obj: bytes, flags: int = 0) -> None:
        self._socket.send(obj, flags)

    def recv_json(self, flags: int = 0) -> Any:
        return self._socket.recv_json(flags)

    def recv_string(self, flags: int = 0) -> str:
        return self._socket.recv_string(flags)

    def recv_pyobj(self, flags: int = 0) -> Any:
        return self._socket.recv_pyobj(flags)

    def recv_bytes(self, flags: int = 0) -> bytes:
        return self._socket.recv(flags)

    def send_model(self, model: BaseMessage):
        payload = model.model_dump_json()
        self._socket.send_string(payload)

    def recv_model(self) -> BaseMessage:
        payload = self._socket.recv()

        try:
            subject = BaseMessage.model_validate_json(payload)
        except ValidationError as e:
            self._logger.info(f"Error deserializing the MessageSubject: {e}")
            raise e

        model_class = MESSAGE_SUBJECT_TO_MODEL.get(subject.subject)

        if not model_class:
            raise ValueError(f"Unsupported MessageSubject: {subject.subject}")

        try:
            return model_class.model_validate_json(payload)
        except ValidationError as e:
            self._logger.info(f"Error deserializing the {model_class.__name__}: {e}")
            raise

    def close(self):
        self._socket.close()
