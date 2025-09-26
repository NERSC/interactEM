from typing import Any

from distiller_streaming.com import com_sparse
from distiller_streaming.models import BatchedFrames, COMPartial

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator

logger = get_logger()

@operator
def com_partial(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    if not inputs:
        logger.warning("No input provided to the subtract operator.")
        return None

    center = None
    init_center_x = parameters.get("init_center_x")
    init_center_y = parameters.get("init_center_y")
    if init_center_x is not None and init_center_y is not None:
        center = (init_center_x, init_center_y)

    crop = None
    crop_to_x = parameters.get("crop_to_x")
    crop_to_y = parameters.get("crop_to_y")
    if crop_to_x is not None and crop_to_y is not None:
        crop = (crop_to_x, crop_to_y)

    batch = BatchedFrames.from_bytes_message(inputs)
    com = com_sparse(batch, init_center=center, crop_to=crop, replace_nans=False)

    return COMPartial(header=batch.header, array=com).to_bytes_message()


def profile_com_partial():
    NUM_ITERS = 20
    inputs = BatchedFrames.create_synthetic_batch(
        scan_size=128,
        frame_shape=(576, 576),
        frames_per_position=2,
        events_per_frame=10,
    ).to_bytes_message()
    for i in range(NUM_ITERS):
        logger.info(f"iter {i + 1} / {NUM_ITERS}")
        logger.info(f"Data size (MB): {len(inputs.data) / 1024 / 1024:.1f}")
        parameters = {
            "init_center_x": 255,
            "init_center_y": 255,
            "crop_to_x": 128,
            "crop_to_y": 128,
        }

        ret = com_partial(inputs, parameters)
        if not ret:
            continue
        ret.header.model_copy()
        ret.header.model_dump_json().encode()


if __name__ == "__main__":
    profile_com_partial()
