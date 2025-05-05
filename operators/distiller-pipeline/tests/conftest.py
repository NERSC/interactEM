import numpy as np
import pytest

from distiller_pipeline import FrameAccumulator, FrameHeader


@pytest.fixture
def frame_accumulator():
    return FrameAccumulator(scan_number=1, scan_shape=(10, 10), frame_shape=(128, 128))

@pytest.fixture
def sample_frame_header():
    return FrameHeader(
        scan_number=1,
        frame_number=0,
        nSTEM_positions_per_row_m1=10,
        nSTEM_rows_m1=10,
        STEM_x_position_in_row=5,
        STEM_row_in_scan=3,
        modules=[0],
        frame_shape=(128, 128)
    )

@pytest.fixture
def sample_frame_data():
    return np.random.randint(0, 128*128, size=50, dtype=np.uint32)

@pytest.fixture
def populated_frame_accumulator(
    frame_accumulator, sample_frame_header, sample_frame_data
):
    header1 = sample_frame_header.model_copy()
    frame_accumulator.add_frame(header1, sample_frame_data.copy())
    header2 = sample_frame_header.model_copy()
    header2.STEM_x_position_in_row = 0
    header2.STEM_row_in_scan = 0
    frame_accumulator.add_frame(header2, sample_frame_data.copy() + 1)
    header3 = sample_frame_header.model_copy()
    frame_accumulator.add_frame(header3, sample_frame_data.copy() + 2)
    return frame_accumulator
