import gc
from collections import OrderedDict
from typing import Any

import numpy as np
import quantem as em
from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrames
from quantem.core.utils.diffractive_imaging_utils import fit_probe_circle
from quantem.diffractive_imaging.direct_ptychography import (
    DirectPtychography,
    OptimizationParameter,
)

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
def quantem_direct_ptycho(
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
    max_concurrent_scans = 1  # TODO: remove this

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
    logger.info(f"Scan {scan_number}: Calculating ptycho images.")

    # Calculation parameters
    energy = parameters.get("accelerating_voltage", 300e3)
    probe_semiangle = parameters.get("probe_semiangle", 25.0)
    # test data set: 0.14383155 nm probe step size
    probe_step_size_nm = parameters.get("probe_step_size", 0.1)
    probe_step_size_A = probe_step_size_nm * 10
    upsampling_factor = parameters.get("upsampling_factor", 2)

    optimize_defocus = bool(parameters.get("optimize_defocus", True))
    if optimize_defocus:
        defocus_search_max_nm = parameters.get("defocus_search_range", 50)
        defocus_search_max_A = defocus_search_max_nm * 10  # convert to Angstroms
    else:
        defocus_search_max_A = 0

    initial_defocus_nm = parameters.get("initial_defocus", 0)
    initial_defocus_A = initial_defocus_nm * 10

    # Only search in one direction from initial guess
    if initial_defocus_A > 0:
        defocus_search_range_A = (0, defocus_search_max_A)
    elif initial_defocus_A < 0:
        defocus_search_range_A = (-defocus_search_max_A, 0)
    else:
        defocus_search_range_A = (-defocus_search_max_A, defocus_search_max_A)

    # in degrees
    diffraction_rotation_angle_deg = parameters.get("diffraction_rotation_angle", 0)
    rotation_angle = diffraction_rotation_angle_deg * np.pi / 180  # convert to radians

    optimize_angle = bool(parameters.get("optimize_rotation_angle", False))

    optimize_C12 = bool(parameters.get("optimize_C12", False))
    if optimize_C12:
        maximum_C12_magnitude_nm = parameters.get("maximum_C12_magnitude", 10)
        maximum_C12_magnitude_A = maximum_C12_magnitude_nm * 10  # convert to Angstroms
    else:
        maximum_C12_magnitude_A = None

    deconvolution_kernel = parameters.get("deconvolution_kernel", "parallax")

    crop_probes = parameters.get("crop_probes", 0)
    if crop_probes == 0:
        logger.info(f"Scan {scan_number}: No cropping of probes applied.")
        dense_data = accumulator[:, :-1, :, :].to_dense()  ## remove the flyback column
    else:
        logger.info(f"Scan {scan_number}: Crop and densify.")
        dense_data = accumulator[
            crop_probes:-crop_probes, crop_probes : -crop_probes - 1, :, :
        ].to_dense()  ## crop the edges if needed and remove the flyback column

    # Convert SparseArray to Dataset4dstem
    dset = em.datastructures.Dataset4dstem.from_array(array=dense_data)
    logger.debug(f"dense shape = {dense_data.shape}")

    dset.get_dp_mean()
    probe_qy0, probe_qx0, probe_R = fit_probe_circle(dset.dp_mean.array, show=False)
    logger.debug(f"fit probe circle: {probe_qy0}, {probe_qx0}, {probe_R}")

    dset.sampling[2] = probe_semiangle / probe_R
    dset.sampling[3] = probe_semiangle / probe_R
    dset.units[2:] = ["mrad", "mrad"]

    dset.sampling[0:2] = probe_step_size_A
    dset.units[0:2] = ["A", "A"]

    logger.info(f"Scan {scan_number}: Start direct ptycho")
    try:
        # Initialize DirectPtychography with initial guesses
        aberration_coefs = {}
        if initial_defocus_A is not None:
            aberration_coefs["C10"] = -initial_defocus_A  # Note the negative sign

        direct_ptycho = DirectPtychography.from_dataset4d(
            dset,
            energy=energy,
            semiangle_cutoff=probe_semiangle,
            device=QUANTEM_DEVICE,
            aberration_coefs=aberration_coefs if aberration_coefs else None,
            max_batch_size=10,
            rotation_angle=rotation_angle,  # need radians
        )

        if optimize_C12 or optimize_angle or optimize_defocus:
            logger.info(f"Scan {scan_number}: Optimizing hyperparameters")

            # Build optimization aberration coefficients
            opt_aberration_coefs = {}

            if optimize_defocus:
                opt_aberration_coefs["C10"] = OptimizationParameter(
                    defocus_search_range_A[0], defocus_search_range_A[1]
                )
            else:
                opt_aberration_coefs["C10"] = -initial_defocus_A

            if optimize_C12:
                opt_aberration_coefs["C12"] = OptimizationParameter(
                    0, maximum_C12_magnitude_A
                )
                opt_aberration_coefs["phi12"] = OptimizationParameter(
                    -np.pi / 2, np.pi / 2
                )

            if optimize_angle:
                opt_rotation_angle = OptimizationParameter(0, np.pi)
            else:
                opt_rotation_angle = rotation_angle

            direct_ptycho.optimize_hyperparameters(
                aberration_coefs=opt_aberration_coefs,
                rotation_angle=opt_rotation_angle,
                deconvolution_kernel=deconvolution_kernel,
                n_trials=25,
                max_batch_size=10,
            )
        else:
            logger.info(f"Scan {scan_number}: Using manual hyperparameter settings")

        initial_parallax = direct_ptycho.reconstruct(
            deconvolution_kernel=deconvolution_kernel,
            upsampling_factor=upsampling_factor,
            max_batch_size=10,
        )

        # Process and return result
        logger.info(f"Scan {scan_number}: Reconstruction done")
        output_bytes = initial_parallax.obj.tobytes()
        output_meta = {
            "scan_number": scan_number,
            "shape": initial_parallax.obj.shape,
            "dtype": str(initial_parallax.obj.dtype),
            "source_operator": "quantem-direct-ptycho",
            "direct_ptycho_params": {'C12': direct_ptycho.hyperparameter_state.optimized_aberrations['C12'],
                                     'phi12': direct_ptycho.hyperparameter_state.optimized_aberrations['phi12'],
                                    'C10': -direct_ptycho.aberration_coefs['C10'],
                                    'rotation_angle': direct_ptycho.rotation_angle,
                                    },
        }
        header = MessageHeader(subject=MessageSubject.BYTES, meta=output_meta)
        return BytesMessage(header=header, data=output_bytes)
    except Exception as e:
        logger.exception(
            f"Direct ptychography reconstruction failed for scan {scan_number}: {e}"
        )
    finally:
        if QUANTEM_DEVICE == "gpu":
            try:
                import torch
                del direct_ptycho
                torch.cuda.empty_cache()
                gc.collect()
            except Exception:
                logger.exception("Failed to clean up DirectPtychography resources.")
