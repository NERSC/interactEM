import msgspec.msgpack
import numpy as np
import pytest

from distiller_streaming.emitter import FrameEmitter
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
    e = FrameEmitter(sparse_array, 42, 1.0)
    assert e.total_frames == 50 and not e.is_finished()
    with pytest.raises(TypeError):
        FrameEmitter("bad", 1, 1)  # type: ignore
    with pytest.raises(TypeError):
        FrameEmitter(sparse_array, "x", 1)  # type: ignore
    with pytest.raises(ValueError):
        FrameEmitter(sparse_array, 1, 0)


def test_single_vs_batched(sparse_array):
    for n in (1.0, 5.0):  # here 5.0 MB will likely batch multiple frames
        e = FrameEmitter(sparse_array, 42, n)
        m = e.get_next_frame_message()
        assert isinstance(m, BytesMessage)


def test_dtype_and_empty_data(sparse_array):
    sparse_array.data[0, 0] = np.array([], np.uint32)
    sparse_array.data[1, 0] = np.array([1, 2, 3], np.int64)
    e = FrameEmitter(sparse_array, 42, 1.0)
    msgs = emit_all(e)
    for m in msgs:
        header = msgspec.msgpack.decode(m.header.meta, type=BatchedFrameHeader)
        for h in header.headers:
            assert isinstance(h.data_size_bytes, int)


def test_frame_order(sparse_array):
    e = FrameEmitter(sparse_array, 42, 1.0)
    positions = [
        (h.STEM_row_in_scan, h.STEM_x_position_in_row, h.frame_number or 0)
        for m in emit_all(e)
        for h in msgspec.msgpack.decode(m.header.meta, type=BatchedFrameHeader).headers
    ]
    assert positions == sorted(positions)


def test_batching_counts(sparse_array):
    # Use a tiny batch size so we get multiple messages
    e = FrameEmitter(sparse_array, 42, 0.00001)
    msgs = emit_all(e)
    assert len(msgs) > 1
    assert all(isinstance(m, BytesMessage) for m in msgs)


def test_exhaustion(sparse_array):
    e = FrameEmitter(sparse_array, 42, 1.0)
    emit_all(e)
    assert e.is_finished()
    with pytest.raises(StopIteration):
        e.get_next_frame_message()
