import msgspec.structs
import numpy as np
import pytest

from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.models import (
    BatchedFrameHeader,
    BatchedFrames,
    Frame,
    FrameHeader,
)


def make_single_frame(header: FrameHeader, data: np.ndarray) -> Frame:
    return Frame(header=header, buffer=data.tobytes())


def test_add_frame_overwrites_same_position(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    frame1 = make_single_frame(sample_frame_header, sample_frame_data)
    frame2 = make_single_frame(sample_frame_header, sample_frame_data + 1)

    frame_accumulator.add_frame(frame1)
    frame_accumulator.add_frame(frame2)

    # Same position overwrites; only one frame slot exists per position, and
    # num_frames_added counts unique positions filled, not calls to add_frame
    # (a duplicate/retransmitted frame must not inflate scan-completion count).
    assert frame_accumulator.num_frames_added == 1
    assert len(frame_accumulator.frames_added_indices) == 1
    flat_pos = sample_frame_header.scan_position_flat
    np.testing.assert_array_equal(
        frame_accumulator.data_flat[flat_pos], sample_frame_data + 1
    )

    # Different position should add a new entry.
    header2 = msgspec.structs.replace(
        sample_frame_header, STEM_row_in_scan=4, STEM_x_position_in_row=6
    )
    frame3 = make_single_frame(header2, sample_frame_data)
    frame_accumulator.add_frame(frame3)
    assert len(frame_accumulator.frames_added_indices) == 2
    assert frame_accumulator.num_frames_added == 2


@pytest.mark.parametrize("batched", [False, True])
def test_process_message(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
    batched,
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


def test_add_batch_duplicate_position_does_not_inflate_count(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    """Regression test: a retransmitted batch covering an already-filled
    position must not inflate num_frames_added, since `finished` compares
    it against total_frames and would otherwise fire early while most
    positions are still zero-filled."""
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
    frame_accumulator.add_message(msg)  # duplicate/retransmitted batch

    assert frame_accumulator.num_frames_added == 1
    assert len(frame_accumulator.frames_added_indices) == 1


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
    with pytest.raises(ValueError):
        frame_accumulator.add_message(msg)

    # Insufficient data
    insufficient_header = msgspec.structs.replace(
        sample_frame_header, data_size_bytes=128 * 128 * 4
    )
    small_data = np.zeros((2, 2), dtype=np.uint32)
    batched_header = BatchedFrameHeader(
        scan_number=insufficient_header.scan_number,
        headers=[insufficient_header],
        batch_size_bytes=128 * 128 * 4,
    )
    batched_frames = BatchedFrames.from_np_arrays(batched_header, [small_data])
    msg = batched_frames.to_bytes_message()
    with pytest.raises(ValueError):
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

    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1

    frame_accumulator.clear()
    assert frame_accumulator.num_frames_added == 0
    assert frame_accumulator.data.shape == (10, 10, 128, 128)
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

    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 1
