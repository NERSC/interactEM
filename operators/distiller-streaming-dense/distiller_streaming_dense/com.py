import numpy as np
from stempy.image import com_dense

from distiller_streaming_dense.models import BatchedFrames


def com_dense_batch(
    batch: BatchedFrames,
    crop_to: int | None = None,
    init_center: tuple[int, int] | None = None,
    replace_nans: bool = True,
) -> np.ndarray:
    """Compute per-scan-position center of mass for a batch of dense frames.

    Mirrors the sparse package's com_sparse() output contract: a (2, *scan_shape)
    array, row 0 = y center of mass, row 1 = x center of mass, NaN where no
    frame was received for that position (unless replace_nans).
    """
    scan_shape = batch.header.scan_shape
    frame_shape = batch.header.frame_shape
    num_scans = scan_shape[0] * scan_shape[1]

    frames, position_indices = batch.get_frame_stack_with_positions()

    com = np.full((2, num_scans), np.nan, dtype=np.float32)

    if len(frames) == 0:
        return com.reshape((2, *scan_shape))

    if crop_to is not None:
        if init_center is not None:
            cx, cy = init_center
        else:
            # Use the global summed frame's COM as the crop center.
            cx_f, cy_f = com_dense(frames.sum(axis=0))[:, 0]
            cx, cy = float(cx_f), float(cy_f)

        YY, XX = np.mgrid[0 : frame_shape[0], 0 : frame_shape[1]]
        r = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
        crop_mask = r <= crop_to
        frames = frames * crop_mask[None, :, :]

    frame_com = com_dense(frames)  # shape (2, num_frames): (x, y) per frame

    com[1, position_indices] = frame_com[0]
    com[0, position_indices] = frame_com[1]

    com = com.reshape((2, *scan_shape))

    if replace_nans:
        for i in range(2):
            nans = np.isnan(com[i])
            if nans.any():
                com[i, nans] = np.nanmean(com[i])

    return com
