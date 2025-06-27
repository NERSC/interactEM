from typing import Any

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator

logger = get_logger()

@operator
def receive_benchmark_frame(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> None:

    if inputs:
        meta = inputs.header.meta if hasattr(inputs.header, 'meta') else {}
        content_preview = inputs.data[:64]  # Show first 64 bytes
        logger.info(f"Received message: {len(inputs.data)} bytes, meta: {meta}, preview: {content_preview!r}")
    else:
        logger.warning("No input message received.")

    return None
