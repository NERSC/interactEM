import io
import time
from typing import Any

import numpy as np
from PIL import Image

from core.logger import get_logger
from core.models.messages import BytesMessage, MessageHeader, MessageSubject
from operators.operator import operator

logger = get_logger()


@operator
def random_image(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    width = int(parameters.get("width", 100))
    height = int(parameters.get("height", 100))
    interval = int(parameters.get("interval", 2))

    time.sleep(interval)

    random_data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    image = Image.fromarray(random_data, "RGB")
    byte_array = io.BytesIO()
    image.save(byte_array, format="JPEG")
    byte_array.seek(0)
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})

    return BytesMessage(header=header, data=byte_array.getvalue())
