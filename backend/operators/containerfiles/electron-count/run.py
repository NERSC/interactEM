import asyncio

import numpy as np
import stempy.image as stim
from scipy.ndimage import maximum_filter

from core.logger import get_logger
from operators.messengers.base import BytesMessage, MessageHeader, MessageSubject
from operators.operator import operator

logger = get_logger("operator_main", "DEBUG")


@operator
def count_image(inputs: BytesMessage | None) -> BytesMessage:
    if inputs:
        arr = np.frombuffer(inputs.data, dtype=np.uint16).reshape(100, 100)
        logger.info(f"Received image: {arr[45:55, 45:55]}")
        max_filter = maximum_filter(arr, size=3, mode="constant")
        # Compare the original array with the filtered array
        local_maxima = arr == max_filter

        # Remove the border effects by setting the border to False
        local_maxima[:1, :] = False
        local_maxima[-1:, :] = False
        local_maxima[:, :1] = False
        local_maxima[:, -1:] = False
        local_maxima = local_maxima.astype(np.uint16)
        print(f"Local maxima: {local_maxima[45:55, 45:55]}")
        sparse_array = stim.electron_count_frame(arr)
        print(f"Stempy counted: {sparse_array.to_dense()[0][0][45:55, 45:55]}")
        print(
            f"Are they the same? {np.allclose(local_maxima[45:55, 45:55], sparse_array.to_dense()[0][0][45:55, 45:55])}"
        )

    header = MessageHeader(subject=MessageSubject.BYTES, meta={})
    return BytesMessage(
        header=header, data=sparse_array.data.tobytes()
    ) or BytesMessage(header=header, data=b"No input provided")


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
