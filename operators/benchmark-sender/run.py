import time
from typing import Any

import numpy as np

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()

# --- DataFrame Class Definition ---
class DataFrame:
    def __init__(self, data_size_bytes: int):
        self.scan_number = 0
        self.data = np.random.bytes(data_size_bytes)

# Generate DataFrames from 1KB to 32MB (doubling each time)
sizes_in_bytes = [1024 * (2 ** i) for i in range(0, 16)]
accumulated_data = [DataFrame(size) for size in sizes_in_bytes]

NUM_FRAMES_PER_SIZE = 1000

# Global state variables
current_size_index = 0
current_frame_repeat_count = 0
first_time = True

@operator
def send_benchmark_frame(inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:

    global current_size_index, current_frame_repeat_count, first_time

    # Completed sending frames
    if current_size_index >= len(sizes_in_bytes):
        return None

    # Wait for reciever to connect
    if first_time:
        time.sleep(2)
        first_time = False

    current_frame = accumulated_data[current_size_index]

    # Prepare metadata
    output_meta = {
        "scan_number": current_frame.scan_number,
        "frame_id": current_size_index * NUM_FRAMES_PER_SIZE + current_frame_repeat_count,
        "size": sizes_in_bytes[current_size_index]
    }

    # Create message
    output_message = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES,
            meta=output_meta
        ),
        data=current_frame.data,
    )

    # Update counters
    current_frame_repeat_count += 1

    if current_frame_repeat_count == NUM_FRAMES_PER_SIZE:
        # Interval between send receive of different sizes of messages
        interval = int(parameters.get("interval", 2))
        time.sleep(interval)

        current_size_index += 1
        current_frame_repeat_count = 0

    return output_message
