from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from nats.js import JetStreamContext
from pydantic import BaseModel

from core.models.base import OperatorID
from core.models.pipeline import InputJSON, OutputJSON


class MessageSubject(str, Enum):
    BYTES = "bytes"
    SHM = "shm"


class MessageHeader(BaseModel):
    subject: MessageSubject
    meta: dict[str, Any] = {}


class BaseMessage(BaseModel):
    header: MessageHeader


class BytesMessage(BaseMessage):
    data: bytes


class ShmMessage(BaseMessage):
    shm_meta: dict[str, Any] = {}


MESSAGE_SUBJECT_TO_MODEL: dict[MessageSubject, type[BaseMessage]] = {
    MessageSubject.BYTES: BytesMessage,
    MessageSubject.SHM: ShmMessage,
}


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
