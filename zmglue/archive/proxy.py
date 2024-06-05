import multiprocessing
import time
from enum import Enum
from multiprocessing.shared_memory import SharedMemory
from queue import Empty, SimpleQueue
from uuid import uuid4

import zmq
from pydantic import BaseModel

from zmglue.logger import get_logger
from zmglue.types import (
    ErrorMessage,
    ProtocolZmq,
    QueueMessage,
    QueueMessageAction,
    StatusMessage,
    URIZmq,
)
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("proxy", "DEBUG")


class ProxyConfig(BaseModel):
    num_frontend_workers: int
    num_backend_workers: int
    io_threads_per_worker: int


class ShmemQueueSocketType(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    MIDDLE = "middle"


class ShmemQueueSocket(Socket):
    type_info_map = {
        ShmemQueueSocketType.FRONTEND: {
            "type": zmq.REQ,
            "bind": True,
            "uris": [
                URIZmq(
                    node_id=uuid4(),
                    port_id=uuid4(),
                    transport_protocol=ProtocolZmq.tcp,
                    hostname="localhost",
                    hostname_bind="*",
                    port=5554,
                )
            ],
            "options": {zmq.SocketOption.LINGER: 0},
        },
        ShmemQueueSocketType.BACKEND: {
            "type": zmq.PUSH,
            "bind": True,
            "uris": [
                URIZmq(
                    node_id=uuid4(),
                    port_id=uuid4(),
                    transport_protocol=ProtocolZmq.tcp,
                    hostname="localhost",
                    hostname_bind="*",
                    port=5556,
                )
            ],
            "options": {zmq.SocketOption.LINGER: 0},
        },
        ShmemQueueSocketType.MIDDLE: {
            "type": zmq.REQ,
            "bind": False,
            "uris": [
                URIZmq(
                    node_id=uuid4(),
                    port_id=uuid4(),
                    transport_protocol=ProtocolZmq.ipc,
                    hostname="localhost",
                    port=5555,
                )
            ],
            "options": {
                zmq.SocketOption.LINGER: 0,
                # zmq.SocketOption.SNDTIMEO: 1000,
                # zmq.SocketOption.RCVTIMEO: 1000,
            },
        },
    }

    def __init__(self, type: ShmemQueueSocketType, context: zmq.Context):

        super().__init__(info, context, logger)
        self.shmems = {}


class ProxyFrontendWorker:
    def __init__(self, io_threads: int):
        self.io_threads = io_threads

    def setup_sockets(self):
        self.context = zmq.Context(self.io_threads)
        self.socket = Socket(
            SocketInfo(
                type=zmq.PULL,
                bind=True,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        hostname_bind="*",
                        port=5554,
                    )
                ],
                options={zmq.SocketOption.LINGER: 0},
            ),
            self.context,
            logger,
        )
        self.queue_socket = Socket(
            SocketInfo(
                type=zmq.REQ,
                bind=False,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.ipc,
                        hostname="localhost",
                        port=5555,
                    )
                ],
                options={
                    zmq.SocketOption.LINGER: 0,
                    # zmq.SocketOption.SNDTIMEO: 1000,
                    # zmq.SocketOption.RCVTIMEO: 1000,
                },
            ),
            self.context,
            logger,
        )
        self.queue_socket.bind_or_connect()
        self.socket.bind_or_connect()

    def run(self):
        self.setup_sockets()
        while True:
            time.sleep(1)
            msg = self.socket.recv_bytes()
            if msg == zmq.Again:
                continue
            shmem = SharedMemory(create=True, size=len(msg))
            shmem.buf[: len(msg)] = msg
            self.queue_socket.send_model(
                QueueMessage(
                    name=shmem.name, size=len(msg), type=QueueMessageAction.PUT
                )
            )
            logger.info(f"Sent message to queue: {shmem.name}")
            response = self.queue_socket.recv_model()
            logger.info(f"Received response from queue: {response}")
            if isinstance(response, ErrorMessage):
                logger.error(f"Error response: {response}")
            elif isinstance(response, StatusMessage):
                logger.info(f"Status: {response.status}")


class ProxyBackendWorker:
    def __init__(self, io_threads: int):
        self.context: zmq.SyncContext | None = None
        self.io_threads = io_threads

    def setup_sockets(self):
        self.context = zmq.Context(self.io_threads)
        self.socket = Socket(
            SocketInfo(
                type=zmq.PUSH,
                bind=True,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        hostname_bind="*",
                        port=5556,
                    )
                ],
                options={zmq.SocketOption.LINGER: 0, zmq.SocketOption.SNDTIMEO: 1000},
            ),
            self.context,
            logger,
        )
        self.queue_socket = Socket(
            SocketInfo(
                type=zmq.REQ,
                bind=False,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.ipc,
                        hostname="localhost",
                        port=5555,
                    )
                ],
                options={
                    zmq.SocketOption.LINGER: 0,
                    # zmq.SocketOption.SNDTIMEO: 1000,
                    # zmq.SocketOption.RCVTIMEO: 1000,
                },
            ),
            self.context,
            logger,
        )
        self.queue_socket.bind_or_connect()
        self.socket.bind_or_connect()

    def run(self):
        self.setup_sockets()
        while True:
            time.sleep(1)
            res = self.queue_socket.send_model(
                QueueMessage(type=QueueMessageAction.GET, name=None)
            )
            if res == zmq.Again:
                continue
            msg = self.queue_socket.recv_model()
            logger.info(f"Received message from queue: {msg}")
            if msg == zmq.Again:
                continue
            if isinstance(msg, ErrorMessage):
                logger.error(f"Error receiving message from queue: {msg}")
                continue
            if not isinstance(msg, QueueMessage):
                logger.error(f"Invalid message received: {msg}")
                continue
            if msg.type == QueueMessageAction.EMPTY:
                continue

            shmem = SharedMemory(create=False, name=msg.name)
            self.socket.send_bytes(zmq.Frame(shmem.buf[: msg.size]))
            self.queue_socket.send_model(
                QueueMessage(name=shmem.name, type=QueueMessageAction.FREE)
            )
            response = self.queue_socket.recv_model()
            if isinstance(response, ErrorMessage):
                logger.error(f"Error freeing shared memory: {response}")
            elif isinstance(response, StatusMessage):
                if response.status != "OK":
                    logger.error(f"Error freeing shared memory: {response}")


class ProxyHub:
    def __init__(self):
        self.context: zmq.SyncContext | None = None
        self.queue: SimpleQueue | None = None

    def setup_sockets(self):
        self.context = zmq.Context()
        self.queue_socket = Socket(
            SocketInfo(
                type=zmq.REP,
                bind=True,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.ipc,
                        hostname="localhost",
                        hostname_bind="localhost",
                        port=5555,
                    )
                ],
                options={zmq.SocketOption.LINGER: 0},
            ),
            self.context,
            logger,
        )
        self.queue_socket.bind_or_connect()

    def run(self):
        self.setup_sockets()
        self.queue = SimpleQueue()
        while True:
            msg = self.queue_socket.recv_model()
            logger.info(f"Received message from worker: {msg}")
            if not isinstance(msg, QueueMessage):
                self.queue_socket.send_model(
                    ErrorMessage(message="Invalid message type")
                )

            if msg.type == QueueMessageAction.PUT:
                self.queue.put((msg.name, msg.size))
                self.queue_socket.send_model(StatusMessage(status="OK"))

            elif msg.type == QueueMessageAction.GET:
                try:
                    name, size = self.queue.get(block=False)
                except Empty:
                    self.queue_socket.send_model(
                        QueueMessage(name=None, type=QueueMessageAction.EMPTY)
                    )
                    continue
                self.queue_socket.send_model(
                    QueueMessage(type=QueueMessageAction.GET, name=name, size=size)
                )

            elif msg.type == QueueMessageAction.FREE:

                self.queue_socket.send_model(StatusMessage(status="OK"))

            else:
                self.queue_socket.send_model(StatusMessage(status="Not OK"))


class Proxy:
    def __init__(self, cfg: ProxyConfig):
        self.cfg = cfg
        self.frontend_workers = []
        self.backend_workers = []

    def start(self):
        hub = multiprocessing.Process(target=ProxyHub().run)
        hub.start()
        for _ in range(self.cfg.num_frontend_workers):
            p = multiprocessing.Process(
                target=ProxyFrontendWorker(self.cfg.io_threads_per_worker).run
            )
            p.start()
            self.frontend_workers.append(p)
        for _ in range(self.cfg.num_backend_workers):
            p = multiprocessing.Process(
                target=ProxyBackendWorker(self.cfg.io_threads_per_worker).run
            )
            p.start()
            self.backend_workers.append(p)

        context = zmq.Context()
        push_socket = Socket(
            SocketInfo(
                type=zmq.PUSH,
                bind=False,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        port=5554,
                    )
                ],
                options={zmq.SocketOption.LINGER: 0},
            ),
            context,
            logger,
        )
        push_socket.bind_or_connect()
        pull_socket = Socket(
            SocketInfo(
                type=zmq.PULL,
                bind=False,
                uris=[
                    URIZmq(
                        node_id=uuid4(),
                        port_id=uuid4(),
                        transport_protocol=ProtocolZmq.tcp,
                        hostname="localhost",
                        port=5556,
                    )
                ],
                options={zmq.SocketOption.LINGER: 0},
            ),
            context,
            logger,
        )
        pull_socket.bind_or_connect()
        while True:
            push_socket.send_bytes(b"Hello, world!")
            msg = pull_socket.recv_bytes()
            logger.info(f"Received {msg} from backend")

        for p in self.frontend_workers + self.backend_workers:
            p.join()


if __name__ == "__main__":
    config = ProxyConfig(
        num_frontend_workers=1, num_backend_workers=1, io_threads_per_worker=2
    )
    proxy = Proxy(config)
    proxy.start()
