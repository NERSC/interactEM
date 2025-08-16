import numpy as np
import pytest

from distiller_streaming.emitter import FrameEmitter, create_batch_message
from distiller_streaming.models import BatchedFrameHeader, FrameHeader
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


def test_frame_header_and_message(sparse_array):
    e = FrameEmitter(sparse_array, 42, 1.0)
    h, b = e._create_frame_header(3, 1)
    assert isinstance(h, FrameHeader) and h.data_size_bytes == b.nbytes
    m = e._create_frame_message(3, 1)
    assert isinstance(m, BytesMessage) and m.data == b.tobytes()


def test_batched_message(sparse_array):
    e = FrameEmitter(sparse_array, 42, 1.0)
    headers, data = zip(*(e._create_frame_header(i, 0) for i in range(3)), strict=False)
    m = create_batch_message(list(headers), list(data))
    meta = BatchedFrameHeader(**m.header.meta)
    assert len(meta.headers) == 3


@pytest.mark.parametrize("pos,frame", [(25, 0), (0, 5)])
def test_invalid_indices(sparse_array, pos, frame):
    e = FrameEmitter(sparse_array, 42, 1.0)
    with pytest.raises(IndexError):
        e._create_frame_message(pos, frame)


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
        for h in BatchedFrameHeader(**m.header.meta).headers:
            assert isinstance(h.data_size_bytes, int)


def test_frame_order(sparse_array):
    e = FrameEmitter(sparse_array, 42, 1.0)
    positions = [
        (h.STEM_row_in_scan, h.STEM_x_position_in_row, h.frame_number or 0)
        for m in emit_all(e)
        for h in BatchedFrameHeader(**m.header.meta).headers
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


def test_invalid_frame_data(sparse_array):
    sparse_array.data[0, 0] = None
    e = FrameEmitter(sparse_array, 42, 1.0)
    with pytest.raises(ValueError):
        e._create_frame_header(0, 0)


def test_invalid_shapes(sparse_array):
    sparse_array.scan_shape = ()
    with pytest.raises(ValueError):
        FrameEmitter(sparse_array, 42, 1.0)._create_frame_header(0, 0)
