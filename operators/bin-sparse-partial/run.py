from typing import Any

#from distiller_streaming.bin import bin_frames_simple
from distiller_streaming.models import BatchedFrames, BatchedFrameHeader

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

    bin_value = None
    bin_param = parameters.get("bin_value")
    if bin_param is not None:
        bin_value = bin_param
    
    # Get the batch of frames from the input
    batch = BatchedFrames.from_bytes_message(inputs)
    
    # Extract necessary metadata from the header
    scan_shape = batch.header.scan_shape
    frame_shape = batch.header.frame_shape

    # Get the sparse frames
    data, position_indices = batch.get_frame_arrays_with_positions()
    #scan_positions = position_indices
    
    # Convert each event into the location on the reduced frame size (binning)
    rows = data // frame_shape[0] // bin_value # row location of event
    cols = data % frame_shape[1] // bin_value # column location of event
    # Convert to raveled location
    rows *= (frame_shape[0] // bin_value)
    rows += cols
    
    # Update all frame header frame_size values
    new_headers = batch.header.headers
    for ii in range(len(new_headers)):
        new_headers[ii].frame_shape = (new_headers[ii].frame_shape[0] // bin_value, new_headers[ii].frame_shape[1] // bin_value)
    new_batch_header = BatchedFrameHeader(
            scan_number=batch.header.scan_number,
            headers=new_headers,
            batch_size_bytes=batch.header.batch_size_bytes,
            total_frames=batch.header.total_frames)
    out = BatchedFrames.from_np_arrays(new_batch_header, rows)
    return out.to_bytes_message()

