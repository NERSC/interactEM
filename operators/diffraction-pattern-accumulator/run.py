from collections import OrderedDict
from typing import Any

from distiller_streaming.accumulator import FrameAccumulator

# Import FrameAccumulator and FrameHeader
from distiller_streaming.util import get_summed_diffraction_pattern, validate_message

from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)
from interactem.operators.operator import operator

logger = get_logger()

# --- Operator State ---
# OrderedDict to hold FrameAccumulator instances with LRU behavior
accumulators: OrderedDict[int, FrameAccumulator] = OrderedDict()


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
    header, data = validate_message(inputs)
    scan_number = header.scan_number
    scan_shape = header.scan_shape
    frame_shape = header.frame_shape

    # --- 2. Get or Create FrameAccumulator ---
    max_concurrent_scans = parameters.get("max_concurrent_scans", 2)

    if scan_number not in accumulators:
        # Check if we need to evict old accumulators before creating new one
        if len(accumulators) >= max_concurrent_scans:
            # Remove the oldest accumulator (first item in OrderedDict)
            oldest_scan, oldest_accumulator = accumulators.popitem(last=False)
            logger.info(
                f"Evicting accumulator for scan {oldest_scan} to make room for scan {scan_number}"
            )

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
    # Move the accessed scan to the end (most recently used)
    accumulator = accumulators[scan_number]
    accumulators.move_to_end(scan_number)
    accumulator.add_message(inputs)

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
