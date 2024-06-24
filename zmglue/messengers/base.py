from abc import ABC, abstractmethod


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

    @abstractmethod
    def send(self, msg, dst: str):
        pass

    @abstractmethod
    def recv(self, src: str):
        pass

    @abstractmethod
    def start(self, client, pipeline):
        pass
