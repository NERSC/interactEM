from collections import OrderedDict
from typing import Any

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrames
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

import quantem as em
from quantem.core import config
from quantem.core.datastructures import Dataset4dstem
from quantem.core.utils.diffractive_imaging_utils import fit_probe_circle

logger = get_logger()

# --- Operator State ---
# OrderedDict to hold FrameAccumulator instances with LRU behavior
accumulators: OrderedDict[int, FrameAccumulator] = OrderedDict()


@operator
def py4dstem_parallax(
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

    # --- 5. Perform Calculation ---
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

    logger.debug(f"Scan {scan_number}: Calculating parallax images.")

    probe_semiangle_mrad = 25
    energy = 300e3
    additional_rotation = 0
    com_rotaiton = -169 + additional_rotation

    data = accumuklator.get_dense()
    dc = em.datastructures.Dataset4dstem.from_array(data, 'test', (0,0,0,0), (1,1,2,2), ('A', 'A', 'mrad', 'mrad'), )
    dc.get_dp_mean()

    probe_qy0, probe_qx0, probe_semiangle_px = fit_probe_circle(
        dc.dp_mean.array, show=False,
        threshold=10
    )

    dc.sampling[2] = probe_semiangle_mrad / probe_semiangle_px
    dc.sampling[3] = probe_semiangle_mrad / probe_semiangle_px
    dc.units[2:] = ["mrad", "mrad"]

    # Process and return result
    output_meta = {
        "scan_number": scan_number,
        "accumulated_messages": accumulator.num_batches_added,
        "shape": dc.dp_mean.shape,
        "dtype": str(dc.dp_mean.dtype),
        "center_used": center,
        "source_operator": "py4dstem-dense",
    }

    parallax_BF_bytes = parallax.recon_BF.tobytes()
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return BytesMessage(header=header, data=parallax_BF_bytes)
