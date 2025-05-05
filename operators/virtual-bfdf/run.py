from typing import Any

import numpy as np
import stempy.image as stim  # Import stim
from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import FrameHeader
from distiller_streaming.util import (
    calculate_diffraction_center,
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
def calculate_bright_field(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """
    Accumulates sparse frames, calculates diffraction center periodically,
    and calculates/emits virtual bright field images.
    """
    global accumulators

    if not inputs:
        return None

    # --- 1. Extract Metadata and Frame Data ---

    # Parse the full header first
    header = FrameHeader(**inputs.header.meta)
    scan_number = header.scan_number
    # Construct scan_shape from metadata (height, width)
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
             # Cannot proceed with this scan if accumulator fails
             raise


    accumulator = accumulators[scan_number]
    accumulator.add_frame(header, sparse_indices)

   # --- 4. Check Calculation Frequency ---
    calc_freq = int(parameters.get("calculation_frequency", 100))
    if calc_freq <= 0:
        calc_freq = 100

    if accumulator.num_frames_added == 0 or accumulator.num_frames_added % calc_freq != 0:
        logger.debug(f"Scan {scan_number}: Not time to calculate yet. Frames added: {accumulator.num_frames_added}.")
        return None

    logger.debug(f"Scan {scan_number}: Triggering calculation after {accumulator.num_frames_added} frames.")

    subsample_step = int(parameters.get("subsample_step_center", 2))
    if subsample_step <= 0:
        subsample_step = 2

    logger.debug(f"Scan {scan_number}: Calculating center (subsample_step={subsample_step}).")
    dp = get_summed_diffraction_pattern(accumulator, subsample_step=subsample_step)
    center = calculate_diffraction_center(dp)
    logger.debug(f"Scan {scan_number}: Center calculated: {center}.")

    logger.debug(f"Scan {scan_number}: Calculating BF image with center {center}.")
    inner_radius = int(parameters.get("inner_radius", 0))
    outer_radius = int(parameters.get("outer_radius", 75))
    if inner_radius < 0:
        inner_radius = 0
    if outer_radius <= inner_radius:
        outer_radius = inner_radius + 1

    # Calculate STEM images using stim.create_stem_images
    stem_images = stim.create_stem_images(
        accumulator,
        inner_radii=(inner_radius,),
        outer_radii=(outer_radius,),
        center=center,
    )

    bf_image = stem_images[0,]
    array_bytes = bf_image.tobytes()

    output_meta = {
        "scan_number": scan_number,
        "accumulated_frames": accumulator.num_frames_added,
        "shape": bf_image.shape,
        "dtype": str(bf_image.dtype),
        "center_used": center,
        "inner_radius": inner_radius,
        "outer_radius": outer_radius,
        "source_operator": "bright-field"
    }
    output_message = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES, meta=output_meta
        ),
        data=array_bytes,
    )
    logger.info(f"Scan {scan_number}: Emitting BF image ({bf_image.shape}).")
    return output_message
