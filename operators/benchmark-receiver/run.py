from typing import Any

from pydantic import BaseModel, ValidationError

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator

logger = get_logger()

class FrameHeader(BaseModel):
    scan_number: int
    frame_id: int
    size: int

# Global state variables for tracking (keyed by frame size)
received_frame_counts = {} # count of frames received
total_bytes_received = {} # total bytes received
prev_batch_frame_size = None

@operator
def receive_benchmark_frame(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> None:

    global received_frame_counts, total_bytes_received, prev_batch_frame_size

    if not inputs:
        return None

    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError:
        logger.error("Invalid message")
        return None

    frame_size = header.size  # Size in bytes from metadata
    actual_data_size = len(inputs.data)

    # Use frame_size as the key for tracking
    if frame_size not in received_frame_counts:
        if prev_batch_frame_size is not None and prev_batch_frame_size in received_frame_counts:
            logger.info(
                f"Finished receiving frames of {prev_batch_frame_size/1024:.1f} KB: "
                f"count={received_frame_counts[prev_batch_frame_size]}, "
                f"total_bytes={total_bytes_received[prev_batch_frame_size]} "
                f"({total_bytes_received[prev_batch_frame_size]/1024:.1f} KB)"
            )
        total_bytes_received[frame_size] = 0
        received_frame_counts[frame_size] = 0

        logger.info(f"Started receiving frames of {frame_size/1024:.1f} KB")
        prev_batch_frame_size = frame_size

    # Update counters
    received_frame_counts[frame_size] += 1
    total_bytes_received[frame_size] += actual_data_size
    return None
