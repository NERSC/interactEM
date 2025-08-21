import numpy as np
import pytest

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.models import BatchedFrameHeader, FrameHeader
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject


def make_single_message(header, data) -> BytesMessage:
    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES, meta=header.model_dump()),
        data=data.tobytes(),
    )


def test_add_frame_same_and_different_positions(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    # Same position should expand
    frame_accumulator.add_frame(sample_frame_header, sample_frame_data)
    frame_accumulator.add_frame(sample_frame_header, sample_frame_data)
    assert frame_accumulator.data.shape[1] == 2

    # Different position should not expand
    header2 = sample_frame_header.model_copy(
        update={"STEM_row_in_scan": 4, "STEM_x_position_in_row": 6}
    )
    frame_accumulator.add_frame(header2, sample_frame_data)
    assert frame_accumulator.data.shape[1] == 2  # unchanged


@pytest.mark.parametrize(
    "update,err",
    [
        ({"scan_number": 99}, "Scan number mismatch"),
        ({"nSTEM_rows_m1": 11}, "Mismatch between header scan shape"),
        ({"frame_shape": (64, 64)}, "Mismatch between header frame shape"),
    ],
)
def test_invalid_headers(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
    update: dict[str, int] | dict[str, tuple[int, int]],
    err,
):
    bad = sample_frame_header.model_copy(update=update)
    with pytest.raises(ValueError, match=err):
        frame_accumulator.add_frame(bad, sample_frame_data)


@pytest.mark.parametrize("batched", [False, True])
def test_process_message(
    frame_accumulator: FrameAccumulator,
    sample_frame_header: FrameHeader,
    sample_frame_data,
    batched,
    batched_message_factory,
):
    msg = (
        batched_message_factory([sample_frame_header], [sample_frame_data])
        if batched
        else make_single_message(sample_frame_header, sample_frame_data)
    )
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
    bad = sample_frame_header.model_copy(update={"STEM_row_in_scan": 999})
    with pytest.raises(IndexError):
        frame_accumulator.add_frame(bad, sample_frame_data)


def test_size_mismatch_and_insufficient_data(
    frame_accumulator: FrameAccumulator,
    batched_message_factory,
    sample_frame_header: FrameHeader,
    sample_frame_data,
):
    # Size mismatch
    msg = batched_message_factory([sample_frame_header], [sample_frame_data])
    msg = msg.model_copy(update={"data": msg.data + b"extra"})
    with pytest.raises(ValueError, match="Data size mismatch"):
        frame_accumulator.add_message(msg)

    # Insufficient data
    header = sample_frame_header.model_copy(update={"data_size_bytes": 100})
    msg = batched_message_factory([header], [np.array([1, 2], np.uint32)])
    with pytest.raises(ValueError, match="Insufficient data"):
        frame_accumulator.add_message(msg)


def test_empty_batched_message(frame_accumulator: FrameAccumulator):
    empty_header = BatchedFrameHeader(
        headers=[], total_batch_size_bytes=0, scan_number=frame_accumulator.scan_number
    )
    msg = BytesMessage(
        header=MessageHeader(
            subject=MessageSubject.BYTES, meta=empty_header.model_dump()
        ),
        data=b"",
    )
    frame_accumulator.add_message(msg)
    assert frame_accumulator.num_frames_added == 0
