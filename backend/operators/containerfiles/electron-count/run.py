import asyncio

import numpy as np
import stempy.image as stim
from pydantic import BaseModel, ValidationError

from core.logger import get_logger
from core.models.messages import BytesMessage, MessageHeader, MessageSubject
from operators.operator import operator

logger = get_logger("operator_main", "DEBUG")


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


first_time = True


@operator
def count_image(inputs: BytesMessage | None) -> BytesMessage | None:
    global first_time
    if not inputs:
        return None

    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError:
        logger.error("Invalid message")
        return None
    arr = np.frombuffer(inputs.data, dtype=np.uint16).reshape(576, 576)
    sparse_array = stim.electron_count_frame(arr, background_threshold=28.6217068096665)
    header = MessageHeader(subject=MessageSubject.BYTES, meta=header.model_dump())
    if first_time:
        print(sparse_array.dtype)
        print(sparse_array.data)
        first_time = False
    return BytesMessage(header=header, data=sparse_array.data[0][0].tobytes())


async def async_main():
    op = count_image()
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
