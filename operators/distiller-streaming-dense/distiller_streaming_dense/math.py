"""Pure-numpy math utilities, vendored from stempy.image so this package has
no runtime dependency on stempy.

Vendored from stempy/python/stempy/image/__init__.py:
- com_v1_kernel: center-of-mass from sparse (flat hit-index) event data.
  Kept for API completeness; this package's dense pipeline instead uses
  com_dense directly (see com.py).
- com_dense: center-of-mass from dense 2D/3D frame(s).
- phase_from_com: DPC phase integration from a center-of-mass field.
"""

import numpy as np


def com_v1_kernel(
    all_events_concat: np.ndarray,
    position_indices: np.ndarray,
    scan_shape: tuple[int, int],
    frame_shape: tuple[int, int],
    crop_to: int | None = None,
    init_center: tuple[int, int] | None = None,
    replace_nans: bool = True,
) -> np.ndarray:
    """Compute per-scan-position center of mass from flat hit-index event data.

    :param all_events_concat: flat pixel indices (row-major into frame_shape)
        for every electron hit, concatenated across all scan positions.
    :param position_indices: parallel array giving the flat scan-position
        index each hit in all_events_concat belongs to.
    """
    num_scans = scan_shape[0] * scan_shape[1]
    frame_x, frame_y = frame_shape

    com = np.full((2, num_scans), np.nan, dtype=np.float32)

    if len(all_events_concat) == 0:
        return com.reshape((2, *scan_shape))

    # Decode coordinates
    if frame_x & (frame_x - 1) == 0:  # power of 2
        shift = int(np.log2(frame_x))
        x = (all_events_concat >> shift).astype(np.float32)
    else:
        x = (all_events_concat // frame_x).astype(np.float32)

    if frame_y & (frame_y - 1) == 0:
        mask = frame_y - 1
        y = (all_events_concat & mask).astype(np.float32)
    else:
        y = (all_events_concat % frame_y).astype(np.float32)

    # Cropping
    if crop_to is not None:
        if init_center is not None:
            r = np.sqrt((x - init_center[0]) ** 2 + (y - init_center[1]) ** 2)
            mask = r <= crop_to
            position_indices = position_indices[mask]
            x = x[mask]
            y = y[mask]
        else:
            sum_x_all = np.bincount(position_indices, weights=x, minlength=num_scans)
            sum_y_all = np.bincount(position_indices, weights=y, minlength=num_scans)
            counts_all = np.bincount(position_indices, minlength=num_scans)

            valid_pos = counts_all > 0
            centers_x = np.zeros(num_scans, dtype=np.float32)
            centers_y = np.zeros(num_scans, dtype=np.float32)
            centers_x[valid_pos] = sum_x_all[valid_pos] / counts_all[valid_pos]
            centers_y[valid_pos] = sum_y_all[valid_pos] / counts_all[valid_pos]

            event_center_x = centers_x[position_indices]
            event_center_y = centers_y[position_indices]
            r = np.sqrt((x - event_center_x) ** 2 + (y - event_center_y) ** 2)
            mask = r <= crop_to
            position_indices = position_indices[mask]
            x = x[mask]
            y = y[mask]

    # Final COM calculation
    if len(position_indices) > 0:
        sum_x = np.bincount(position_indices, weights=x, minlength=num_scans)
        sum_y = np.bincount(position_indices, weights=y, minlength=num_scans)
        counts = np.bincount(position_indices, minlength=num_scans)

        valid = counts > 0
        com[0, valid] = sum_y[valid] / counts[valid]
        com[1, valid] = sum_x[valid] / counts[valid]

    com = com.reshape((2, *scan_shape))

    if replace_nans:
        for i in range(2):
            nans = np.isnan(com[i])
            if nans.any():
                com[i, nans] = np.nanmean(com[i])

    return com


def com_dense(frames: np.ndarray) -> np.ndarray:
    """Compute the center of mass for a set of dense 2D frames.

    :param frames: The frames to calculate the center of mass from
    :type frames: numpy.ndarray (2D or 3D)

    :return: The center of mass along each axis of set of frames, shape (2, num_frames)
    :rtype: np.ndarray
    """
    # Make 3D if its only 2D
    if frames.ndim == 2:
        frames = frames[None, :, :]

    YY, XX = np.mgrid[0 : frames.shape[1], 0 : frames.shape[2]]
    com = np.zeros((2, frames.shape[0]), dtype=np.float64)
    for ii, dp in enumerate(frames):
        mm = dp.sum()
        com_x = np.sum(XX * dp)
        com_y = np.sum(YY * dp)
        com[:, ii] = (com_x / mm, com_y / mm)
    return com


def phase_from_com(
    com: np.ndarray, theta: float = 0, flip: bool = False, reg: float = 1e-10
) -> np.ndarray:
    """Integrate 4D-STEM centre of mass (DPC) measurements to calculate
    object phase. Assumes a three dimensional array com, with the final
    two dimensions corresponding to the image and the first dimension
    of the array corresponding to the y and x centre of mass respectively.
    Note this version of the reconstruction is not quantitative.

    Thanks to the py4DSTEM project and author Hamish Brown.

    :param com: The center of mass for each frame as a 3D array of size [2, M, N]
    :type com: numpy.ndarray, 3D
    :param theta: The angle between real space and reciprocal space in radians
    :param flip: Whether to flip the com direction to account for a mirror across the vertical axis.
    :param reg: A regularization parameter

    :return: A 2D ndarray of the DPC phase.
    :rtype: numpy.ndarray
    """
    # Perform rotation and flipping if needed (from py4dstem)
    CoMx = com[0, :, :]
    CoMy = com[1, :, :]
    if flip:
        CoMx_rot = CoMx * np.cos(theta) + CoMy * np.sin(theta)
        CoMy_rot = CoMx * np.sin(theta) - CoMy * np.cos(theta)
    else:
        CoMx_rot = CoMx * np.cos(theta) - CoMy * np.sin(theta)
        CoMy_rot = CoMx * np.sin(theta) + CoMy * np.cos(theta)

    # Get shape of arrays
    ny, nx = com.shape[1:]

    # Calculate Fourier coordinates for array
    ky, kx = (np.fft.fftfreq(x) for x in [ny, nx])

    # Calculate numerator and denominator expressions for solution of
    # phase from centre of mass measurements
    numerator = ky[:, None] * np.fft.fft2(CoMx_rot) + kx[None, :] * np.fft.fft2(
        CoMy_rot
    )
    denominator = 2 * np.pi * 1j * ((kx**2)[None, :] + (ky**2)[:, None]) + reg
    # Avoid a divide by zero for the origin of the Fourier coordinates
    numerator[0, 0] = 0
    denominator[0, 0] = 1

    # Return real part of the inverse Fourier transform
    return np.real(np.fft.ifft2(numerator / denominator))
