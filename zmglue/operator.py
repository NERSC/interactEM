import traceback
from abc import ABC, abstractmethod
from functools import wraps
from io import StringIO
from queue import Queue
from typing import Any, Callable, Dict, Optional, Union, cast

from zmglue.messengers.zmq import QueueMap, QueueType, ZmqMessenger
from zmglue.types import BaseMessage, DataMessage, IdType, MessageSubject, PortKey


class Operator:
    def __init__(
        self,
        name: str,
        messenger: ZmqMessenger,
    ):
        self.name = name
        self.messenger = messenger
        self.queues: QueueMap = {QueueType.input: {}, QueueType.output: {}}

    def start(self):

        self.messenger.queues = self.queues
        self.messenger.start()

        self.input_queues = self.queues[QueueType.input]
        self.output_queues = self.queues[QueueType.output]

        while True:
            for port_id in self.input_queues.keys():
                msg = self.messenger.recv(port_id)

            for port_id, q in self.input_queues.items():
                message = q.get()
                self.messenger.send(message, port_id)
            #     if message is None:
            #         continue
            #     if message.subject == MessageSubject.SHMEM:
            #         pass
            #     elif message.subject == MessageSubject.DATA:
            #         message = DataMessage(**message.model_dump())
            #         messages.append(message)
            #         output = self.operate(message)
            #     else:
            #         raise Exception(f"Unknown message subject: {message.subject}")

            # for q in self.output_queues.values():
            #     pass

    # def operate(self, task_message: DataMessage) -> DataMessage:

    #     inputs = task_message.data
    #     output = self.kernel(inputs)

    #     return self.output_queues[]DataMessage(data=output)

    # @abstractmethod
    # def kernel(self, inputs: bytes) -> bytes:
    #     pass


# KernelFn = Callable[[bytes], bytes]


# def operator(
#     func: Optional[KernelFn] = None,
#     name: Optional[str] = None,
#     start: bool = True,
#     messenger: Optional[InterOperatorMessenger] = None,
# ) -> Any:
#     # A decorator to automatically make an Operator where the function
#     # that is decorated will be the kernel function.

#     def decorator(func: KernelFn) -> Operator:
#         nonlocal name
#         nonlocal messenger

#         if name is None:
#             name = func.__name__

#         if messenger is None:
#             messenger = InterOperatorMessenger()
#         @wraps(func)
#         def kernel(_, *args, **kwargs):
#             # Remove self so the caller does not need to add it
#             return func(*args, **kwargs)

#         class_name = f"{name.capitalize()}Operator"
#         OpClass = type(class_name, (Operator,), {"kernel": kernel})

#         obj = OpClass(name, messenger)

#         if start:
#             obj.start()

#         return obj

#     if func is not None:
#         return decorator(func)

#     return decorator
