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
    # calc_freq = int(parameters.get("calculation_frequency", 100))
    # if calc_freq <= 0:
    #     calc_freq = 100

    # if not accumulator.finished and (
    #     accumulator.num_batches_added == 0
    #     or accumulator.num_batches_added % calc_freq != 0
    # ):
    #     logger.debug(
    #         f"Scan {scan_number}: Not time to calculate yet. Messages added: {accumulator.num_batches_added}."
    #     )
    #     return None

    if not accumulator.num_batches_added == 244:
        if accumulator.num_batches_added % 20 == 0:
            logger.info(
                f"Scan {scan_number}: Not time to calculate yet. Frames added: {accumulator.num_frames_added}."
            )
        return None

    # --- 5. Perform Calculation ---
    logger.info(
        f"Scan {scan_number}: Triggering calculation after {accumulator.num_batches_added} messages."
    )
    logger.info(f"Accumulator finished: {accumulator.finished}")

    subsample_step = int(parameters.get("subsample_step_center", 2))
    if subsample_step <= 0:
        subsample_step = 2

    logger.info(
        f"Scan {scan_number}: Calculating center (subsample_step={subsample_step})."
    )
    dp = get_summed_diffraction_pattern(accumulator, subsample_step=subsample_step)

    logger.info(f"Scan {scan_number}: Calculating ptycho images.")

    probe_semiangle = 25
    energy = 300e3

    logger.info(f"densify")
    data = accumulator.to_dense()[:,:-1,:,:]  ## remove last row and column to make it even sized
    dset = em.datastructures.Dataset4dstem.from_array(array=data)
    logger.info(f"dense shape = {data.shape}")

    dset.get_dp_mean()
    logger.info(f"fit probe circle")
    probe_qy0, probe_qx0, probe_R = fit_probe_circle(
        dset.dp_mean.array, show=False
    )
    logger.info(f"{probe_qy0}, {probe_qx0}, {probe_R}")

    logger.info(f"input metadata")
    dset.sampling[2] = probe_semiangle / probe_R
    dset.sampling[3] = probe_semiangle / probe_R
    dset.units[2:] = ["mrad", "mrad"]

    dset.sampling[0] = 0.14383155 * 10 ## this has to be Anggstrom for quantem
    dset.sampling[1] = 0.14383155 * 10
    dset.units[0:2] = ["A", "A"]

    logger.info(f"{dset.units}")

    logger.info(f"run direct ptycho")
    try:
        direct_ptycho = em.diffractive_imaging.direct_ptychography.DirectPtychography.from_dataset4d(
                            dset,
                            energy=energy,
                            semiangle_cutoff=probe_semiangle,
                            device="cpu", 
                            aberration_coefs={'C10':0},
                            max_batch_size=10,
                            rotation_angle=0, # need radians
                            )
        
        logger.info(f"fit hyperparameters")
        direct_ptycho.fit_hyperparameters()
        initial_parallax = direct_ptycho.reconstruct_with_fitted_parameters(
            upsampling_factor = 2,  ### this can be changed
            max_batch_size = 10
        )

        logger.debug(f"reconstruction done")
        # Process and return result
        output_bytes = initial_parallax.obj.tobytes()
        output_meta = {
            "scan_number": scan_number,
            "shape": initial_parallax.obj.shape,
            "dtype": str(initial_parallax.obj.dtype),
            "source_operator": "quantem-direct-ptycho",
        }
    except:
        raise
        logger.info(f"Direct ptychography reconstruction failed for scan {scan_number}.")
        output_bytes = dp.tobytes()
        output_meta = {
            "scan_number": scan_number,
            "accumulated_messages": accumulator.num_batches_added,
            "shape": dp.shape,
            "dtype": str(dp.dtype),
            "source_operator": "quantem-direct-ptycho-failed",
        }

    header = MessageHeader(subject=MessageSubject.BYTES, meta=output_meta)
    return BytesMessage(header=header, data=output_bytes)
