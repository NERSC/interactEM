import numpy as np
from stempy.image import com_sparse as stempy_com_sparse
from stempy.io import SparseArray

from distiller_streaming.accumulator import FrameAccumulator
from distiller_streaming.com import com_sparse
from distiller_streaming.models import BatchedFrames


def test_com_sparse_vs_stempy():
    """Test that our com_sparse produces
    the same results as stempy's com_sparse."""

    # Create synthetic batch with known parameters
    batch = BatchedFrames.create_synthetic_batch(
        scan_size=32,  # Smaller size for faster testing
        frame_shape=(128, 128),
        frames_per_position=1,
        events_per_frame=50,
    )

    # Convert BatchedFrames to FrameAccumulator
    accumulator = FrameAccumulator.from_batch(batch)

    # Convert FrameAccumulator to stempy-compatible SparseArray
    stempy_array = SparseArray(
        data=accumulator.data,
        scan_shape=accumulator.scan_shape,
        frame_shape=accumulator.frame_shape,
        dtype=accumulator.dtype,
    )

    # Test our implementation
    our_result = com_sparse(batch)

    # Test stempy implementation
    stempy_result = stempy_com_sparse(stempy_array)

    # Compare results - they should be very close (allowing for floating point precision)
    np.testing.assert_allclose(
        our_result,
        stempy_result,
        rtol=1e-5,
        atol=1e-6,
        err_msg="Our com_sparse implementation differs from stempy's implementation",
    )

    # Additional shape and type checks
    assert our_result.shape == stempy_result.shape
    assert our_result.dtype == stempy_result.dtype
