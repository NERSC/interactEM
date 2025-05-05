import io
from typing import Any

import matplotlib.cm as cm
import numpy as np
from PIL import Image, ImageEnhance
from pydantic import BaseModel

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()


class InputMeta(BaseModel):
    shape: tuple[int, int]
    dtype: str
    source_operator: str | None = None


@operator
def array_image_converter(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """
    Converts numpy array data into a
    displayable image format (JPEG/PNG) with normalization and colormapping.
    """
    if not inputs:
        return None

    brightness = float(parameters.get("brightness", 1.0))
    contrast = float(parameters.get("contrast", 1.0))
    colormap_name = parameters.get("colormap", "viridis")
    image_format = parameters.get("image_format", "PNG").upper()
    percentile_min = float(parameters.get("percentile_min", 0.5))
    percentile_max = float(parameters.get("percentile_max", 99.5))

    if image_format not in ["JPEG", "PNG"]:
        raise ValueError(
            f"Unsupported image format: {image_format}. Supported formats are JPEG and PNG."
        )

    meta = InputMeta(**inputs.header.meta)
    original_dtype = np.dtype(meta.dtype)
    image = np.frombuffer(inputs.data, dtype=original_dtype).reshape(meta.shape)

    # Normalize using percentile clipping to handle outliers
    min_val = np.percentile(image, percentile_min)
    max_val = np.percentile(image, percentile_max)
    denominator = max_val - min_val
    normalized_pattern = np.clip((image - min_val) / denominator, 0.0, 1.0).astype(np.float32)

    colormap = cm.get_cmap(colormap_name)
    colored_image_data = colormap(normalized_pattern)

    # Convert to 8-bit RGB
    rgb_image_data = (colored_image_data[:, :, :3] * 255).astype(np.uint8)

    image = Image.fromarray(rgb_image_data, mode="RGB")

    if contrast != 1.0:
        contrast_enhancer = ImageEnhance.Contrast(image)
        image = contrast_enhancer.enhance(contrast)

    if brightness != 1.0:
        brightness_enhancer = ImageEnhance.Brightness(image)
        image = brightness_enhancer.enhance(brightness)

    byte_array = io.BytesIO()
    image.save(byte_array, format=image_format)
    image_bytes = byte_array.getvalue()

    output_message = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES
        ),
        data=image_bytes,
    )

    return output_message
