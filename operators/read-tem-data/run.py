from pathlib import Path
from typing import Any

import ncempy
import numpy as np
from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.emitter import BatchEmitter
from distiller_streaming_dense.models import NumpyDtype

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()

data_dir = Path(f"{DATA_DIRECTORY}/raw_data_dir")

active_emitter: BatchEmitter | None = None
current_scan_number: int = 1
current_file: str | None = None
cached_array: tuple[str, np.ndarray] | None = None


def _resolve_shapes(
    data: np.ndarray, parameters: dict[str, Any]
) -> tuple[tuple[int, int], tuple[int, int]]:
    scan_shape_y = int(parameters.get("scan_shape_y", 0) or 0)
    scan_shape_x = int(parameters.get("scan_shape_x", 0) or 0)
    frame_shape_y = int(parameters.get("frame_shape_y", 0) or 0)
    frame_shape_x = int(parameters.get("frame_shape_x", 0) or 0)

    if scan_shape_y and scan_shape_x and frame_shape_y and frame_shape_x:
        return (scan_shape_y, scan_shape_x), (frame_shape_y, frame_shape_x)

    if data.ndim != 4:
        raise ValueError(
            f"Expected a 4D array (scan_y, scan_x, frame_y, frame_x) from ncempy, "
            f"got shape {data.shape} (ndim={data.ndim}). "
            f"Set scan_shape_y/scan_shape_x/frame_shape_y/frame_shape_x explicitly."
        )

    return (int(data.shape[0]), int(data.shape[1])), (int(data.shape[2]), int(data.shape[3]))


def _coerce_wire_dtype(data: np.ndarray) -> np.ndarray:
    """BatchedFrames wire format only supports a fixed set of native-byte-order
    dtypes (the wire header records a type name like "uint16" with no
    endianness), so non-native byte order must be normalized before emission
    or receivers will silently misinterpret the bytes."""
    try:
        NumpyDtype(data.dtype.name)
    except ValueError:
        logger.warning(
            f"dtype '{data.dtype}' not supported on the wire; casting to uint32."
        )
        return data.astype(np.uint32)

    if not data.dtype.isnative:
        logger.warning(f"Byte-swapping non-native dtype '{data.dtype}' for the wire.")
        return data.astype(data.dtype.newbyteorder("="))

    return data


@operator
def reader(
    inputs: BytesMessage | None, parameters: dict[str, Any], trigger=None
) -> BytesMessage | None:
    """Reads dense TEM data from disk and streams it out as batched dense frames."""
    if trigger is None:
        return None

    global active_emitter, current_scan_number, current_file, cached_array

    file = parameters.get("file")
    batch_size_mb = float(parameters.get("batch_size_mb", 1.0))
    cache_last_file = bool(parameters.get("cache_last_file", False))

    if not file:
        raise ValueError("Parameter 'file' is not set.")

    if file != current_file:
        current_file = file
        active_emitter = None
        if not cache_last_file:
            cached_array = None
        logger.info(f"New file received: {file}. Resetting.")

    if active_emitter is None:
        file_path = data_dir / Path(file)

        data = (
            cached_array[1]
            if cache_last_file and cached_array and cached_array[0] == file
            else None
        )

        if data is None:
            logger.info(f"Loading file: {file_path}")
            dd = ncempy.read(file_path)
            data = dd["data"]
            logger.info(f"file data shape: {data.shape}, dtype: {data.dtype}")
            if cache_last_file:
                cached_array = (file, data)

        data = _coerce_wire_dtype(data)
        scan_shape, frame_shape = _resolve_shapes(data, parameters)

        accumulator = FrameAccumulator.from_dense_array(
            scan_number=current_scan_number,
            scan_shape=scan_shape,
            frame_shape=frame_shape,
            data=data,
        )

        active_emitter = BatchEmitter(
            accumulator, scan_number=current_scan_number, batch_size_mb=batch_size_mb
        )
        logger.info(
            f"Emitter created for Scan {current_scan_number}. "
            f"Scan Shape: {scan_shape}, Frame Shape: {frame_shape}, "
            f"Total Frames: {active_emitter.total_frames}. "
            f"Batch size: {batch_size_mb} MB."
        )

    try:
        return active_emitter.get_next_batch_message()
    except StopIteration:
        logger.info(
            f"Finished sending all {active_emitter.total_frames} frames "
            f"for Scan Number: {current_scan_number} (Emitter exhausted)."
        )
        current_scan_number += 1
        active_emitter = None
        return None
