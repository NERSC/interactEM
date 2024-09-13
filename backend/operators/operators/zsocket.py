from collections.abc import Sequence
from typing import Any, Literal

import zmq
import zmq.asyncio
from pydantic import BaseModel, model_validator

from core.logger import get_logger
from core.models.base import (
    IdType,
    PortID,
    Protocol,
)
from core.models.uri import ZMQAddress

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
    address_map: dict[IdType, Sequence[ZMQAddress]] = {}
    parent_id: PortID
    bind: bool
    options: list[tuple[zmq.SocketOption, Any]] = []
    connected_to: list[IdType] = []
    bound_to: list[IdType] = []

    @model_validator(mode="after")
    def check_bind_and_ports(self):
        if self.bind and len(self.address_map) > 1:
            raise ValueError(
                "If bind is True, the address_map must contain only one entry."
            )
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
        for opt, val in self.info.options:
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

    def bind_or_connect(self) -> tuple[bool, int | None]:
        self._configure()

        if not self.info.address_map or all(
            not addrs for addrs in self.info.address_map.values()
        ):
            logger.error("No addresses provided in address_map")
            raise ValueError("No addresses provided in address_map")

        if self.info.bind:
            return self._bind_to_addresses(self.info.address_map)
        else:
            return (False, self._connect_to_addresses(self.info.address_map))

    def _bind_to_addresses(
        self, address_map: dict[IdType, Sequence[ZMQAddress]]
    ) -> tuple[bool, int | None]:
        if len(address_map) > 1:
            raise ValueError("Can't bind to multiple address groups when binding.")

        addr_group = next(iter(address_map.values()))
        if len(addr_group) > 1:
            raise ValueError("Can't bind to multiple addresses within a single group.")

        addr = addr_group[0]
        if addr.protocol == Protocol.tcp:
            return self._bind_tcp(addr)
        else:
            self._socket.bind(addr.to_bind_address())
            self.info.bound_to.append(self.info.parent_id)
            logger.info(f"Bound to {addr.to_bind_address()}")
            return False, None

    def _bind_tcp(self, addr: ZMQAddress) -> tuple[bool, int | None]:
        bind_addr = addr.to_bind_address()
        updated = False
        if not addr.port:
            port = self._socket.bind_to_random_port(bind_addr)
            addr.port = port  # Update the address with the bound port
            updated = True
        else:
            self._socket.bind(bind_addr)
            port = addr.port

        self.info.bound_to.append(self.info.parent_id)
        logger.info(
            f"Socket on {self.info.parent_id} bound to port: {port} on {addr.hostname}"
        )
        return updated, port

    def _connect_to_addresses(
        self, address_map: dict[IdType, Sequence[ZMQAddress]]
    ) -> None:
        for id_type, addr_group in address_map.items():
            for addr in addr_group:
                self._socket.connect(addr.to_connect_address())
                logger.info(f"Connected to {addr.to_connect_address()}")
            self.info.connected_to.append(id_type)

    def reconnect(self, id: IdType, new_addresses: Sequence[ZMQAddress]):
        self.disconnect(id)
        self.info.address_map[id] = new_addresses
        self._connect_to_new_addresses(id, new_addresses)

    def disconnect(self, id_to_disconnect: IdType):
        if id_to_disconnect not in self.info.connected_to:
            logger.warning(f"ID {id_to_disconnect} is not currently connected.")
            return

        current_addresses = self.info.address_map.get(id_to_disconnect, [])
        for addr in current_addresses:
            logger.info(f"Disconnecting from {addr.to_connect_address()}")
            self._socket.disconnect(addr.to_connect_address())

        self.info.connected_to.remove(id_to_disconnect)

    def _connect_to_new_addresses(
        self, id_to_connect: IdType, addresses: Sequence[ZMQAddress]
    ):
        self._connect_to_addresses({id_to_connect: addresses})

    def close(self):
        self.info.connected_to.clear()
        self.info.bound_to.clear()
        self._socket.close()
