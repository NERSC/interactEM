from typing import Any

#from distiller_streaming.bin import bin_frames_simple
from distiller_streaming.models import BatchedFrameHeader, BatchedFrames

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

    bin_value = parameters.get("bin_value", 1)

    # Get the batch of frames from the input
    batch = BatchedFrames.from_bytes_message(inputs)

    # Extract necessary metadata from the header
    frame_shape = batch.header.frame_shape

    # Calculate the new frame shape after binning
    new_frame_shape = (frame_shape[0] // bin_value, frame_shape[1] // bin_value)

    # Get the sparse frames
    data, _ = batch.get_frame_arrays_with_positions()

    # Convert each event into the location on the reduced frame size (binning)
    rows = data // frame_shape[0] // bin_value # row location of event
    cols = data % frame_shape[1] // bin_value # column location of event
    # Convert to raveled location
    rows *= (frame_shape[0] // bin_value)
    rows += cols

    # Update all frame header frame_shape values and create a new batch with the binned data
    for header in batch.header.headers:
        header.frame_shape = new_frame_shape
    out = BatchedFrames.from_np_arrays(batch.header, rows)
    return out.to_bytes_message()
