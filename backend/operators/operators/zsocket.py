from collections.abc import Sequence
from typing import Any

import zmq
import zmq.asyncio
from pydantic import BaseModel, model_validator

from core.logger import get_logger
from core.models.base import (
    IdType,
    PortID,
    Protocol,
)
from core.models.ports import PortMetrics
from core.models.uri import ZMQAddress

logger = get_logger("socket", "INFO")



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

class Socket(zmq.asyncio.Socket):
    metrics: PortMetrics
    info: SocketInfo

    def __init__(
        self,
        context=None,
        socket_type=-1,
        io_loop=None,
        _from_socket: zmq.Socket | None = None,
        **kwargs,
    ) -> None:
        info = kwargs.pop("info", None)
        info = SocketInfo.model_validate(info)
        super().__init__(context, socket_type, io_loop, _from_socket, **kwargs)
        self.metrics = PortMetrics(id=info.parent_id)
        self.info = info


    def _configure(self):
        if self.info.options:
            logger.info("Setting socket options")
        for opt, val in self.info.options:
            self.set(opt, val)

    def bind_or_connect(self) -> None:
        self._configure()

        if not self.info.address_map or all(
            not addrs for addrs in self.info.address_map.values()
        ):
            logger.error("No addresses provided in address_map")
            raise ValueError("No addresses provided in address_map")

        if self.info.bind:
            return self._bind_to_addresses(self.info.address_map)
        else:
            return self._connect_to_addresses(self.info.address_map)

    def update_address_map(self, port_id: IdType, addresses: Sequence[ZMQAddress]):
        self.info.address_map[port_id] = addresses

    def _bind_to_addresses(
        self, address_map: dict[IdType, Sequence[ZMQAddress]]
    ) -> None:
        if len(address_map) > 1:
            raise ValueError("Can't bind to multiple address groups when binding.")

        addr_group = next(iter(address_map.values()))
        if len(addr_group) > 1:
            raise ValueError("Can't bind to multiple addresses within a single group.")

        addr = addr_group[0]
        bind_addr = addr.to_bind_address()
        if addr.protocol == Protocol.tcp and not addr.port:
            port = self.bind_to_random_port(bind_addr)
            addr.port = port
            # TODO: check if this correctly updates the address_map
        else:
            self.bind(bind_addr)

        self.info.bound_to.append(self.info.parent_id)
        logger.info(
            f"Socket on {self.info.parent_id} bound to {addr.to_bind_address()}"
        )

    def _connect_to_addresses(
        self, address_map: dict[IdType, Sequence[ZMQAddress]]
    ) -> None:
        for id_type, addr_group in address_map.items():
            for addr in addr_group:
                self.connect(addr.to_connect_address())
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
            super().disconnect(addr.to_connect_address())

        self.info.connected_to.remove(id_to_disconnect)

    def _connect_to_new_addresses(
        self, id_to_connect: IdType, addresses: Sequence[ZMQAddress]
    ):
        self._connect_to_addresses({id_to_connect: addresses})

    def close(self):
        self.info.connected_to.clear()
        self.info.bound_to.clear()
        super().close()


class Context(zmq.Context[Socket]):
    # Here we copy zmq.asyncio.Context but replace
    # the generic with our own Socket class
    # This is the only way to get the correct type hints
    _socket_class = Socket
    _instance = None

    def socket(self, info: SocketInfo) -> Socket:
        return super().socket(socket_type=info.type, socket_class=Socket, info=info)
