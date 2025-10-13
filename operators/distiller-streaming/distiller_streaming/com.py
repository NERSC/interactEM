from stempy.image import com_v1_kernel

from distiller_streaming.models import BatchedFrames


def com_sparse(
    batch: BatchedFrames,
    crop_to: tuple[int, int] | None = None,
    init_center: tuple[int, int] | None = None,
    replace_nans: bool = True,
):
    scan_shape = batch.header.scan_shape
    frame_shape = batch.header.frame_shape
    all_events_concat, position_indices = batch.get_frame_arrays_with_positions()

    return com_v1_kernel(
        all_events_concat,
        position_indices,
        scan_shape,
        frame_shape,
        crop_to,
        init_center,
        replace_nans,
    )
