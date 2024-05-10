from typing import Any

import zmq
from pydantic import BaseModel


class ContextInfo(BaseModel):
    options: dict[zmq.ContextOption, Any] = {}


class Context:
    def __init__(self, info: ContextInfo):
        self._context: zmq.SyncContext = zmq.Context()
        self._options: dict[zmq.ContextOption, Any] = info.options
        self._configure()

    def _configure(self):
        for option, val in self._options.items():
            self._context.set(option, val)
