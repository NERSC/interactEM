import asyncio
from pathlib import Path

import ncempy
import numpy as np
import stempy.io as stio
from numpy.linalg import svd
from pydantic import BaseModel, ValidationError
from scipy import ndimage
from stempy.contrib import FileSuffix, get_scan_path

from core.logger import get_logger
from core.models.messages import BytesMessage
from operators.operator import operator

logger = get_logger("vacuum_scan_subtract", "DEBUG")


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
    assert (
        points.shape[0] <= points.shape[1]
    ), f"There are only {points.shape[1]} points in {points.shape[0]} dimensions."
    ctr = points.mean(axis=1)
    x = points - ctr[:, np.newaxis]
    M = np.dot(x, x.T)  # Could also use np.cov(x) here.
    return ctr, svd(M)[0][:, -1]


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


# Params:
keep_flyback: bool = False

# Load the offsets for the vacuum scan subtraction
vacuum_scan_id = 20132
vacuum_scan_num = 714
distiller_path = Path("/vacuum_scan")

offsets_path, vacuum_scan_num, vacuum_scan_id = get_scan_path(
    distiller_path,
    scan_num=vacuum_scan_num,
    scan_id=vacuum_scan_id,
    version=1,
    file_suffix=FileSuffix.OFFSETS,
)

offsets_data = ncempy.read(offsets_path)["data"]

current_scan_num = -1
current_camera_length = -1
current_stem_magnification = "50x"

factor = (
    0 / offsets_data.shape[1],
    0 / offsets_data.shape[2],
)

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

print(f"plane fit to COM0: {planeCOM0}")
print(f"plane fit to COM1: {planeCOM1}")


def generate_shifts(scan_shape, com2_filt, planeCOM0, planeCOM1, method):
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


@operator
def subtract(inputs: BytesMessage | None) -> BytesMessage | None:
    global \
        current_scan_num, \
        current_camera_length, \
        current_stem_magnification, \
        offsets_data, \
        factor, \
        planeCOM0, \
        planeCOM1, \
        row_shifts, \
        column_shifts

    if not inputs:
        logger.warning("No input provided to the subtract operator.")
        return None

    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError as e:
        logger.error(f"Invalid message: {e}")
        return None

    scan_shape = (header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1)
    frame_shape = (576, 576)
    scan_num = header.scan_number

    if scan_num != current_scan_num:
        logger.info(
            f"New scan detected. Previous scan: {current_scan_num}, Current scan: {scan_num}"
        )

        method = "interp"
        logger.info(f"Generating shifts using method: {method}")

        row_shifts, column_shifts = generate_shifts(
            scan_shape, offsets_data, planeCOM0, planeCOM1, method
        )
        logger.debug("Shifts generated for new scan...")

        current_scan_num = scan_num

    sparse_frame = np.frombuffer(inputs.data, dtype=np.uint32)
    position = (header.STEM_row_in_scan, header.STEM_x_position_in_row)
    row_idx, col_idx = position
    row_shift = row_shifts[row_idx, col_idx]  # type: ignore
    column_shift = column_shifts[row_idx, col_idx]  # type: ignore

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

    centered = np.empty((1, 1), dtype=object)
    centered[0, 0] = np.ravel_multi_index(
        (ev_columns_centered, ev_rows_centered), frame_shape
    )
    experiment_centered = stio.SparseArray(centered, (1, 1), frame_shape)
    return BytesMessage(
        header=inputs.header,
        data=experiment_centered.data[0][0].astype(np.uint32).tobytes(),
    )


async def async_main():
    op = subtract()
    await op.start()


def main():
    # Run the async main function using asyncio.run
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


if __name__ == "__main__":
    main()
