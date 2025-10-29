from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from interactem.core.models.base import IdType


class TrackingMetadataBase(BaseModel):
    id: IdType


class InputPortTrackingMetadata(TrackingMetadataBase):
    time_after_header_validate: datetime


class OutputPortTrackingMetadata(TrackingMetadataBase):
    time_before_send: datetime


class OperatorTrackingMetadata(TrackingMetadataBase):
    time_before_operate: datetime
    time_after_operate: datetime

class TrackingMetadatas(BaseModel):
    metadatas: list[
        OperatorTrackingMetadata
        | OutputPortTrackingMetadata
        | InputPortTrackingMetadata
    ] = Field(default_factory=list)


class MessageSubject(str, Enum):
    BYTES = "bytes"
    SHM = "shm"


class MessageHeader(BaseModel):
    subject: MessageSubject
    meta: bytes | dict[str, Any] = b"{}"
    tracking: TrackingMetadatas | None = None

class BaseMessage(BaseModel):
    header: MessageHeader


class BytesMessage(BaseMessage):
    data: bytes


class ShmMessage(BaseMessage):
    shm_meta: dict[str, Any] = {}
