import numpy as np
import pytest

from distiller_streaming.util import (
    calculate_diffraction_center,
    get_diffraction_center,
    get_summed_diffraction_pattern,
)


@pytest.mark.parametrize("subsample_step", [1, 2])
def test_get_summed_diffraction_pattern_variants(
    populated_frame_accumulator, subsample_step
):
    summed_dp = get_summed_diffraction_pattern(
        populated_frame_accumulator, subsample_step=subsample_step
    )
    assert summed_dp.shape == populated_frame_accumulator.frame_shape
    assert summed_dp.dtype == np.float64
    assert summed_dp.sum() > 0


@pytest.mark.parametrize(
    "func,kwargs,err",
    [
        (get_summed_diffraction_pattern, {}, "No frames available for summing"),
        (get_diffraction_center, {}, "No frames available for summing"),
    ],
)
def test_empty_accumulator_errors(frame_accumulator, func, kwargs, err):
    with pytest.raises(ValueError, match=err):
        func(frame_accumulator, **kwargs)


def test_calculate_diffraction_center_gaussian():
    size = 128
    cx, cy = size // 2, size // 2
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    sigma = 10
    pattern = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma**2))
    assert calculate_diffraction_center(pattern) == (63, 63)


def test_calculate_diffraction_center_empty():
    with pytest.raises(ValueError, match="Empty diffraction pattern"):
        calculate_diffraction_center(np.array([]))
