import numpy as np
import pytest
from stempy.io import SparseArray

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrameHeader, FrameHeader
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject


@pytest.fixture
def sparse_array():
    scan_shape, frame_shape = (5, 5), (128, 128)
    num_scans, frames_per_scan = 25, 2
    data = np.empty((num_scans, frames_per_scan), dtype=object)
    for i in range(num_scans):
        for j in range(frames_per_scan):
            data[i, j] = np.array([i * 100 + j * 10 + k for k in range(5)], np.uint32)
    return SparseArray(
        data=data,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        dtype=np.uint32,
        sparse_slicing=True,
        allow_full_expand=False,
        metadata={"modules": [0, 1, 2, 3]},
    )


def emit_all(emitter):
    messages = []
    try:
        while True:
            messages.append(emitter.get_next_frame_message())
    except StopIteration:
        return messages


@pytest.fixture
def frame_accumulator() -> FrameAccumulator:
    return FrameAccumulator(scan_number=1, scan_shape=(10, 10), frame_shape=(128, 128))


@pytest.fixture
def sample_frame_header() -> FrameHeader:
    return FrameHeader(
        scan_number=1,
        frame_number=0,
        nSTEM_positions_per_row_m1=10,
        nSTEM_rows_m1=10,
        STEM_x_position_in_row=5,
        STEM_row_in_scan=3,
        modules=[0],
        frame_shape=(128, 128),
        data_size_bytes=200,
    )


@pytest.fixture
def sample_frame_data() -> np.ndarray:
    return np.random.randint(0, 128 * 128, size=50, dtype=np.uint32)


@pytest.fixture
def populated_frame_accumulator(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data: np.ndarray,
) -> FrameAccumulator:
    header1 = sample_frame_header.model_copy()
    header1.data_size_bytes = len(sample_frame_data.tobytes())
    frame_accumulator.add_frame(header1, sample_frame_data.copy())

    header2 = sample_frame_header.model_copy()
    header2.STEM_x_position_in_row = 0
    header2.STEM_row_in_scan = 0
    data2 = sample_frame_data.copy() + 1
    header2.data_size_bytes = len(data2.tobytes())
    frame_accumulator.add_frame(header2, data2)

    header3 = sample_frame_header.model_copy()
    data3 = sample_frame_data.copy() + 2
    header3.data_size_bytes = len(data3.tobytes())
    frame_accumulator.add_frame(header3, data3)

    return frame_accumulator


@pytest.fixture
def batched_message_factory():
    """Factory to create a batched BytesMessage from headers and data arrays."""

    def _factory(
        headers: list[FrameHeader], data_arrays: list[np.ndarray]
    ) -> BytesMessage:
        combined_data = b"".join(arr.tobytes() for arr in data_arrays)
        batched_header = BatchedFrameHeader(
            scan_number=headers[0].scan_number,
            headers=headers,
            total_batch_size_bytes=len(combined_data),
        )
        return BytesMessage(
            header=MessageHeader(
                subject=MessageSubject.BYTES, meta=batched_header.model_dump()
            ),
            data=combined_data,
        )

    return _factory


