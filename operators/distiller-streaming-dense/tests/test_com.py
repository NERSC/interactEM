import numpy as np
from stempy.image import com_dense

from distiller_streaming_dense.com import com_dense_batch
from distiller_streaming_dense.models import BatchedFrames


def naive_com_dense(frame: np.ndarray) -> tuple[float, float]:
    """Independent, unoptimized reference implementation of center-of-mass
    for a single 2D frame, used to cross-check com_dense without depending
    on stempy."""
    total = frame.sum()
    com_x = 0.0
    com_y = 0.0
    for yy in range(frame.shape[0]):
        for xx in range(frame.shape[1]):
            weight = frame[yy, xx]
            com_x += xx * weight
            com_y += yy * weight
    return com_x / total, com_y / total


def test_com_dense_matches_naive_reference():
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 5, size=(16, 16)).astype(np.float64)

    expected_x, expected_y = naive_com_dense(frame)
    result = com_dense(frame)

    assert result.shape == (2, 1)
    np.testing.assert_allclose(result[0, 0], expected_x, rtol=1e-10)
    np.testing.assert_allclose(result[1, 0], expected_y, rtol=1e-10)


def test_com_dense_batch_matches_per_frame_com():
    """com_dense_batch's per-position result should match calling com_dense
    directly on each frame individually."""
    batch = BatchedFrames.create_synthetic_batch(
        scan_size=4,
        frame_shape=(32, 32),
        events_per_frame=50,
    )

    result = com_dense_batch(batch, replace_nans=False)

    frames, positions = batch.get_frame_stack_with_positions()
    scan_shape = batch.header.scan_shape

    for frame, pos in zip(frames, positions, strict=True):
        expected = com_dense(frame)  # shape (2, 1): (x, y)
        row, col = np.unravel_index(int(pos), scan_shape)
        np.testing.assert_allclose(result[1, row, col], expected[0, 0], rtol=1e-5)
        np.testing.assert_allclose(result[0, row, col], expected[1, 0], rtol=1e-5)

    assert result.shape == (2, *scan_shape)
