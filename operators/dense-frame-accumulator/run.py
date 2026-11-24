import io
from collections import OrderedDict
from typing import Any

import numpy as np
from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.models import BatchedFrames
from distiller_streaming_dense.util import (
    calculate_diffraction_center,
    get_summed_diffraction_pattern,
)
from PIL import Image

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()

# --- Operator State ---
accumulators: OrderedDict[int, FrameAccumulator] = OrderedDict()


def _normalize_to_uint8(pattern: np.ndarray) -> np.ndarray:
    lo, hi = pattern.min(), pattern.max()
    if hi <= lo:
        return np.zeros_like(pattern, dtype=np.uint8)
    scaled = (pattern - lo) / (hi - lo) * 255.0
    return scaled.astype(np.uint8)


@operator
def accumulate(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """
    Accumulates dense frames per scan, and once a scan is complete, emits a
    JPEG-encoded summed diffraction pattern.
    """
    global accumulators

    if not inputs:
        return None

    batch = BatchedFrames.from_bytes_message(inputs)
    scan_number = batch.header.scan_number

    max_concurrent_scans = int(parameters.get("max_concurrent_scans", 3))

    if scan_number not in accumulators:
        if len(accumulators) >= max_concurrent_scans:
            oldest_scan, _ = accumulators.popitem(last=False)
            logger.info(
                f"Evicting accumulator for scan {oldest_scan} to make room for scan {scan_number}"
            )

        logger.info(f"Creating new FrameAccumulator for scan {scan_number}")
        accumulators[scan_number] = FrameAccumulator(
            scan_number=scan_number,
            scan_shape=batch.header.scan_shape,
            frame_shape=batch.header.frame_shape,
        )

    accumulator = accumulators[scan_number]
    accumulators.move_to_end(scan_number)
    accumulator.add_message(inputs)

    if not accumulator.finished:
        logger.debug(
            f"Scan {scan_number}: {accumulator.num_frames_added} frames accumulated so far."
        )
        return None

    logger.info(f"Scan {scan_number}: complete ({accumulator.num_frames_added} frames).")

    summed_dp = get_summed_diffraction_pattern(accumulator, subsample_step=1)
    center = calculate_diffraction_center(summed_dp)

    image = Image.fromarray(_normalize_to_uint8(summed_dp), "L")
    bio = io.BytesIO()
    image.save(bio, format="JPEG")

    del accumulators[scan_number]

    logger.info(f"Scan {scan_number}: emitting summed diffraction pattern (center={center}).")
    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES, meta={}),
        data=bio.getvalue(),
    )
