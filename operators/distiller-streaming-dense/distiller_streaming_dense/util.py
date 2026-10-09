from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import msgpack
import numpy as np
import zmq

from distiller_streaming_dense.math import com_dense
from distiller_streaming_dense.models import FrameHeader
from interactem.core.logger import get_logger

if TYPE_CHECKING:
    from distiller_streaming_dense.accumulator import FrameAccumulator
else:
    from pydantic import BaseModel

    FrameAccumulator = BaseModel


logger = get_logger()


def extract_header_frame_pairs(
    buffer: bytes, headers: list[FrameHeader]
) -> list[tuple[FrameHeader, np.ndarray]]:
    pairs: list[tuple[FrameHeader, np.ndarray]] = []
    offset = 0

    for header in headers:
        # Validate enough bytes remain for this frame
        if offset + header.data_size_bytes > len(buffer):
            raise ValueError(
                f"Insufficient data for frame at position "
                f"({header.STEM_row_in_scan}, {header.STEM_x_position_in_row}). "
                f"Expected {header.data_size_bytes} bytes at offset {offset}, "
                f"but only {len(buffer) - offset} bytes remaining."
            )

        # Slice and convert
        frame_bytes = buffer[offset : offset + header.data_size_bytes]
        frame_data = np.frombuffer(frame_bytes, dtype=header.np_dtype).reshape(
            header.frame_shape
        )
        pairs.append((header, frame_data))

        offset += header.data_size_bytes

    if offset != len(buffer):
        raise ValueError(f"Unused bytes detected: {len(buffer) - offset}")

    return pairs


def separate_header_datas(
    pairs: list[tuple[FrameHeader, np.ndarray]],
) -> tuple[list[FrameHeader], list[np.ndarray]]:
    if not pairs:
        return [], []
    headers, data = zip(*pairs, strict=True)
    return list(headers), list(data)


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

    subset = accumulator.data_flat[indices_to_sum]
    summed_dp = subset.sum(axis=0, dtype=np.float64)

    if summed_dp is None or summed_dp.sum() == 0:
        raise ValueError(f"Scan {scan_number}: Summed DP is empty")

    return summed_dp


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

    # Calculate center of mass
    center_yx = com_dense(diffraction_pattern)

    # Validate result
    if center_yx is None or center_yx.size == 0 or np.isnan(center_yx).any():
        raise ValueError("Center calculation failed")

    # Convert to integer coordinates (x,y)
    center = (int(center_yx[0, 0]), int(center_yx[1, 0]))

    return center


def get_diffraction_center(
    accumulator: FrameAccumulator, subsample_step: int = 2
) -> tuple[int, int]:
    """
    Convenience function that calculates the diffraction center from an accumulator.

    Args:
        accumulator: FrameAccumulator containing dense frames
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


def unpack_frame_array(
    packed_data: bytes,
) -> "FrameAccumulator":
    """Unpack a msgpack-encoded dense frame dataset into a FrameAccumulator.

    Expected payload: {
        "scan_number": int | None,
        "scan_shape": (int, int),
        "frame_shape": (int, int),
        "dtype": str,
        "data": bytes,  # raw dense array bytes, shape (*scan_shape, *frame_shape)
        "metadata": dict,
    }
    """
    from distiller_streaming_dense.accumulator import (
        FrameAccumulator as _FrameAccumulator,
    )

    unpacked_data = msgpack.unpackb(packed_data, raw=False)

    scan_number = unpacked_data.get("scan_number")
    scan_shape = tuple(unpacked_data["scan_shape"])
    frame_shape = tuple(unpacked_data["frame_shape"])
    dtype = np.dtype(unpacked_data.get("dtype", "uint32"))
    raw_bytes = unpacked_data["data"]
    metadata = unpacked_data.get("metadata", {})

    expected_size = int(np.prod(scan_shape)) * int(np.prod(frame_shape))
    array = np.frombuffer(raw_bytes, dtype=dtype)
    if array.size != expected_size:
        raise ValueError(
            f"Inconsistent unpacked data: expected {expected_size} elements "
            f"for scan_shape {scan_shape} x frame_shape {frame_shape}, got {array.size}"
        )
    array = array.reshape((*scan_shape, *frame_shape))

    accumulator = _FrameAccumulator(
        scan_number=scan_number if scan_number is not None else 0,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        dtype=dtype,
        metadata=metadata,
    )
    accumulator.data = array
    accumulator._frames_added = set(range(accumulator.num_scans))
    accumulator._num_frames_added = accumulator.num_scans

    return accumulator


def receive_and_unpack_frame_array(
    socket: zmq.Socket,
) -> "FrameAccumulator":
    packed_data = socket.recv(copy=False)

    return unpack_frame_array(bytes(packed_data.buffer))


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
