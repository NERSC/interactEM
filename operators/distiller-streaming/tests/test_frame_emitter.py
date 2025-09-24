import msgspec
import msgspec.msgpack
import numpy as np
import pytest

from distiller_streaming.emitter import BatchEmitter
from distiller_streaming.models import BatchedFrameHeader
from interactem.core.models.messages import BytesMessage


def emit_all(emitter):
    messages = []
    try:
        while True:
            messages.append(emitter.get_next_frame_message())
    except StopIteration:
        return messages


def test_init_and_invalid_args(sparse_array):
    e = BatchEmitter(sparse_array, 42, 1.0)
    assert e.total_frames == 50 and not e.finished
    with pytest.raises(TypeError):
        BatchEmitter("bad", 1, 1)  # type: ignore
    with pytest.raises(TypeError):
        BatchEmitter(sparse_array, "x", 1)  # type: ignore
    with pytest.raises(ValueError):
        BatchEmitter(sparse_array, 1, 0)


def test_single_vs_batched(sparse_array):
    for n in (1.0, 5.0):  # here 5.0 MB will likely batch multiple frames
        e = BatchEmitter(sparse_array, 42, n)
        m = e.get_next_frame_message()
        assert isinstance(m, BytesMessage)


def test_dtype_and_empty_data(sparse_array):
    sparse_array.data[0, 0] = np.array([], np.uint32)
    sparse_array.data[1, 0] = np.array([1, 2, 3], np.int64)
    e = BatchEmitter(sparse_array, 42, 1.0)
    msgs = emit_all(e)
    for m in msgs:
        header = msgspec.msgpack.decode(m.header.meta, type=BatchedFrameHeader)
        for h in header.headers:
            assert isinstance(h.data_size_bytes, int)


def test_frame_order(sparse_array):
    e = BatchEmitter(sparse_array, 42, 1.0)
    positions = [
        (h.STEM_row_in_scan, h.STEM_x_position_in_row, h.frame_number or 0)
        for m in emit_all(e)
        for h in msgspec.msgpack.decode(m.header.meta, type=BatchedFrameHeader).headers
    ]
    assert positions == sorted(positions)


def test_batching_counts(sparse_array):
    # Use a tiny batch size so we get multiple messages
    e = BatchEmitter(sparse_array, 42, 0.00001)
    msgs = emit_all(e)
    assert len(msgs) > 1
    assert all(isinstance(m, BytesMessage) for m in msgs)


def test_exhaustion(sparse_array):
    e = BatchEmitter(sparse_array, 42, 1.0)
    emit_all(e)
    assert e.finished
    with pytest.raises(StopIteration):
        e.get_next_frame_message()


@pytest.mark.parametrize(
    "batch_size_mb",
    [0.00001, 0.0001, 0.001, 1.0, 10.0],  # Include both small and large batch sizes
)
def test_batch_count_and_metadata(sparse_array, batch_size_mb):
    """Test that batch count prediction and metadata are correct for various batch sizes."""
    e = BatchEmitter(sparse_array, 42, batch_size_mb)

    # Check predicted batch count
    predicted_batches = e.total_batches
    assert isinstance(predicted_batches, int)
    assert predicted_batches > 0

    # Generate all messages
    msgs = emit_all(e)
    actual_batches = len(msgs)

    # Predicted count should match actual
    assert predicted_batches == actual_batches, (
        f"Batch size {batch_size_mb} MB: predicted {predicted_batches} "
        f"batches but got {actual_batches}"
    )

    # Check metadata in each message
    for i, msg in enumerate(msgs):
        header = msgspec.msgpack.decode(msg.header.meta, type=BatchedFrameHeader)

        assert header.total_batches == predicted_batches
        assert header.total_batches is not None

        assert header.current_batch_index == i
        assert header.current_batch_index is not None
        assert 0 <= header.current_batch_index < header.total_batches

    # Special case: single batch
    if batch_size_mb >= 10.0:  # Large enough to fit all frames
        assert predicted_batches == 1
        assert actual_batches == 1
        header = msgspec.msgpack.decode(msgs[0].header.meta, type=BatchedFrameHeader)
        assert header.total_batches == 1
        assert header.current_batch_index == 0
