import shutil
from pathlib import Path
from typing import Any

import msgspec
import ncempy
import numpy as np
from distiller_streaming.models import BatchedFrames, Frame
from numpy.linalg import svd
from pydantic import ValidationError
from scipy import ndimage

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()


def planeFit(points):
    """
    p, n = planeFit(points)

    Given an array, points, of shape (d,...)
    representing points in d-dimensional space,
    fit an d-dimensional plane to the points.
    Return a point, p, on the plane (the point-cloud centroid),
    and the normal, n.

    """

    points = np.reshape(
        points, (np.shape(points)[0], -1)
    )  # Collapse trialing dimensions
    assert points.shape[0] <= points.shape[1], (
        f"There are only {points.shape[1]} points in {points.shape[0]} dimensions."
    )
    ctr = points.mean(axis=1)
    x = points - ctr[:, np.newaxis]
    M = np.dot(x, x.T)  # Could also use np.cov(x) here.
    return ctr, svd(M)[0][:, -1]


# Params:
keep_flyback: bool = False

# Load the offsets for the vacuum scan subtraction
offsets_path = Path(f"{DATA_DIRECTORY}/offsets.emd")
# Copy to local storage to avoid HDF5 file locking issues...
local_path = "/tmp/offsets.emd"
shutil.copy(offsets_path, local_path)
offsets_data = ncempy.read(local_path)["data"]

current_scan_num = -1

factor = (
    0 / offsets_data.shape[1],
    0 / offsets_data.shape[2],
)

# Dictionary to store shifts for each scan number
scan_shifts_cache = {}

row_shifts = None
column_shifts = None


# Interpolate to fit the vacuum scan_shape
# This is not exactly necessary, but tests the use of interpolation for later

YY, XX = np.mgrid[0 : offsets_data.shape[1], 0 : offsets_data.shape[2]]

# Interpolation
com2_fit = np.zeros((2, *XX.shape))
com2_fit[0, :, :] = ndimage.map_coordinates(
    offsets_data[0, :, :], (YY.ravel(), XX.ravel()), mode="nearest"
).reshape(XX.shape)
com2_fit[1, :, :] = ndimage.map_coordinates(
    offsets_data[1, :, :], (YY.ravel(), XX.ravel()), mode="nearest"
).reshape(XX.shape)

com2_filt_median = np.median(offsets_data, axis=(1, 2))

# Fit to a plane
planeCOM0 = planeFit(np.stack((YY, XX, offsets_data[0,] - com2_filt_median[0])))
planeCOM1 = planeFit(np.stack((YY, XX, offsets_data[1,] - com2_filt_median[1])))


def generate_shifts(scan_shape, com2_filt, planeCOM0, planeCOM1, method):
    global com2_filt_median

    n_rows, n_cols = scan_shape
    factor = (
        n_rows / offsets_data.shape[2],
        n_cols / offsets_data.shape[1],
    )
    factor_n_rows, factor_n_cols = factor
    logger.debug(f"Factor calculated: {factor}")
    rr, cc = np.mgrid[0:n_rows, 0:n_cols]
    rr = rr.astype("<f4") / factor_n_rows
    cc = cc.astype("<f4") / factor_n_cols

    if method == "interp":
        com2_fit = np.zeros((2, *cc.shape))
        com2_fit[0, :, :] = ndimage.map_coordinates(
            com2_filt[0, :, :], (rr.ravel(), cc.ravel()), mode="nearest"
        ).reshape(cc.shape)
        com2_fit[1, :, :] = ndimage.map_coordinates(
            com2_filt[1, :, :], (rr.ravel(), cc.ravel()), mode="nearest"
        ).reshape(cc.shape)

        z0 = com2_fit[0, :, :]
        z1 = com2_fit[1, :, :]
    elif method == "plane":
        normal = planeCOM0[1]
        d = np.dot(-planeCOM0[0], normal)
        # calculate corresponding z
        z0 = (-normal[0] * rr - normal[1] * cc - d) / normal[2]

        normal = planeCOM1[1]
        d = np.dot(-planeCOM1[0], normal)
        # calculate corresponding z
        z1 = (-normal[0] * rr - normal[1] * cc - d) / normal[2]
    else:
        print("unknown method. Choose interp or plane.")

    # Round to integers
    shift_axis0 = np.round(z0 - z0.mean()).astype(np.int64)
    shift_axis1 = np.round(z1 - z1.mean()).astype(np.int64)
    return shift_axis0, shift_axis1


def _subtract_one(frame: Frame) -> Frame:
    global row_shifts, column_shifts
    header = frame.header
    sparse_frame = frame.array
    frame_shape = header.frame_shape
    position = (header.STEM_row_in_scan, header.STEM_x_position_in_row)
    row_idx, col_idx = position
    row_shift = row_shifts[row_idx, col_idx]
    column_shift = column_shifts[row_idx, col_idx]

    ev_columns, ev_rows = np.unravel_index(sparse_frame, frame_shape)
    ev_rows_centered = ev_rows - row_shift
    ev_columns_centered = ev_columns - column_shift

    keep = (
        (ev_rows_centered < frame_shape[0])
        & (ev_rows_centered >= 0)
        & (ev_columns_centered < frame_shape[1])
        & (ev_columns_centered >= 0)
    )

    ev_rows_centered = ev_rows_centered[keep]
    ev_columns_centered = ev_columns_centered[keep]

    centered_indices = np.ravel_multi_index(
        (ev_columns_centered, ev_rows_centered), frame_shape
    ).astype(np.uint32)

    data = centered_indices.tobytes()

    new_header = msgspec.structs.replace(header, data_size_bytes=len(data))
    return Frame(header=new_header, buffer=data)

@operator
def subtract(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global current_scan_num, row_shifts, column_shifts, scan_shifts_cache

    if not inputs:
        logger.warning("No input provided to the subtract operator.")
        return None

    try:
        batch = BatchedFrames.from_bytes_message(inputs)
    except ValidationError as e:
        logger.error(f"Invalid message: {e}")
        return None

    header = batch.header

    scan_num = header.scan_number
    # Check if we have shifts cached for this scan number
    if scan_num not in scan_shifts_cache:
        method = parameters.get("method", "interp")
        if method not in ["interp", "plane"]:
            method = "interp"

        logger.info(f"Generating shifts using method: {method}")
        scan_shape = header.scan_shape

        row_shifts, column_shifts = generate_shifts(
            scan_shape, offsets_data, planeCOM0, planeCOM1, method
        )

        # Cache the shifts for this scan number
        scan_shifts_cache[scan_num] = (row_shifts, column_shifts)
        logger.debug(f"Shifts generated and cached for scan {scan_num}")
    else:
        # Use cached shifts
        row_shifts, column_shifts = scan_shifts_cache[scan_num]
        logger.debug(f"Using cached shifts for scan {scan_num}")

    # beam compensation per frame
    compensated = [_subtract_one(frame) for frame in batch.iter_frames()]
    return BatchedFrames.from_frames(compensated).to_bytes_message()
