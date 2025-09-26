from collections import OrderedDict
from typing import Any

import numpy as np
import stempy.image as stim  # Import stim
from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrames
from distiller_streaming.util import (
    calculate_diffraction_center,
    get_summed_diffraction_pattern,
)
from stempy import _image
from stempy.io import SparseArray

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


def patched_create_stem_images(
    input,
    inner_radii,
    outer_radii,
    center=(-1, -1),
):
    """Patched version of stempy.image.create_stem_images for NumPy 2.x compatibility"""

    # Ensure the inner and outer radii are tuples or lists
    if not isinstance(inner_radii, tuple | list):
        inner_radii = [inner_radii]
    if not isinstance(outer_radii, tuple | list):
        outer_radii = [outer_radii]

    # Electron counted data attributes
    if isinstance(input, SparseArray):
        imgs = _image.create_stem_images(
            input.data,
            inner_radii,
            outer_radii,
            input.scan_shape[::-1],
            input.frame_shape,
            center,
        )
    else:
        raise Exception(
            "Type of input, "
            + str(type(input))
            + ", is not known to stempy.image.create_stem_images()"
        )

    images = [np.asarray(img) for img in imgs]
    return np.asarray(images)


# Replace the original function
stim.create_stem_images = patched_create_stem_images


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
    batch = BatchedFrames.from_bytes_message(inputs)
    scan_number = batch.header.scan_number

    # --- 2. Get or Create FrameAccumulator ---
    max_concurrent_scans = int(parameters.get("max_concurrent_scans", 3))

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
            accumulators[scan_number] = FrameAccumulator.from_header(batch.header)
        except ValueError as e:
            logger.error(
                f"Failed to initialize FrameAccumulator for scan {scan_number}: {e}"
            )
            raise

    # Move the accessed scan to the end (most recently used)
    accumulator = accumulators[scan_number]
    accumulators.move_to_end(scan_number)
    accumulator.add_message(inputs)

    # --- 4. Check Calculation Frequency ---
    calc_freq = int(parameters.get("calculation_frequency", 100))
    if calc_freq <= 0:
        calc_freq = 100

    if not accumulator.finished and (
        accumulator.num_batches_added == 0
        or accumulator.num_batches_added % calc_freq != 0
    ):
        logger.debug(
            f"Scan {scan_number}: Not time to calculate yet. Messages added: {accumulator.num_batches_added}."
        )
        return None

    logger.debug(
        f"Scan {scan_number}: Triggering calculation after {accumulator.num_batches_added} messages."
    )

    subsample_step = int(parameters.get("subsample_step_center", 2))
    if subsample_step <= 0:
        subsample_step = 2

    logger.debug(
        f"Scan {scan_number}: Calculating center (subsample_step={subsample_step})."
    )
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
        "accumulated_messages": accumulator.num_batches_added,
        "shape": bf_image.shape,
        "dtype": str(bf_image.dtype),
        "center_used": center,
        "inner_radius": inner_radius,
        "outer_radius": outer_radius,
        "source_operator": "bright-field",
    }
    output_message = BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES, meta=output_meta),
        data=array_bytes,
    )
    logger.info(
        f"Scan {scan_number}: Emitting BF image ({bf_image.shape}). Num messages added so far: {accumulator.num_batches_added}"
    )
    return output_message
