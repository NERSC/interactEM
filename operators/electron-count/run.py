import asyncio
from typing import Any

import numpy as np
import stempy.image as stim
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator
from pydantic import BaseModel, ValidationError

logger = get_logger()


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


@operator
def count_image(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global first_time
    if not inputs:
        return None
    background_threshold = float(parameters.get("background_threshold", 28.0))
    xray_threshold = float(parameters.get("xray_threshold", 2000.0))

    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError:
        logger.error("Invalid message")
        return None
    arr = np.frombuffer(inputs.data, dtype=np.uint16).reshape(576, 576)
    sparse_array = stim.electron_count_frame(
        arr,
        background_threshold=background_threshold,
        xray_threshold=xray_threshold,
    )
    header = MessageHeader(subject=MessageSubject.BYTES, meta=header.model_dump())
    return BytesMessage(header=header, data=sparse_array.data[0][0].tobytes())