import time

import numpy as np

from zmglue.logger import get_logger
from zmglue.models.messages import BaseMessage, DataMessage
from zmglue.operator import operator

logger = get_logger("operators.examples", "DEBUG")


@operator
def create_hello_world(inputs: BaseMessage | None) -> BaseMessage:
    return DataMessage(data=b"Hello, World!")


@operator
def receive_hello_world(inputs: BaseMessage | None) -> BaseMessage:
    if inputs:
        logger.info(f"Received message: {inputs}")
    return inputs or DataMessage(data=b"No input provided")


@operator
def process_hello_world(inputs: BaseMessage | None) -> BaseMessage:
    if inputs:
        logger.info(f"Processing message: {inputs}")
    return inputs or DataMessage(data=b"No input provided")


# TODO: This operator does not work, because of send_model() serialization
@operator
def send_image_every_second(inputs: BaseMessage | None) -> BaseMessage:
    time.sleep(1)
    arr = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    return DataMessage(data=arr.tobytes())
