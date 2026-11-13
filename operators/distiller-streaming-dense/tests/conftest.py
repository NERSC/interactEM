import msgspec.structs
import numpy as np
import pytest

from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.models import Frame, FrameHeader


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
        data_size_bytes=128 * 128 * 4,
    )


@pytest.fixture
def sample_frame_data() -> np.ndarray:
    frame = np.zeros((128, 128), dtype=np.uint32)
    rng = np.random.default_rng(0)
    xs = rng.integers(0, 128, size=50)
    ys = rng.integers(0, 128, size=50)
    np.add.at(frame, (xs, ys), 1)
    return frame


@pytest.fixture
def frame_array() -> FrameAccumulator:
    """A FrameAccumulator fully populated with dense frames, analogous to the
    sparse package's `sparse_array` fixture."""
    scan_shape, frame_shape = (5, 5), (128, 128)
    accumulator = FrameAccumulator(
        scan_number=42,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        dtype=np.uint32,
        metadata={"modules": [0, 1, 2, 3]},
    )
    num_scans = scan_shape[0] * scan_shape[1]
    data_flat = accumulator.data_flat
    for i in range(num_scans):
        frame = np.zeros(frame_shape, dtype=np.uint32)
        idx = np.array([i * 100 + k for k in range(5)]) % (frame_shape[0] * frame_shape[1])
        rows, cols = np.unravel_index(idx, frame_shape)
        frame[rows, cols] += 1
        data_flat[i] = frame
        accumulator._frames_added.add(i)
    accumulator._num_frames_added = num_scans
    return accumulator


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
    data2 = sample_frame_data.copy() + 1
    frame2 = Frame(header=header2, buffer=data2.tobytes())
    frame_accumulator.add_frame(frame2)

    header3 = msgspec.structs.replace(
        sample_frame_header,
        STEM_x_position_in_row=1,
        STEM_row_in_scan=0,
        data_size_bytes=len(sample_frame_data.tobytes()),
    )
    data3 = sample_frame_data.copy() + 2
    frame3 = Frame(header=header3, buffer=data3.tobytes())
    frame_accumulator.add_frame(frame3)

    return frame_accumulator
