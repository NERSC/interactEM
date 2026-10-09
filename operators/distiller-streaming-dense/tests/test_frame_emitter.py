import msgspec
import msgspec.msgpack
import numpy as np
import pytest

from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.emitter import BatchEmitter
from distiller_streaming_dense.models import (
    BatchedFrameHeader,
    BatchedFrames,
    NumpyDtype,
)
from interactem.core.models.messages import BytesMessage


def emit_all(emitter):
    messages = []
    try:
        while True:
            messages.append(emitter.get_next_batch_message())
    except StopIteration:
        return messages


def test_init_and_invalid_args(frame_array):
    e = BatchEmitter(frame_array, 42, 1.0)
    assert e.total_frames == 25 and not e.finished
    with pytest.raises(TypeError):
        BatchEmitter("bad", 1, 1)  # type: ignore
    with pytest.raises(TypeError):
        BatchEmitter(frame_array, "x", 1)  # type: ignore
    with pytest.raises(ValueError):
        BatchEmitter(frame_array, 1, 0)


def test_single_vs_batched(frame_array):
    for n in (1.0, 5.0):
        e = BatchEmitter(frame_array, 42, n)
        m = e.get_next_batch_message()
        assert isinstance(m, BytesMessage)


def test_frame_order(frame_array):
    e = BatchEmitter(frame_array, 42, 1.0)
    positions = [
        (h.STEM_row_in_scan, h.STEM_x_position_in_row, h.frame_number or 0)
        for m in emit_all(e)
        for h in msgspec.msgpack.decode(m.header.meta, type=BatchedFrameHeader).headers
    ]
    assert positions == sorted(positions)


def test_batching_counts(frame_array):
    # Use a tiny batch size so we get multiple messages
    e = BatchEmitter(frame_array, 42, 0.00001)
    msgs = emit_all(e)
    assert len(msgs) > 1
    assert all(isinstance(m, BytesMessage) for m in msgs)


def test_exhaustion(frame_array):
    e = BatchEmitter(frame_array, 42, 1.0)
    emit_all(e)
    assert e.finished
    with pytest.raises(StopIteration):
        e.get_next_batch_message()


@pytest.mark.parametrize(
    "batch_size_mb",
    [0.00001, 0.0001, 0.001, 1.0, 10.0],
)
def test_batch_count_and_metadata(frame_array, batch_size_mb):
    """Test that batch count prediction and metadata are correct for various batch sizes."""
    e = BatchEmitter(frame_array, 42, batch_size_mb)

    predicted_batches = e.total_batches
    assert isinstance(predicted_batches, int)
    assert predicted_batches > 0

    msgs = emit_all(e)
    actual_batches = len(msgs)

    assert predicted_batches == actual_batches, (
        f"Batch size {batch_size_mb} MB: predicted {predicted_batches} "
        f"batches but got {actual_batches}"
    )

    for i, msg in enumerate(msgs):
        header = msgspec.msgpack.decode(msg.header.meta, type=BatchedFrameHeader)

        assert header.total_batches == predicted_batches
        assert header.total_batches is not None

        assert header.current_batch_index == i
        assert header.current_batch_index is not None
        assert 0 <= header.current_batch_index < header.total_batches

    if batch_size_mb >= 10.0:  # Large enough to fit all frames
        assert predicted_batches == 1
        assert actual_batches == 1
        header = msgspec.msgpack.decode(msgs[0].header.meta, type=BatchedFrameHeader)
        assert header.total_batches == 1
        assert header.current_batch_index == 0


@pytest.mark.parametrize("dtype", [np.uint16, np.int32, np.float32, np.float64])
def test_emitted_frame_headers_use_actual_dtype(dtype):
    """Regression test: emitted FrameHeaders must record the accumulator's
    real dtype, not silently default to uint32 (which corrupts same-width
    types like float32/int32 on decode and breaks reshape for mismatched
    widths like uint16)."""
    scan_shape, frame_shape = (2, 2), (4, 4)
    data = np.arange(2 * 2 * 4 * 4, dtype=dtype).reshape(*scan_shape, *frame_shape)
    accumulator = FrameAccumulator.from_dense_array(
        scan_number=1, scan_shape=scan_shape, frame_shape=frame_shape, data=data
    )

    emitter = BatchEmitter(accumulator, scan_number=1, batch_size_mb=1.0)
    msg = emitter.get_next_batch_message()
    decoded = BatchedFrames.from_bytes_message(msg)

    expected_dtype = NumpyDtype(np.dtype(dtype).name)
    for header in decoded.header.headers:
        assert header.dtype == expected_dtype

    frames, _ = decoded.get_frame_stack_with_positions()
    assert frames.dtype == np.dtype(dtype)
    np.testing.assert_array_equal(frames, data.reshape(-1, *frame_shape))
