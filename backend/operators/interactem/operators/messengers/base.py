from abc import ABC, abstractmethod

from nats.js import JetStreamContext

from interactem.core.models.base import OperatorID
from interactem.core.models.messages import BytesMessage
from interactem.core.models.pipeline import InputJSON, OutputJSON


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
    async def send(self, message: BytesMessage):
        pass

    @abstractmethod
    async def recv(self) -> BytesMessage | None:
        pass

    @abstractmethod
    async def start(self, pipeline):
        pass

    @abstractmethod
    async def stop(self):
        pass
