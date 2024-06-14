from time import time
from typing import Dict, Type

from zmglue.agentclient import AgentClient
from zmglue.logger import get_logger
from zmglue.messengers.base import BaseMessenger
from zmglue.messengers.zmq import ZmqMessenger
from zmglue.models import CommBackend, IdType, OperatorJSON
from zmglue.pipeline import Pipeline

logger = get_logger("operator", "DEBUG")

BACKEND_TO_MESSENGER: Dict[CommBackend, Type[BaseMessenger]] = {
    CommBackend.ZMQ: ZmqMessenger,
}


class Operator:
    def __init__(
        self,
        id: IdType,
    ):
        self.id = id
        self.messenger: BaseMessenger | None = None
        self.pipeline: Pipeline | None = None
        self.info: OperatorJSON | None = None
        self.client = AgentClient(id=id)

    def start(self):
        while self.pipeline is None:
            response = self.client.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)

        self.info = self.pipeline.get_operator(self.id)
        if self.info is None:
            raise ValueError(f"Operator {self.id} not found in pipeline")

        backend = self.info.uri.comm_backend
        self.messenger = BACKEND_TO_MESSENGER[backend]()

        while True:
            time.sleep(1)

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
