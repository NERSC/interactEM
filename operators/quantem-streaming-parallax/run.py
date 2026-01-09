from collections import OrderedDict
from typing import Any

import numpy as np
import quantem as em
from quantem.core.utils.diffractive_imaging_utils import fit_probe_circle
from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrames

from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)
from interactem.operators.operator import operator

logger = get_logger()


def _detect_quantem_device() -> str:
    try:
        import torch  # quantem depends on torch
    except Exception:
        return "cpu"

    if torch.cuda.is_available():
        return "gpu"

    return "cpu"


QUANTEM_DEVICE = _detect_quantem_device()
logger.info(f"quantem-direct-ptycho using device={QUANTEM_DEVICE}")


class FrameAccumulatorFull(FrameAccumulator):
    def completely_finished(self) -> bool:
        """Check if all expected frames have been added."""
        num_batches_added = self.num_batches_added
        total_batches_expected = self._total_batches_expected

        if not num_batches_added:
            return False

        if not total_batches_expected:
            return False

        if num_batches_added // total_batches_expected == 1:
            return True
        else:
            return False


# --- Operator State ---
# OrderedDict to hold FrameAccumulator instances with LRU behavior
accumulators: OrderedDict[int, FrameAccumulatorFull] = OrderedDict()


@operator
def streaming_parallax(
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
    max_concurrent_scans = int(parameters.get("max_concurrent_scans", 1))

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
            accumulators[scan_number] = FrameAccumulatorFull.from_header(batch.header)
        except ValueError as e:
            logger.error(
                f"Failed to initialize FrameAccumulator for scan {scan_number}: {e}"
            )
            raise

    # Move the accessed scan to the end (most recently used)
    accumulator = accumulators[scan_number]
    accumulators.move_to_end(scan_number)
    accumulator.add_message(inputs)

    # Check if all frames have been added
    if not (accumulator.completely_finished()):
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

    logger.info(f"Scan {scan_number}: Calculating parallax.")

    # Calculation parameters
    probe_semiangle = float(parameters.get("probe_semiangle", 25.0))
    energy = int(parameters.get("accelerating_voltage", 300e3))
    probe_step_size = float(
        parameters.get("probe_step_size", 0.1)
    )  # test data set: 0.14383155 nm
    initial_defocus_nm = float(parameters.get("initial_defocus", 0))  # in nanometers
    defocus = initial_defocus_nm * 10  # convert to Angstroms
    diffraction_rotation_angle = float(
        parameters.get("diffraction_rotation_angle", 0)
    )  # in degrees
    rotation_angle = diffraction_rotation_angle * np.pi / 180  # convert to radians
    crop_probes = int(parameters.get("crop_probes", 0))

    if crop_probes == 0:
        logger.info(f"Scan {scan_number}: No cropping of probes applied.")
        dense_data = accumulator[:, :-1, :, :].to_dense()  ## remove the flyback column
    else:
        logger.info(f"Scan {scan_number}: Crop and densify.")
        dense_data = accumulator[crop_probes:-crop_probes, crop_probes:-crop_probes-1, :, :].to_dense()  ## crop the edges if needed and remove the flyback column
    
    #energy = 300e3
    #defocus = 1.5e4
    #rotation_angle = np.deg2rad(-15)
    upsampling_factor = 1

    dataset = em.datastructures.Dataset4dstem.from_array(array=dense_data)
    logger.debug(f"dense shape = {dense_data.shape}")
    wavelength = em.core.utils.utils.electron_wavelength_angstrom(energy)

    scan_gpts = dataset.shape[:2]
    gpts = dataset.shape[-2:]

    scan_sampling = dataset.sampling[:2]
    angular_sampling = dataset.sampling[-2:]

    dataset.get_dp_mean()
    probe_qy0, probe_qx0, probe_R = fit_probe_circle(dataset.dp_mean.array, show=False)
    logger.debug(f"fit probe circle: {probe_qy0}, {probe_qx0}, {probe_R}")
    bf_mask = torch.as_tensor(
        np.fft.ifftshift(
            dataset.dp_mean.array > dataset.dp_mean.array.max() * 0.5
        )
    )

    dataset.sampling[2] = probe_semiangle / probe_R
    dataset.sampling[3] = probe_semiangle / probe_R
    dataset.units[2:] = ["mrad", "mrad"]

    dataset.sampling[0] = (
        probe_step_size * 10
    )  ## convert to be Anggstrom for quantem. distiller will give nanometers.
    dataset.sampling[1] = probe_step_size * 10
    dataset.units[0:2] = ["A", "A"]
    logger.info(f"Scan {scan_number}: Start streaming parallax")
    try:
        stream_prlx = em.diffractive_imaging.StreamingParallax(
                            gpts,
                            scan_gpts,
                            scan_sampling,
                            wavelength,
                            bf_mask,
                            angular_sampling=angular_sampling,
                            aberration_coefs={"C10":-defocus},
                            rotation_angle=rotation_angle,
                            upsampling_factor=1,
                            enable_phase_flipping=True
                        ).preprocess(
                        )
        logger.info(f"Scan {scan_number}: Calculate parallax")
        streamed_data = torch.as_tensor(dataset.array.reshape((-1,)+gpts))
        r_up = stream_prlx._return_scan_positions()
        psi = torch.zeros(stream_prlx.upsampled_gpts)
        psi_flipped = torch.zeros(stream_prlx.upsampled_gpts)

        stream_prlx.reconstruct(
            psi,
            psi_flipped,
            streamed_data[:2000],
            r_up[:2000],
        )

        # Process and return result
        logger.info(f"Scan {scan_number}: Reconstruction done")
        output_bytes = psi.tobytes()
        output_meta = {
            "scan_number": scan_number,
            "shape": psi.shape,
            "dtype": str(psi.dtype),
            "source_operator": "quantem-streaming-parallax",
        }
    except Exception as e:
        zeros_out = np.zeros(accumulator.scan_shape, dtype=np.uint8)
        logger.exception(
            f"Parallax reconstruction failed for scan {scan_number}: {e}"
        )
        output_bytes = zeros_out.tobytes()
        output_meta = {
            "scan_number": scan_number,
            "accumulated_messages": accumulator.num_batches_added,
            "shape": zeros_out.shape,
            "dtype": str(zeros_out.dtype),
            "source_operator": "quantem-direct-ptycho-failed",
        }
    finally:
        # free up GPU memory
        del dataset
        torch.cuda.empty_cache()
        gc.collect()
    header = MessageHeader(subject=MessageSubject.BYTES, meta=output_meta)
    return BytesMessage(header=header, data=output_bytes)
