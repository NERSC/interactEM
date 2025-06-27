import time
from typing import Any

import numpy as np

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()

# --- Global Accumulator: 256 MB ---
ACCUMULATOR_SIZE = 268_434_432  # 256 MB in bytes
accumulated_data = np.random.randint(0, 256, ACCUMULATOR_SIZE, dtype=np.uint8)

# --- Operator State ---
data_pointer = 0
chunk_counter = 0

# --- Chunk Size Configuration ---
MIN_CHUNK_SIZE = 1024        # 1 KB
MAX_CHUNK_SIZE = 128 * 1024 * 1024  # 128 MB for local machine

@operator
def send_benchmark_frame(inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:

    global data_pointer, chunk_counter

    interval = int(parameters.get("interval", 2))

    time.sleep(interval)

    # Check if we've sent all chunks
    if data_pointer >= ACCUMULATOR_SIZE:
        return None

    chunk_size = int(MIN_CHUNK_SIZE * (2**chunk_counter)) # doubles the chunk size in each iteration
    chunk_size = min(chunk_size, MAX_CHUNK_SIZE) # Cap at MAX_CHUNK_SIZE
    chunk_size = min(chunk_size, ACCUMULATOR_SIZE - data_pointer) # Ensure we don't exceed the remaining data

    # Extract data for this chunk
    end_pointer = data_pointer + chunk_size
    chunk_data = accumulated_data[data_pointer:end_pointer]

    # Prepare metadata
    output_meta = {
        "scan_number": 0,
        "chunk_index": int(chunk_counter),
        "chunk_size": int(chunk_size),
        "data_start": int(data_pointer),
        "data_end": int(end_pointer),
        "accumulator_size": int(ACCUMULATOR_SIZE),
        "timestamp": time.time(),
        "chunk_size_kb": round(chunk_size / 1024, 2),
    }

    # Convert to bytes
    array_bytes = chunk_data.tobytes()

    # Create message
    output_message = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES, meta=output_meta
        ),
        data=array_bytes,
    )

    # Log progress
    logger.info(
        f"Sent chunk {chunk_counter + 1}: {chunk_size:,} bytes ({chunk_size/1024:.1f} KB)"
    )

    # Update counters
    data_pointer = end_pointer
    chunk_counter += 1

    return output_message
