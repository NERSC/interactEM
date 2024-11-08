from typing import Any

import numpy as np

from core.logger import get_logger
from core.models.messages import BytesMessage, MessageHeader, MessageSubject

from .operator import operator

logger = get_logger()


@operator
def create_hello_world(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage:
    logger.info("Creating message...")
    if inputs:
        return BytesMessage(header=inputs.header, data=b"Hello, World!")
    else:
        header = MessageHeader(subject=MessageSubject.BYTES, meta={})
        return BytesMessage(header=header, data=b"Hello, World!")


@operator
def receive_hello_world(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage:
    if inputs:
        logger.info(f"Received message: {inputs}")
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return inputs or BytesMessage(header=header, data=b"No input provided")


@operator
def process_hello_world(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage:
    if inputs:
        logger.info(f"Processing message: {inputs}")
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return inputs or BytesMessage(header=header, data=b"No input provided")


arr = np.random.randint(0, 255, (100, 100), dtype=np.uint16)


@operator
def send_image(inputs: BytesMessage | None, parameters: dict[str, Any]) -> BytesMessage:
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return BytesMessage(header=header, data=arr.tobytes())


@operator
def recv_image(inputs: BytesMessage | None, parameters: dict[str, Any]) -> BytesMessage:
    if inputs:
        _ = np.frombuffer(inputs.data, dtype=np.uint16).reshape(100, 100)
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return inputs or BytesMessage(header=header, data=b"No input provided")
