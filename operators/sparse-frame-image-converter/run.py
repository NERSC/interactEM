import io
from typing import Any

import matplotlib.cm as cm
import numpy as np
from distiller_streaming.models import FrameHeader
from PIL import Image, ImageEnhance
from pydantic import ValidationError

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()


skip_counter = 0
average_counter = 0
accumulated_dense = None


@operator
def image_converter(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global skip_counter, average_counter, accumulated_dense

    average = int(parameters.get("average", 100))
    skip = int(parameters.get("skip", 1))
    brightness = float(parameters.get("brightness", 1.0))
    contrast = float(parameters.get("contrast", 1.0))
    operation = parameters.get("operation", "sum").lower()
    colormap = parameters.get("colormap", "viridis")

    if not inputs:
        return None

    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError:
        logger.error("Invalid message")
        return None

    frame_shape = header.frame_shape
    data = np.frombuffer(inputs.data, dtype=np.uint32)
    y_indices, x_indices = np.unravel_index(data, frame_shape)

    # Create a 2D array and accumulate counts directly
    dense = np.zeros(frame_shape, dtype=np.uint32)
    np.add.at(dense, (y_indices, x_indices), 1)

    # Initialize the accumulator if necessary
    if average_counter == 0 or accumulated_dense is None:
        accumulated_dense = np.zeros_like(dense)

    # Accumulate frames
    accumulated_dense += dense
    average_counter += 1

    # Check if we've accumulated enough frames
    if average_counter < average:
        return None  # Wait until we've accumulated 'average' frames

    # Now, depending on the operation, compute the processed data
    if operation == "average":
        processed_dense = accumulated_dense / average
    elif operation == "sum":
        processed_dense = accumulated_dense
    else:
        logger.error(f"Invalid operation '{operation}'. Must be 'average' or 'sum'.")
        # Reset accumulators for the next set
        average_counter = 0
        accumulated_dense = None
        return None

    # Apply skip logic
    skip_counter += 1
    if skip_counter % skip != 0:
        # Reset accumulators for the next set
        average_counter = 0
        accumulated_dense = None
        return None

    # Proceed to process the processed data
    # Normalize the processed_dense to range [0, 1]
    if processed_dense.max() > 0:
        dense_normalized = processed_dense / processed_dense.max()
    else:
        dense_normalized = processed_dense

    # Apply viridis colormap
    colormap = cm.get_cmap(colormap)
    colored_image = colormap(dense_normalized)

    # Convert to 8-bit RGB
    colored_image = (colored_image[:, :, :3] * 255).astype(np.uint8)

    # Create an RGB image
    image = Image.fromarray(colored_image, mode="RGB")

    # Apply contrast adjustment
    contrast_enhancer = ImageEnhance.Contrast(image)
    image = contrast_enhancer.enhance(contrast)

    # Apply brightness adjustment
    brightness_enhancer = ImageEnhance.Brightness(image)
    image = brightness_enhancer.enhance(brightness)

    # Save the image to a bytes buffer
    byte_array = io.BytesIO()
    image.save(byte_array, format="JPEG")
    byte_array.seek(0)
    header = MessageHeader(subject=MessageSubject.BYTES, meta={})

    # Reset accumulators for the next set
    average_counter = 0
    accumulated_dense = None

    return BytesMessage(header=header, data=byte_array.getvalue())
