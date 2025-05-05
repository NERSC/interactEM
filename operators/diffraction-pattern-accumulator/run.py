from typing import Any

import numpy as np
from distiller_pipeline.accumulator import FrameAccumulator
from distiller_pipeline.models import FrameHeader

# Import FrameAccumulator and FrameHeader
from distiller_pipeline.util import (
    get_summed_diffraction_pattern,
)

from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)
from interactem.operators.operator import operator

logger = get_logger()

# --- Operator State ---
# Dictionary to hold FrameAccumulator instances, keyed by scan_number
accumulators: dict[int, FrameAccumulator] = {}


# --- Operator Kernel ---
@operator
def accumulate_diffraction(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """
    Accumulates sparse diffraction frames using FrameAccumulator for each scan number
    and emits the summed pattern periodically.
    """
    global accumulators

    if not inputs:
        return None

    # --- 1. Extract Metadata and Frame Data ---
    header = FrameHeader(**inputs.header.meta) # Use FrameHeader directly
    scan_number = header.scan_number
    scan_shape = (header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1)
    frame_shape = header.frame_shape
    sparse_indices = np.frombuffer(inputs.data, dtype=np.uint32)

    # --- 2. Get or Create FrameAccumulator ---
    if scan_number not in accumulators:
        # Clear existing accumulators if a new scan starts
        if accumulators:
            logger.info(f"New scan {scan_number} detected. Clearing previous accumulators.")
            accumulators.clear()
        try:
            logger.info(f"Creating new FrameAccumulator for scan {scan_number}")
            accumulators[scan_number] = FrameAccumulator(
                scan_number=scan_number,
                scan_shape=scan_shape,
                frame_shape=frame_shape,
            )
        except ValueError as e:
             logger.error(f"Failed to initialize FrameAccumulator for scan {scan_number}: {e}")
             raise

    # --- 3. Accumulate Frame ---
    accumulator = accumulators[scan_number]
    accumulator.add_frame(header, sparse_indices)

    # --- 4. Check Emission Frequency ---
    update_frequency = int(parameters.get("update_frequency", 100))
    if update_frequency <= 0:
        update_frequency = 100

    if accumulator.num_frames_added == 0:
        logger.debug(f"Scan {scan_number}: No frames added yet.")
        return None

    if accumulator.num_frames_added % update_frequency != 0:
        logger.debug(f"Scan {scan_number}: Not time to emit yet. Frames added: {accumulator.num_frames_added}.")
        return None

    logger.debug(
        f"Scan {scan_number}: Emitting accumulated pattern after {accumulator.num_frames_added} frames."
    )

    # --- Calculate Summed Pattern ---
    summed_dp = get_summed_diffraction_pattern(accumulator)

    # --- Prepare raw data output ---
    array_bytes = summed_dp.tobytes()

    # Create output message with raw array bytes and required metadata
    output_meta = {
        "scan_number": scan_number,
        "accumulated_frames": accumulator.num_frames_added,
        "shape": summed_dp.shape,
        "dtype": str(summed_dp.dtype),
    }
    output_message = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES, meta=output_meta
        ),
        data=array_bytes,
    )
    return output_message
