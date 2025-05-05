from collections.abc import Callable
from typing import Any

import msgpack
import numpy as np
import stempy.image as stim
import zmq
from stempy.io import SparseArray

from distiller_pipeline.accumulator import FrameAccumulator
from interactem.core.logger import get_logger

logger = get_logger()

def get_summed_diffraction_pattern(
    accumulator: FrameAccumulator, subsample_step: int = 2
) -> np.ndarray:
    """Calculate summed diffraction pattern from frames in accumulator."""
    scan_number = accumulator.scan_number
    num_frames = accumulator.num_frames_added

    if num_frames == 0:
        raise ValueError(f"Scan {scan_number}: No frames available for summing")

    # Get indices to sum
    added_indices = sorted(accumulator.frames_added_indices)
    indices_to_sum = added_indices[::subsample_step]

    if not indices_to_sum:
        raise ValueError(f"Scan {scan_number}: No frames left after subsampling")

    # Save original shape
    original_shape = accumulator.shape
    accumulator.ravel_scans()

    try:
        subset = accumulator[indices_to_sum]

        if not isinstance(subset, SparseArray):
            raise TypeError(f"Expected SparseArray subset, got {type(subset)}")

        summed_dp = subset.sum(axis=subset.scan_axes, dtype=np.float64)

        if summed_dp is None or summed_dp.sum() == 0:
            raise ValueError(f"Scan {scan_number}: Summed DP is empty")

        return summed_dp

    finally:
        if accumulator.shape != original_shape:
            accumulator.shape = original_shape


def calculate_diffraction_center(diffraction_pattern: np.ndarray) -> tuple[int, int]:
    """
    Calculates the beam center from a diffraction pattern using center of mass.

    Args:
        diffraction_pattern: 2D NumPy array of the diffraction pattern
        scan_number: Optional scan number for logging purposes

    Returns:
        Tuple of (center_x, center_y) coordinates

    Raises:
        ValueError: If diffraction pattern is empty or center calculation fails
    """
    # Validate input
    if diffraction_pattern is None or diffraction_pattern.size == 0:
        raise ValueError("Empty diffraction pattern")

    # Calculate center of mass using stempy function
    center_yx = stim.com_dense(diffraction_pattern)

    # Validate result
    if center_yx is None or center_yx.size == 0 or np.isnan(center_yx).any():
        raise ValueError("Center calculation failed")

    # Convert to integer coordinates (x,y)
    center = (int(center_yx[1, 0]), int(center_yx[0, 0]))

    logger.debug(f"Calculated center at {center}")
    return center


def get_diffraction_center(
    accumulator: FrameAccumulator, subsample_step: int = 2
) -> tuple[int, int]:
    """
    Convenience function that calculates the diffraction center from an accumulator.

    Args:
        accumulator: FrameAccumulator containing sparse frames
        subsample_step: Step size for subsampling positions

    Returns:
        Tuple of (center_x, center_y) coordinates

    Raises:
        ValueError: If calculation fails at any stage
    """
    # Get the summed diffraction pattern
    summed_dp = get_summed_diffraction_pattern(
        accumulator, subsample_step=subsample_step
    )

    # Calculate center from the pattern
    return calculate_diffraction_center(summed_dp)


def unpack_sparse_array(
    packed_data: bytes,
) -> SparseArray:
    unpacked_data = msgpack.unpackb(packed_data, raw=False)

    scan_number = unpacked_data.get("scan_number")
    scan_shape = tuple(unpacked_data["scan_shape"])
    frame_shape = tuple(unpacked_data["frame_shape"])
    raw_data = unpacked_data["data"]  # Expected: list[list[list[int]]]
    metadata = unpacked_data.get("metadata", {})

    num_scan_positions = len(raw_data)
    expected_scan_positions = np.prod(scan_shape) if scan_shape else 0

    if expected_scan_positions != num_scan_positions:
        raise ValueError(
            f"Inconsistent unpacked data: scan_shape {scan_shape} product ({expected_scan_positions}) "
            f"does not match outer data length {num_scan_positions}"
        )

    # Determine frames_per_scan safely, handle empty scans
    frames_per_scan = len(raw_data[0]) if num_scan_positions > 0 else 0

    # Create the outer numpy array with dtype=object
    data_array = np.empty(scan_shape + (frames_per_scan,), dtype=object)

    for i in range(num_scan_positions):
        scan_index = np.unravel_index(i, scan_shape)
        if len(raw_data[i]) != frames_per_scan:
            raise ValueError(
                f"Inconsistent frame count at scan position {i} (index {scan_index}): "
                f"expected {frames_per_scan}, got {len(raw_data[i])}"
            )
        for j in range(frames_per_scan):
            data_array[scan_index + (j,)] = np.array(raw_data[i][j], dtype=np.uint32)

    # --- Instantiate SparseArray ---
    sparse_array = SparseArray(
        data=data_array,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        metadata=metadata,
    )
    sparse_array.metadata["frames_per_scan"] = frames_per_scan
    if scan_number is not None:
        sparse_array.metadata["scan_number"] = scan_number

    return sparse_array


def receive_and_unpack_sparse_array(
    socket: zmq.Socket,
) -> SparseArray:
    packed_data = socket.recv(copy=False)

    return unpack_sparse_array(bytes(packed_data.buffer))


def parse_nested_dict(
    data: dict, inner_parser: Callable[[Any], Any], depth: int
) -> dict:
    """
    Recursively parse a nested dictionary with string keys expected to be integers.

    Args:
        data: The dictionary to parse.
        inner_parser: The function to apply to the innermost values.
        depth: The current nesting depth (starts at the desired level, e.g., 2 for two levels).

    Returns:
        The parsed dictionary with integer keys.

    Raises:
        ValueError: If keys cannot be converted to int or structure is invalid.
        TypeError: If input is not a dictionary at expected levels.
    """
    if depth < 1:
        raise ValueError("Depth must be at least 1")
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict at depth {depth}, got {type(data)}")

    parsed = {}
    for k, v in data.items():
        try:
            int_key = int(k)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid key '{k}' at depth {depth}, expected integer")

        if depth == 1:
            parsed[int_key] = inner_parser(v)
        else:
            parsed[int_key] = parse_nested_dict(v, inner_parser, depth - 1)
    return parsed


def decode_str(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return str(value)  # Fallback for non-UTF8 bytes
    return str(value)
