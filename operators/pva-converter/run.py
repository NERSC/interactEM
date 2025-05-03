import os
import time
from typing import Any

import numpy as np
import pvaccess as pva
from pvaccess import PvObject as PvaPvObject
from pvapy.hpc.dataConsumer import DataConsumer
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import dependencies, operator

logger = get_logger(level="DEBUG")

AttributeName = str


class ValueDef(BaseModel):
    value: Any | None = None


class AttributeDictValue(BaseModel):
    value: tuple[ValueDef, ValueDef] = (ValueDef(), ValueDef())
    source: str
    sourceType: int
    descriptor: str

    @field_validator("value")
    @classmethod
    def check_value(cls, v):
        if len(v) != 2:
            raise ValueError("Value must have exactly two elements.")
        return v

    def get_value(self) -> str | int | float | None:
        if self.value[0].value is None:
            return
        return self.value[0].value

    def update_value(self, new_value: ValueDef):
        self.value = (new_value, self.value[1])


class Attribute(AttributeDictValue):
    name: AttributeName


class PvObjectMeta(BaseModel):
    uid: int
    attrs: dict[str, Attribute]
    shape: tuple[int, int]  # (ny, nx)

    @classmethod
    def from_pv(cls, pv: PvaPvObject) -> "PvObjectMeta":
        uid = int(pv["uniqueId"])

        dims = pv["dimension"]
        if len(dims) > 2:
            raise ValueError("Image cannot have dimensions larger than 2.")

        attrs = {a["name"]: a for a in pv["attribute"]}

        nx = int(dims[0]["size"])
        ny = int(dims[1]["size"])

        return cls(uid=uid, attrs=attrs, shape=(ny, nx))


def get_image(pv: PvaPvObject, meta: PvObjectMeta) -> np.ndarray:
    fieldKey = pv.getSelectedUnionFieldName()
    image: np.ndarray = np.array(pv["value"][0][fieldKey], copy=False).reshape(
        meta.shape[0], meta.shape[1]
    )
    return image


env_file = "/mnt/env_file"


class DataConsumerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")
    monitorQueueSize: int = 0
    consumerId: str = "0"
    inputChannel: str
    providerType: str = "pva"
    objectIdField: str = "uniqueId"


cfg = DataConsumerConfig()  # type: ignore


class EpicsEnvVars(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")
    EPICS_PVA_NAME_SERVERS: str = "127.0.0.1:11111"
    EPICS_PVA_AUTO_ADDR_LIST: str = "NO"
    PVAPY_EPICS_LOG_LEVEL: str = "0"


epics_env = EpicsEnvVars()


class DataConsumerWrapper(DataConsumer):
    def __init__(self, cfg: DataConsumerConfig):
        super().__init__(**cfg.model_dump())
        self.logger = logger

    def processFromQueue(self) -> tuple[PvObjectMeta, np.ndarray] | None:
        if self.pvObjectQueue is None:
            return
        try:
            pvObject = self.pvObjectQueue.get()
            meta = PvObjectMeta.from_pv(pvObject)
            image = get_image(pvObject, meta)
            return (meta, image)
        except pva.QueueEmpty:
            time.sleep(0.05)
            pass
        except Exception as e:
            self.logger.error(f"Error processing PV object: {e}")
            self.logger.exception(e)
            return


consumer = DataConsumerWrapper(cfg)


@dependencies
def deps():
    os.environ["PVAPY_EPICS_LOG_LEVEL"] = epics_env.PVAPY_EPICS_LOG_LEVEL
    os.environ["EPICS_PVA_AUTO_ADDR_LIST"] = epics_env.EPICS_PVA_AUTO_ADDR_LIST
    os.environ["EPICS_PVA_NAME_SERVERS"] = epics_env.EPICS_PVA_NAME_SERVERS
    logger.info(f"EPICS_PVA_NAME_SERVERS: {epics_env.EPICS_PVA_NAME_SERVERS}")
    global consumer
    consumer.start()
    yield
    consumer.stop()


@operator
def pva_converter(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global consumer
    result = consumer.processFromQueue()
    if result is None:
        return
    meta, image = result
    meta = meta.model_dump()
    data = image.tobytes()
    logger.info(meta)
    header = MessageHeader(subject=MessageSubject.BYTES, meta=meta)
    return BytesMessage(header=header, data=data)
