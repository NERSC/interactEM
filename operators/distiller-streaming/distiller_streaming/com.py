
import numpy as np

from distiller_streaming.models import BatchedFrames


def com_sparse(
    batch: BatchedFrames,
    crop_to: tuple[int, int] | None = None,
    init_center: tuple[int, int] | None = None,
    replace_nans: bool = True,
):
    scan_shape = batch.header.scan_shape
    frame_shape = batch.header.frame_shape
    num_scans = scan_shape[0] * scan_shape[1]

    # Initialize COM array
    com = np.full((2, num_scans), np.nan, dtype=np.float32)
    frame_x, frame_y = frame_shape

    # Get all events at once
    all_events_concat, position_indices = batch.get_frame_arrays_with_positions()

    if len(all_events_concat) == 0:
        return com.reshape((2, *scan_shape))

    # Decode coordinates - use bit operations when possible
    if frame_x & (frame_x - 1) == 0:  # Power of 2
        shift = int(np.log2(frame_x))
        x = (all_events_concat >> shift).astype(np.float32)
    else:
        x = (all_events_concat // frame_x).astype(np.float32)

    if frame_y & (frame_y - 1) == 0:  # Power of 2
        mask = frame_y - 1
        y = (all_events_concat & mask).astype(np.float32)
    else:
        y = (all_events_concat % frame_y).astype(np.float32)

    # Apply cropping mask if needed
    if crop_to is not None:
        if init_center is not None:
            # Fixed center - simple vectorized masking
            xmin = init_center[0] - crop_to[0]
            xmax = init_center[0] + crop_to[0]
            ymin = init_center[1] - crop_to[1]
            ymax = init_center[1] + crop_to[1]

            mask = (x > xmin) & (x <= xmax) & (y > ymin) & (y <= ymax)

            # Filter everything
            position_indices = position_indices[mask]
            x = x[mask]
            y = y[mask]
        else:
            # Variable center - compute per scan position
            sum_x_all = np.bincount(position_indices, weights=x, minlength=num_scans)
            sum_y_all = np.bincount(position_indices, weights=y, minlength=num_scans)
            counts_all = np.bincount(position_indices, minlength=num_scans)

            # Compute centers for each position
            valid_pos = counts_all > 0
            centers_x = np.zeros(num_scans, dtype=np.float32)
            centers_y = np.zeros(num_scans, dtype=np.float32)
            centers_x[valid_pos] = sum_x_all[valid_pos] / counts_all[valid_pos]
            centers_y[valid_pos] = sum_y_all[valid_pos] / counts_all[valid_pos]

            # Create per-event bounds based on position centers
            event_center_x = centers_x[position_indices]
            event_center_y = centers_y[position_indices]

            # Apply mask based on per-event centers
            mask = (
                (x > event_center_x - crop_to[0])
                & (x <= event_center_x + crop_to[0])
                & (y > event_center_y - crop_to[1])
                & (y <= event_center_y + crop_to[1])
            )

            # Filter
            position_indices = position_indices[mask]
            x = x[mask]
            y = y[mask]

    # Use bincount for final grouped summation
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
