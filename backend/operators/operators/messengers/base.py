from abc import ABC, abstractmethod

from core.models.base import OperatorID
from core.models.messages import BaseMessage
from core.models.pipeline import InputJSON, OutputJSON
from nats.js import JetStreamContext


class BaseMessenger(ABC):
    @abstractmethod
    def __init__(self, operator_id: OperatorID, js: JetStreamContext):
        pass

    @property
    @abstractmethod
    def ready(self) -> bool:
        pass

    @property
    @abstractmethod
    def type(self) -> str:
        pass

    @property
    @abstractmethod
    def input_ports(self) -> list[InputJSON]:
        pass

    @property
    @abstractmethod
    def output_ports(self) -> list[OutputJSON]:
        pass

    @abstractmethod
    async def send(self, msg, dst: str):
        pass

    @abstractmethod
    async def recv(self, src: str) -> BaseMessage | None:
        pass

    @abstractmethod
    async def start(self, pipeline):
        pass

    @abstractmethod
    async def stop(self):
        pass
