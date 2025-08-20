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

total_size_bytes = 4_294_967_296
# Generate DataFrames from 1KB to 16MB (doubling each time)
sizes_in_bytes = [1024 * (2 ** i) for i in range(0, 15)]
num_frames_per_size = [total_size_bytes // size for size in sizes_in_bytes]
accumulated_data = [DataFrame(size) for size in sizes_in_bytes]

# Global state variables
current_size_index = 0
current_frame_repeat_count = 0
first_time = True
cumulative_frames = 0

@operator
def send_benchmark_frame(inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:

    global current_size_index, current_frame_repeat_count, first_time, cumulative_frames

    # Completed sending frames
    if current_size_index >= len(sizes_in_bytes):
        return None

    # Wait for receiver to connect
    if first_time:
        time.sleep(2)
        first_time = False

    current_frame = accumulated_data[current_size_index]

    frame_id = cumulative_frames + current_frame_repeat_count

    # Prepare metadata
    output_meta = {
        "scan_number": current_frame.scan_number,
        "frame_id": frame_id,
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

    # Check if we've sent all frames for current size
    if current_frame_repeat_count == num_frames_per_size[current_size_index]:
        # Interval between send receive of different sizes of messages
        interval = int(parameters.get("interval", 45))
        time.sleep(interval)

        cumulative_frames += num_frames_per_size[current_size_index]
        current_size_index += 1
        current_frame_repeat_count = 0

    return output_message
