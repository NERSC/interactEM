from abc import ABC, abstractmethod


class BaseMessenger(ABC):
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
