from abc import ABC, abstractmethod

from zmglue.models.messages import BaseMessage
from zmglue.models.pipeline import InputJSON, OutputJSON


class BaseMessenger(ABC):

    @abstractmethod
    def __init__(self, operator):
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
    def send(self, msg, dst: str):
        pass

    @abstractmethod
    def recv(self, src: str) -> BaseMessage | None:
        pass

    @abstractmethod
    def start(self, client, pipeline):
        pass
