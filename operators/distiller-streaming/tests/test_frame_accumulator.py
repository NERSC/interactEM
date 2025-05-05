import numpy as np
import pytest

from distiller_streaming.util import (
    calculate_diffraction_center,
    get_diffraction_center,
    get_summed_diffraction_pattern,
)


def test_frame_accumulator_init(frame_accumulator):
    assert frame_accumulator.scan_number == 1
    assert frame_accumulator.scan_shape == (10, 10)
    assert frame_accumulator.frame_shape == (128, 128)
    assert frame_accumulator.num_scans == 100
    assert frame_accumulator.data.shape == (100, 1)
    assert frame_accumulator.num_frames_added == 0
    assert len(frame_accumulator._frames_per_position) == 0
    assert frame_accumulator.dtype == np.uint32
    assert isinstance(frame_accumulator.data[0, 0], np.ndarray)
    assert frame_accumulator.data[0, 0].size == 0


def test_add_first_frame(frame_accumulator, sample_frame_header, sample_frame_data):
    scan_pos_flat = 3 * 10 + 5
    frame_accumulator.add_frame(sample_frame_header, sample_frame_data)
    assert frame_accumulator.num_frames_added == 1
    assert frame_accumulator.num_positions_with_frames == 1
    assert scan_pos_flat in frame_accumulator.frames_added_indices
    assert frame_accumulator._frames_per_position[scan_pos_flat] == 1
    assert frame_accumulator.data.shape == (100, 1)
    assert np.array_equal(
        frame_accumulator.data.flat[scan_pos_flat * 1 + 0], sample_frame_data
    )
    assert frame_accumulator.data.flat[0].size == 0

def test_add_second_frame_same_position(
    frame_accumulator, sample_frame_header, sample_frame_data
):
    scan_pos_flat = 3 * 10 + 5
    data1 = sample_frame_data
    data2 = sample_frame_data + 1
    frame_accumulator.add_frame(sample_frame_header, data1)
    frame_accumulator.add_frame(sample_frame_header, data2)
    assert frame_accumulator.num_frames_added == 2
    assert frame_accumulator.num_positions_with_frames == 1
    assert scan_pos_flat in frame_accumulator.frames_added_indices
    assert frame_accumulator._frames_per_position[scan_pos_flat] == 2
    assert frame_accumulator.data.shape == (100, 2)
    assert np.array_equal(frame_accumulator.data.flat[scan_pos_flat * 2 + 0], data1)
    assert np.array_equal(frame_accumulator.data.flat[scan_pos_flat * 2 + 1], data2)
    assert frame_accumulator.data.flat[0].size == 0
    assert frame_accumulator.data.flat[1].size == 0

def test_add_frames_different_positions(frame_accumulator, sample_frame_header, sample_frame_data):
    header1 = sample_frame_header
    data1 = sample_frame_data
    header2 = sample_frame_header.model_copy()
    header2.STEM_x_position_in_row = 0
    header2.STEM_row_in_scan = 0
    data2 = sample_frame_data + 1
    frame_accumulator.add_frame(header1, data1)
    frame_accumulator.add_frame(header2, data2)
    assert frame_accumulator.num_frames_added == 2
    assert frame_accumulator.num_positions_with_frames == 2
    assert 35 in frame_accumulator.frames_added_indices
    assert 0 in frame_accumulator.frames_added_indices
    assert frame_accumulator._frames_per_position[35] == 1
    assert frame_accumulator._frames_per_position[0] == 1
    assert frame_accumulator.shape == (10, 10, 128, 128)
    assert frame_accumulator.data.shape == (100, 1)
    assert np.array_equal(frame_accumulator.data.flat[35], data1)
    assert np.array_equal(frame_accumulator.data.flat[0], data2)


def test_add_frame_scan_number_mismatch(
    frame_accumulator, sample_frame_header, sample_frame_data
):
    header_wrong_scan = sample_frame_header.model_copy(update={"scan_number": 99})
    with pytest.raises(ValueError, match="Scan number mismatch"):
        frame_accumulator.add_frame(header_wrong_scan, sample_frame_data)


def test_add_frame_scan_shape_mismatch(
    frame_accumulator, sample_frame_header, sample_frame_data
):
    header_wrong_shape = sample_frame_header.model_copy(update={"nSTEM_rows_m1": 11})
    with pytest.raises(ValueError, match="Mismatch between header scan shape"):
        frame_accumulator.add_frame(header_wrong_shape, sample_frame_data)


def test_add_frame_frame_shape_mismatch(
    frame_accumulator, sample_frame_header, sample_frame_data
):
    header_wrong_shape = sample_frame_header.model_copy(
        update={"frame_shape": (64, 64)}
    )
    with pytest.raises(ValueError, match="Mismatch between header frame shape"):
        frame_accumulator.add_frame(header_wrong_shape, sample_frame_data)


def test_add_frame_position_out_of_bounds(frame_accumulator, sample_frame_header, sample_frame_data):
    header_out_of_bounds = sample_frame_header.model_copy(
        update={"STEM_row_in_scan": 10}
    )
    with pytest.raises(IndexError, match="Invalid scan position"):
        frame_accumulator.add_frame(header_out_of_bounds, sample_frame_data)


def test_get_summed_diffraction_pattern(populated_frame_accumulator):
    summed_dp = get_summed_diffraction_pattern(
        populated_frame_accumulator, subsample_step=1
    )
    assert isinstance(summed_dp, np.ndarray)
    assert summed_dp.shape == populated_frame_accumulator.frame_shape
    assert summed_dp.dtype == np.float64
    assert summed_dp.sum() > 0


def test_get_summed_diffraction_pattern_subsampled(populated_frame_accumulator):
    summed_dp = get_summed_diffraction_pattern(populated_frame_accumulator, subsample_step=2)
    assert isinstance(summed_dp, np.ndarray)
    assert summed_dp.shape == populated_frame_accumulator.frame_shape
    assert summed_dp.sum() > 0

def test_get_summed_diffraction_pattern_empty(frame_accumulator):
    with pytest.raises(ValueError, match="No frames available for summing"):
        get_summed_diffraction_pattern(frame_accumulator)


def test_calculate_diffraction_center():
    size = 128
    center_x, center_y = size // 2, size // 2
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    sigma = 10
    pattern = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma**2))
    calculated_center = calculate_diffraction_center(pattern)
    assert calculated_center == (63, 63)


def test_calculate_diffraction_center_empty():
    empty_pattern = np.array([])
    with pytest.raises(ValueError, match="Empty diffraction pattern"):
        calculate_diffraction_center(empty_pattern)


def test_get_diffraction_center(populated_frame_accumulator):
    center = get_diffraction_center(populated_frame_accumulator, subsample_step=1)
    assert isinstance(center, tuple)
    assert len(center) == 2
    assert isinstance(center[0], int)
    assert isinstance(center[1], int)

def test_get_diffraction_center_empty(frame_accumulator):
    with pytest.raises(ValueError, match="No frames available for summing"):
        get_diffraction_center(frame_accumulator)
