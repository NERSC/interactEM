from unittest.mock import MagicMock

import numpy as np
import pytest
from stempy.io import SparseArray

from distiller_pipeline import FrameAccumulator, FrameEmitter, FrameHeader
from interactem.core.models.messages import BytesMessage


@pytest.fixture
def mock_sparse_array():
    mock_array = MagicMock(spec=SparseArray)
    mock_array.scan_shape = (5, 5)
    mock_array.frame_shape = (128, 128)
    mock_array.num_scans = 25
    data_shape = (25, 2)
    mock_data = np.empty(data_shape, dtype=object)
    for i in range(data_shape[0]):
        for j in range(data_shape[1]):
            mock_data[i, j] = np.array([i*100 + j*10 + k for k in range(5)], dtype=np.uint32)
    mock_array.data = mock_data
    mock_array.data.shape = data_shape
    mock_array.metadata = {"scan_number": 42, "modules": [0, 1, 2, 3]}
    return mock_array

@pytest.fixture
def frame_emitter(mock_sparse_array):
    return FrameEmitter(sparse_array=mock_sparse_array, scan_number=42)

def test_frame_emitter_initialization(frame_emitter, mock_sparse_array):
    assert frame_emitter.scan_number == 42
    assert frame_emitter.total_positions == 25
    assert frame_emitter.frames_per_position == 2
    assert frame_emitter.total_frames == 50
    assert frame_emitter._position_index == 0
    assert frame_emitter._frame_index == 0
    assert frame_emitter._frames_emitted == 0
    assert not frame_emitter._finished
    assert frame_emitter._sparse_array == mock_sparse_array

def test_frame_emitter_invalid_init():
    with pytest.raises(TypeError, match="sparse_array must be a stempy.io.SparseArray"):
        FrameEmitter(sparse_array="not_a_sparse_array", scan_number=1)
    mock_array = MagicMock(spec=SparseArray)
    with pytest.raises(TypeError, match="scan_number must be an integer"):
        FrameEmitter(sparse_array=mock_array, scan_number="1")

def test_create_frame_message(frame_emitter):
    message = frame_emitter._create_frame_message(scan_position_index=3, frame_index=1)
    assert isinstance(message, BytesMessage)
    meta = message.header.meta
    assert isinstance(meta, dict)
    assert meta["scan_number"] == 42
    assert meta["STEM_row_in_scan"] == 0
    assert meta["STEM_x_position_in_row"] == 3
    expected_data = frame_emitter._sparse_array.data[3, 1].tobytes()
    assert message.data == expected_data

def test_create_frame_message_invalid_position(frame_emitter):
    with pytest.raises(IndexError, match="Invalid scan_position_index"):
        frame_emitter._create_frame_message(scan_position_index=25, frame_index=0)

def test_create_frame_message_invalid_frame_index(frame_emitter):
    with pytest.raises(IndexError, match="Invalid frame_index"):
        frame_emitter._create_frame_message(scan_position_index=3, frame_index=2)

def test_get_next_frame_message(frame_emitter):
    messages = []
    for _ in range(3):
        msg = frame_emitter.get_next_frame_message()
        assert isinstance(msg, BytesMessage)
        messages.append(msg)
    assert frame_emitter._position_index == 1
    assert frame_emitter._frame_index == 0
    assert frame_emitter._frames_emitted == 3
    meta0 = messages[0].header.meta
    assert meta0["STEM_row_in_scan"] == 0
    assert meta0["STEM_x_position_in_row"] == 0
    meta1 = messages[1].header.meta
    assert meta1["STEM_row_in_scan"] == 0
    assert meta1["STEM_x_position_in_row"] == 0
    meta2 = messages[2].header.meta
    assert meta2["STEM_row_in_scan"] == 0
    assert meta2["STEM_x_position_in_row"] == 1

def test_emitter_exhaustion(frame_emitter):
    for _ in range(50):
        frame_emitter.get_next_frame_message()
    assert frame_emitter._frames_emitted == 50
    assert frame_emitter._position_index == 24
    assert frame_emitter._frame_index == 1
    with pytest.raises(StopIteration):
        frame_emitter.get_next_frame_message()
    assert frame_emitter._finished
    with pytest.raises(StopIteration, match="FrameEmitter is finished"):
        frame_emitter.get_next_frame_message()

def test_emitter_raises_on_none_frame(mock_sparse_array):
    mock_sparse_array.data[5, 0] = None
    emitter = FrameEmitter(sparse_array=mock_sparse_array, scan_number=42)
    for _ in range(10):
        emitter.get_next_frame_message()
    with pytest.raises(ValueError, match="No data found for position 5, frame 0"):
        emitter.get_next_frame_message()
    assert emitter._frames_emitted == 10
    assert emitter._position_index == 4
    assert emitter._frame_index == 1

def test_emitter_raises_on_wrong_type_frame(mock_sparse_array):
    mock_sparse_array.data[10, 1] = "not an array"
    emitter = FrameEmitter(sparse_array=mock_sparse_array, scan_number=42)
    for _ in range(21):
        emitter.get_next_frame_message()
    with pytest.raises(TypeError, match="Expected ndarray for position 10, frame 1"):
        emitter.get_next_frame_message()
    assert emitter._frames_emitted == 21
    assert emitter._position_index == 10
    assert emitter._frame_index == 0

@pytest.fixture
def populated_frame_accumulator():
    accumulator = FrameAccumulator(
        scan_number=42,
        scan_shape=(5, 5),
        frame_shape=(128, 128)
    )
    return accumulator

def test_integration_emitter_to_accumulator(frame_emitter, populated_frame_accumulator):
    frames_added = 0
    for _ in range(10):
        msg = frame_emitter.get_next_frame_message()
        meta = msg.header.meta
        header = FrameHeader(
            scan_number=meta["scan_number"],
            nSTEM_positions_per_row_m1=meta["nSTEM_positions_per_row_m1"],
            nSTEM_rows_m1=meta["nSTEM_rows_m1"],
            STEM_x_position_in_row=meta["STEM_x_position_in_row"],
            STEM_row_in_scan=meta["STEM_row_in_scan"],
            modules=meta["modules"],
            frame_shape=tuple(meta["frame_shape"])
        )
        frame_data = np.frombuffer(msg.data, dtype=np.uint32)
        populated_frame_accumulator.add_frame(header, frame_data)
        frames_added += 1
    assert populated_frame_accumulator.num_frames_added == frames_added
    assert populated_frame_accumulator.num_positions_with_frames == 5
    positions = populated_frame_accumulator.frames_added_indices
    assert 0 in positions
    assert 1 in positions
    assert 2 in positions
    assert 3 in positions
    assert 4 in positions

def test_frame_emitter_with_empty_sparse_array():
    mock_array = MagicMock(spec=SparseArray)
    mock_array.scan_shape = (0, 0)
    mock_array.frame_shape = (128, 128)
    mock_array.num_scans = 0
    mock_data = np.empty((0, 1), dtype=object)
    mock_array.data = mock_data
    mock_array.data.shape = (0, 1)
    mock_array.metadata = {"scan_number": 1}
    emitter = FrameEmitter(sparse_array=mock_array, scan_number=1)
    assert emitter.total_positions == 0
    assert emitter.frames_per_position == 1
    assert emitter.total_frames == 0
    with pytest.raises(StopIteration):
        emitter.get_next_frame_message()
    assert emitter._finished
