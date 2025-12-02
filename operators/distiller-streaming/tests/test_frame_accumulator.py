import msgspec.structs
import numpy as np
import pytest

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import (
    BatchedFrameHeader,
    BatchedFrames,
    Frame,
    FrameHeader,
)


def make_single_frame(header: FrameHeader, data: np.ndarray) -> Frame:
    return Frame(header=header, buffer=data.tobytes())


def test_add_frame_same_and_different_positions(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    frame1 = make_single_frame(sample_frame_header, sample_frame_data)
    frame2 = make_single_frame(sample_frame_header, sample_frame_data)

    # Same position should expand
    frame_accumulator.add_frame(frame1)
    frame_accumulator.add_frame(frame2)
    assert frame_accumulator.data.shape[1] == 2

    # Different position should not expand
    header2 = msgspec.structs.replace(
        sample_frame_header, STEM_row_in_scan=4, STEM_x_position_in_row=6
    )
    frame3 = make_single_frame(header2, sample_frame_data)
    frame_accumulator.add_frame(frame3)
    assert frame_accumulator.data.shape[1] == 2  # unchanged


@pytest.mark.parametrize("batched", [False, True])
def test_process_message(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
    batched,
):
    # Update header with correct data size
    header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )

    # Create BatchedFrames and convert to message
    batched_header = BatchedFrameHeader(
        scan_number=header.scan_number,
        headers=[header],
        batch_size_bytes=len(sample_frame_data.tobytes()),
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [sample_frame_data])
    msg = batched_frames.to_bytes_message()

    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1


def test_expand_frame_dimension(frame_accumulator: FrameAccumulator):
    frame_accumulator.expand_frame_dimension_if_needed(5)
    assert frame_accumulator.data.shape == (100, 5)


def test_index_out_of_bounds(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    bad = msgspec.structs.replace(sample_frame_header, STEM_row_in_scan=999)
    frame = make_single_frame(bad, sample_frame_data)
    with pytest.raises(IndexError):
        frame_accumulator.add_frame(frame)


def test_size_mismatch_and_insufficient_data(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    # Size mismatch
    header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )

    batched_header = BatchedFrameHeader(
        scan_number=header.scan_number,
        headers=[header],
        batch_size_bytes=len(sample_frame_data.tobytes()),
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [sample_frame_data])
    msg = batched_frames.to_bytes_message()
    msg = msg.model_copy(update={"data": msg.data + b"extra"})
    with pytest.raises(ValueError, match="Unused bytes detected"):
        frame_accumulator.add_message(msg)

    # Insufficient data
    insufficient_header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=100
    )
    small_data = np.array([1, 2], np.uint32)
    batched_header = BatchedFrameHeader(
        scan_number=insufficient_header.scan_number,
        headers=[insufficient_header],
        batch_size_bytes=100,
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [small_data])
    msg = batched_frames.to_bytes_message()
    with pytest.raises(ValueError, match="buffer is smaller than requested size"):
        frame_accumulator.add_message(msg)


def test_clear_resets_accumulator(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )
    batched_header = BatchedFrameHeader(
        scan_number=header.scan_number,
        headers=[header],
        batch_size_bytes=len(sample_frame_data.tobytes()),
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [sample_frame_data])
    msg = batched_frames.to_bytes_message()

    # add a batch so we have data
    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1

    # expand to force more slots
    frame_accumulator.expand_frame_dimension_if_needed(5)
    assert frame_accumulator.data.shape[1] >= 5

    # clear and assert reset
    frame_accumulator.clear()
    assert frame_accumulator.num_frames_added == 0
    assert frame_accumulator.data.shape == (100, 1)
    assert frame_accumulator.frames_added_indices == set()


def test_clear_then_reuse(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=len(sample_frame_data.tobytes())
    )
    batched_header = BatchedFrameHeader(
        scan_number=header.scan_number,
        headers=[header],
        batch_size_bytes=len(sample_frame_data.tobytes()),
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [sample_frame_data])
    msg = batched_frames.to_bytes_message()

    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1

    frame_accumulator.clear()

    # Add again after clear
    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1
