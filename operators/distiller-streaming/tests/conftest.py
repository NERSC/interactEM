import msgspec.structs
import numpy as np
import pytest
from stempy.io import SparseArray

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import Frame, FrameHeader


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
    header1 = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )
    frame1 = Frame(header=header1, buffer=sample_frame_data.tobytes())
    frame_accumulator.add_frame(frame1)

    header2 = msgspec.structs.replace(
        sample_frame_header,
        STEM_x_position_in_row=0,
        STEM_row_in_scan=0,
        data_size_bytes=len(sample_frame_data.tobytes()),
    )
    # Ensure we don't exceed the valid index range (0 to 16383)
    data2 = np.clip(sample_frame_data.copy() + 1, 0, 128 * 128 - 1)
    header2 = msgspec.structs.replace(header2, data_size_bytes=len(data2.tobytes()))
    frame2 = Frame(header=header2, buffer=data2.tobytes())
    frame_accumulator.add_frame(frame2)

    header3 = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )
    # Ensure we don't exceed the valid index range (0 to 16383)
    data3 = np.clip(sample_frame_data.copy() + 2, 0, 128 * 128 - 1)
    header3 = msgspec.structs.replace(header3, data_size_bytes=len(data3.tobytes()))
    frame3 = Frame(header=header3, buffer=data3.tobytes())
    frame_accumulator.add_frame(frame3)

    return frame_accumulator
