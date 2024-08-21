from collections.abc import Sequence
from typing import Any, Literal

import zmq
import zmq.asyncio
from core.logger import get_logger
from core.models.base import AgentID, OperatorID, OrchestratorID, PortID, Protocol
from core.models.uri import ZMQAddress
from pydantic import BaseModel, ValidationError, model_validator

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
    parent_id: OperatorID | PortID | AgentID | OrchestratorID | None = None
    bind: bool
    options: dict[zmq.SocketOption, Any] = {}
    connected: bool = False

    @model_validator(mode="before")
    @classmethod
    def coerce_into_address_model(cls, values: dict[str, Any]) -> dict[str, Any]:
        addresses = values.get("addresses", [])

        # If addresses is a single string or ZMQAddress, convert it to a list
        if isinstance(addresses, str | ZMQAddress):
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


class Socket:
    def __init__(self, info: SocketInfo, context: zmq.asyncio.Context):
        self.info: SocketInfo = info
        self._socket: zmq.asyncio.Socket = context.socket(info.type)
        self._metrics: SocketMetrics = SocketMetrics()

    def __del__(self):
        self.close()

    def _configure(self):
        if self.info.options:
            logger.info("Setting socket options")
        for opt, val in self.info.options.items():
            self._socket.set(opt, val)

    async def send(
        self,
        data: Any,
        flags: int = 0,
        copy: bool = True,
        track: bool = False,
        **kwargs: Any,
    ) -> zmq.MessageTracker | None:
        return await self._socket.send(
            data, flags=flags, copy=copy, track=track, **kwargs
        )

    async def send_multipart(
        self,
        msg_parts: list[Any],
        flags: int = 0,
        copy: bool = True,
        track=False,
        **kwargs,
    ) -> zmq.MessageTracker | None:
        return await self._socket.send_multipart(
            msg_parts, flags=flags, copy=copy, track=track, **kwargs
        )

    async def recv(
        # TODO: unsure about this Literal here...
        self,
        flags: int = 0,
        copy: Literal[False] = False,
        track: bool = False,
    ) -> bytes | zmq.Frame:
        return await self._socket.recv(flags, copy=copy, track=track)

    async def recv_multipart(
        self, flags: int = 0, copy: bool = True, track: bool = False
    ) -> list[bytes] | list[zmq.Frame]:
        return await self._socket.recv_multipart(flags=flags, copy=copy, track=track)

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
            self._socket.connect(addr.to_connect_address())
        self.info.connected = True

    def close(self):
        if self.info.connected:
            self.info.connected = False
        self._socket.close()
