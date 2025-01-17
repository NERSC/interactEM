import random
from typing import Any

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()


@operator
def error(inputs: BytesMessage | None, parameters: dict[str, Any]) -> BytesMessage:
    raise_exception = random.choice([True, False])
    # raise_exception = True
    logger.info(f"Error state: { raise_exception }")
    if raise_exception:
        raise Exception("This is an error")
    else:
        return BytesMessage(
            header=MessageHeader(subject=MessageSubject.BYTES, meta={}),
            data=b"Hello, World!",
        )
