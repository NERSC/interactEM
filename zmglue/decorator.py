from abc import ABC
from enum import IntEnum
from functools import wraps
from re import I
from typing import Any, Callable, Dict, Optional, Sequence, Tuple, Union, cast
from uuid import UUID
from xml.dom import ValidationErr

import zmq
from pydantic import BaseModel, model_validator
from zmq import Message, SocketOption

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.types import ZmqURI

logger = get_logger(__name__, "DEBUG")


class SocketInfo(BaseModel):
    type: int  # zmq.SocketType
    uris: Sequence[ZmqURI] = []
    bind: bool
    settings: list[Tuple[int, int | str | bytes]]

    @model_validator(mode="after")
    def check_bind_and_ports(self):
        if self.bind and len(self.uris) > 1:
            raise ValueError("If bind is True, len(uris) must be <= 1")
        return self


AGENT_CLIENT_DEFAULT_SOCKET = SocketInfo(
    type=zmq.REQ,
    bind=False,
    settings=[(zmq.LINGER, int(0)), (zmq.SNDHWM, int(1000))],
)


# We can't subclass zmq.Socket because it only accepts its own attributes
class Socket:
    def __init__(self, info: SocketInfo, context: zmq.Context):
        self.info: SocketInfo = info
        self._socket: zmq.Socket = context.socket(info.type)
        self._configure()

    def _configure(self):
        for setting in self.info.settings:
            self._socket.set(setting[0], setting[1])

    def bind_or_connect(self):

        for uri in self.info.uris:
            addr = uri.to_address()
            if self.info.bind:
                self._socket.bind(addr)
                print(f"Bound to {addr}")
            else:
                self._socket.connect(addr)
                print(f"Connected to {addr}")

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

    def close(self):
        self._socket.close()


class AgentClient:
    def __init__(self, node: Node, context: zmq.Context = zmq.Context()):
        self.context: zmq.Context = context
        self.socket: Socket = Socket(AGENT_CLIENT_DEFAULT_SOCKET, self.context)
        self.node = node

    def get_settings(self, node: Node) -> MessengerSettings:
        request = MessengerSettingsRequest(node=node)
        self.socket.send_json(request.model_dump())
        settings = self.socket.recv_json()
        try:
            settings = MessengerSettings(**settings)
        except ValidationErr as e:
            logger.error(e)
            raise e
        except:
            logger.error("Error parsing settings")
            raise
        return settings


class ZMQMessenger:
    def __init__(self, node: Node):
        self.node = node
        self.settings: Optional[MessengerSettings]
        self.context = zmq.Context()
        self.client = AgentClient(self.node, self.context)
        try:
            self.settings = self.client.get_settings(self.node)
        except:
            self.client.socket.close()

        self.rep = self.context.socket(zmq.REP)
        self.req = self.context.socket(zmq.REQ)
        self.pub = self.context.socket(zmq.PUB)
        self.sub = self.context.socket(zmq.SUB)
        self.pair = self.context.socket(zmq.PAIR)


if __name__ == "__main__":
    node = Node(id=1)
    messenger = ZMQMessenger(node)

# class Operator(ABC):
#     def __init__(
#         self,
#         name: str,
#         messenger: BaseMessenger,
#         array_constructor: Callable[[DataType], DataArray],
#     ):
#         self.name = name
#         self.messenger = messenger
#         self.array_constructor = array_constructor

#     @property
#     def input_queue(self) -> str:
#         input_queue = self.name
#         return input_queue

#     def start(self):
#         while True:
#             message = self.messenger.recv(self.input_queue)

#             if message.type == MessageType.Operate:
#                 task_message = OperateTaskMessage(**message.dict())
#                 self.operate(task_message)
#             elif message.type == MessageType.Terminate:
#                 return
#             else:
#                 raise Exception(f"Unknown message type: {message.type}")

#     def operate(self, task_message: OperateTaskMessage):
#         inputs = task_message.inputs
#         params = task_message.params
#         output_queue = task_message.output_queue

#         try:
#             raw_inputs = {key: RawPort.from_port(port) for key, port in inputs.items()}
#             _raw_outputs = self.kernel(raw_inputs, params)

#             raw_outputs: Dict[PortKey, RawPort] = {
#                 key: port if isinstance(port, RawPort) else RawPort(**port)
#                 for key, port in _raw_outputs.items()
#             }

#             outputs = {
#                 key: cast(RawPort, port).to_port(self.array_constructor)
#                 for key, port in raw_outputs.items()
#             }

#             result = ResultTaskMessage(outputs=outputs)
#             result.parallel_index = task_message.parallel_index
#             self.messenger.send(result, output_queue)
#         except BaseException:
#             # Write exception details to str
#             buf = StringIO()
#             traceback.print_exc(file=buf)
#             error_string = buf.getvalue()
#             error_message = ErrorTaskMessage(error_string=error_string)
#             self.messenger.send(error_message, output_queue)

#     @abstractmethod
#     def kernel(
#         self,
#         inputs: Dict[PortKey, RawPort],
#         parameters: JSONType,
#     ) -> Union[Dict[PortKey, RawPort], Dict[PortKey, Dict]]:
#         pass


# KernelFn = Callable[
#     [Dict[PortKey, RawPort], JSONType],
#     Union[Dict[PortKey, RawPort], Dict[PortKey, Dict]],
# ]


# def operator(
#     func: Optional[KernelFn] = None,
#     name: Optional[str] = None,
#     start: bool = True,
#     messenger: Optional[BaseMessenger] = None,
#     array_constructor: Optional[Callable[[DataType], DataArray]] = None,
# ) -> Any:
#     # A decorator to automatically make an Operator where the function
#     # that is decorated will be the kernel function.

#     def decorator(func: KernelFn) -> Operator:
#         nonlocal name
#         nonlocal messenger
#         nonlocal array_constructor

#         if name is None:
#             name = func.__name__

#         @wraps(func)
#         def kernel(_, *args, **kwargs):
#             # Remove self so the caller does not need to add it
#             return func(*args, **kwargs)

#         class_name = f"{name.capitalize()}Operator"
#         OpClass = type(class_name, (Operator,), {"kernel": kernel})

#         obj = OpClass(name, messenger, array_constructor)

#         if start:
#             obj.start()

#         return obj

#     if func is not None:
#         return decorator(func)

#     return decorator
