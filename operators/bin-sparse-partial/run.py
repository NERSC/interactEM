from typing import Any

from distiller_streaming.bin import bin_frames_simple
from distiller_streaming.models import BatchedFrames, COMPartial

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator

logger = get_logger()

@operator
def bin_partial(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    if not inputs:
        logger.warning("No input provided to the bin operator.")
        return None

    # center = None
    # init_center_x = parameters.get("init_center_x")
    # init_center_y = parameters.get("init_center_y")
    # if init_center_x is not None and init_center_y is not None:
    #     center = (init_center_x, init_center_y)

    # crop = None
    # crop_to_x = parameters.get("crop_to_x")
    # crop_to_y = parameters.get("crop_to_y")
    # if crop_to_x is not None and crop_to_y is not None:
    #     crop = (crop_to_x, crop_to_y)
    
    bin_value = None
    bin_param = parameters.get("bin_value")
    if bin_param is not None:
        bin_value = bin_param
    
    batch = BatchedFrames.from_bytes_message(inputs)
    #binned_frames = bin_sparse(batch, bin_value)
    
    # Ravel the data for easier manipulation in this function
    scan_shape = batch.header.scan_shape
    frame_shape = batch.header.frame_shape
    all_events_concat, position_indices = batch.get_frame_arrays_with_positions()
    scan_positions = position_indices

    data = all_events_concat

    rows = data // frame_shape[0] // bin_factor
    cols = data % frame_shape[1] // bin_factor

    rows *= (frame_shape[0] // bin_factor)
    rows += cols
    
    batch.header.frame_shape = [ii//bin_value for ii in batch.header.frame_shape]

    return COMPartial(header=batch.header, array=rows).to_bytes_message()

def profile_bin_partial():
    NUM_ITERS = 20
    inputs = BatchedFrames.create_synthetic_batch(
        scan_size=128,
        frame_shape=(576, 576),
        frames_per_position=2,
        events_per_frame=10,
    ).to_bytes_message()
    
    scan_shape = batch.header.scan_shape

    #for ii in range(NUM_ITERS):
    #    logger.info(f"iter {ii + 1} / {NUM_ITERS}")
    #    logger.info(f"Data size (MB): {len(inputs.data) / 1024 / 1024:.1f}")
    #    parameters = {
    #        "bin_value": 2,
    #    }

    #    ret = bin_partial(inputs, parameters)
    #    if not ret:
    #        continue
    #    ret.header.model_copy()
    #    ret.header.model_dump_json().encode()


if __name__ == "__main__":
    profile_bin_partial()
