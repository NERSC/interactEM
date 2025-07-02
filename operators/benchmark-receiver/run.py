import time
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

NUM_FRAMES_PER_SIZE = 1000 # expected number of frames per size

# Global state variables for tracking metrics (keyed by frame size)
received_frame_counts = {} # count of frames received
total_bytes_received = {} # total bytes received
start_times = {} # timestamp when first frame received
end_times = {} # timestamp when last frame received

@operator
def receive_benchmark_frame(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> None:

    global received_frame_counts, total_bytes_received, start_times, end_times

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
        total_bytes_received[frame_size] = 0
        received_frame_counts[frame_size] = 0
        start_times[frame_size] = time.time()
        logger.info(f"Started receiving frames of {frame_size/1024:.1f} KB")

    # Update counters
    received_frame_counts[frame_size] += 1
    total_bytes_received[frame_size] += actual_data_size

    if received_frame_counts[frame_size] == NUM_FRAMES_PER_SIZE:
        end_times[frame_size] = time.time()
        total_time = end_times[frame_size] - start_times[frame_size]
        total_mb = total_bytes_received[frame_size] / (1024 * 1024)
        throughput_mbps = (total_bytes_received[frame_size] * 8) / (total_time * 1_000_000)
        message_rate = NUM_FRAMES_PER_SIZE / total_time
        logger.info(
            f"COMPLETED {NUM_FRAMES_PER_SIZE} frames of {frame_size/1024:.1f} KB | "
            f"Total: {total_mb:.2f} MB | Time: {total_time:.2f}s | "
            f"Throughput: {throughput_mbps:.2f} Mbps | Rate: {message_rate:.1f} msg/s | "
        )

    return None
