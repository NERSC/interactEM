#!/usr/bin/env python3
"""Standalone, pipeline-free verification of distiller_streaming_dense against
real dense 4D-STEM data read via ncempy.

This is NOT an interactEM operator and is not wired into NATS/pipelines. It
exercises the dense package's real code paths (FrameAccumulator, BatchEmitter,
wire-format round-trip, get_summed_diffraction_pattern,
calculate_diffraction_center, com_dense_batch) directly against a file on
disk, so you can sanity-check real data shapes/values on the dev machine
before building a real read-tem-data successor operator.

Usage:
    python verify_dense_pipeline.py /path/to/file.emd
    python verify_dense_pipeline.py /path/to/file.emd --scan-shape 128 128 --frame-shape 256 256
    python verify_dense_pipeline.py /path/to/file.emd --max-positions 2048 --batch-size-mb 2.0

Requires ncempy to be installed (not a dependency of distiller_streaming_dense
itself -- install separately, e.g. `uv pip install ncempy`).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.com import com_dense_batch
from distiller_streaming_dense.emitter import BatchEmitter
from distiller_streaming_dense.models import (
    BatchedFrameHeader,
    BatchedFrames,
    FrameHeader,
    NumpyDtype,
)
from distiller_streaming_dense.util import (
    calculate_diffraction_center,
    get_summed_diffraction_pattern,
)


def banner(title: str) -> None:
    print()
    print(f"=== {title} ===")


def load_dense_array(
    file_path: Path,
    scan_shape: tuple[int, int] | None,
    frame_shape: tuple[int, int] | None,
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    """Read a file with ncempy and split its shape into (scan_shape, frame_shape)."""
    import ncempy  # imported lazily: not a dependency of this package

    banner("Reading file with ncempy")
    t0 = time.monotonic()
    dd = ncempy.read(file_path)
    data = dd["data"]
    print(f"ncempy.read took {time.monotonic() - t0:.2f}s")
    print(f"raw data shape: {data.shape}, dtype: {data.dtype}")

    if scan_shape is not None and frame_shape is not None:
        expected = scan_shape + frame_shape
        data = data.reshape(expected)
        return data, scan_shape, frame_shape

    if data.ndim != 4:
        raise ValueError(
            f"Expected a 4D array (scan_y, scan_x, frame_y, frame_x) from ncempy, "
            f"got shape {data.shape} (ndim={data.ndim}). "
            f"Pass --scan-shape and --frame-shape explicitly to disambiguate."
        )

    scan_shape = (int(data.shape[0]), int(data.shape[1]))
    frame_shape = (int(data.shape[2]), int(data.shape[3]))
    return data, scan_shape, frame_shape


def build_batched_frames(
    data: np.ndarray,
    scan_shape: tuple[int, int],
    frame_shape: tuple[int, int],
    scan_number: int,
    position_indices: np.ndarray,
) -> BatchedFrames:
    """Build a real BatchedFrames (same wire format interactEM would send)
    for a subset of scan positions, to exercise serialization."""
    data_flat = data.reshape(np.prod(scan_shape), *frame_shape)
    try:
        dtype_enum = NumpyDtype(data.dtype.name)
    except ValueError:
        raise ValueError(
            f"Data dtype '{data.dtype}' is not one of the supported wire dtypes "
            f"({[d.value for d in NumpyDtype]}). Cast the array before building "
            f"BatchedFrames, e.g. data.astype('uint32')."
        )

    headers = []
    arrays = []
    for pos in position_indices:
        row, col = np.unravel_index(int(pos), scan_shape)
        frame = data_flat[int(pos)]
        headers.append(
            FrameHeader(
                scan_number=scan_number,
                nSTEM_positions_per_row_m1=scan_shape[1],
                nSTEM_rows_m1=scan_shape[0],
                STEM_x_position_in_row=int(col),
                STEM_row_in_scan=int(row),
                modules=[0],
                frame_shape=frame_shape,
                data_size_bytes=frame.nbytes,
                dtype=dtype_enum,
            )
        )
        arrays.append(np.ascontiguousarray(frame))

    header = BatchedFrameHeader(
        scan_number=scan_number,
        headers=headers,
        batch_size_bytes=sum(a.nbytes for a in arrays),
    )
    return BatchedFrames.from_np_arrays(header, arrays)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to a TEM data file readable by ncempy")
    parser.add_argument(
        "--scan-shape",
        type=int,
        nargs=2,
        metavar=("NY", "NX"),
        default=None,
        help="Override scan shape if the file's array isn't naturally 4D",
    )
    parser.add_argument(
        "--frame-shape",
        type=int,
        nargs=2,
        metavar=("FY", "FX"),
        default=None,
        help="Override frame shape if the file's array isn't naturally 4D",
    )
    parser.add_argument(
        "--max-positions",
        type=int,
        default=2048,
        help="Cap the number of scan positions used for the wire-format "
        "round-trip and COM checks (full dataset is still used for the "
        "FrameAccumulator/summed-diffraction-pattern checks). Default: 2048.",
    )
    parser.add_argument("--batch-size-mb", type=float, default=1.0)
    parser.add_argument("--subsample-step", type=int, default=2)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 1

    scan_shape = tuple(args.scan_shape) if args.scan_shape else None
    frame_shape = tuple(args.frame_shape) if args.frame_shape else None

    data, scan_shape, frame_shape = load_dense_array(args.file, scan_shape, frame_shape)
    num_scans = scan_shape[0] * scan_shape[1]
    scan_number = 0

    print(f"Resolved scan_shape={scan_shape}, frame_shape={frame_shape}, num_scans={num_scans}")

    # --- 1. FrameAccumulator: load the full dataset directly ---
    banner("FrameAccumulator: full-dataset load")
    accumulator = FrameAccumulator(
        scan_number=scan_number,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        dtype=data.dtype,
    )
    accumulator.data = np.ascontiguousarray(data)
    accumulator._frames_added = set(range(num_scans))
    accumulator._num_frames_added = num_scans
    print(f"accumulator.shape = {accumulator.shape}")
    print(f"accumulator.num_frames_added = {accumulator.num_frames_added}")

    # --- 2. Summed diffraction pattern + beam center ---
    banner("get_summed_diffraction_pattern / calculate_diffraction_center")
    t0 = time.monotonic()
    summed_dp = get_summed_diffraction_pattern(
        accumulator, subsample_step=args.subsample_step
    )
    print(f"summed_dp.shape={summed_dp.shape}, dtype={summed_dp.dtype}, "
          f"sum={summed_dp.sum():.3e} ({time.monotonic() - t0:.2f}s)")

    center = calculate_diffraction_center(summed_dp)
    print(f"calculated beam center (x, y) = {center}")

    # --- 3. Wire-format round trip (subset of positions, for speed) ---
    banner("BatchedFrames wire-format round-trip (subset)")
    n_subset = min(args.max_positions, num_scans)
    subset_positions = np.arange(n_subset)
    batch = build_batched_frames(data, scan_shape, frame_shape, scan_number, subset_positions)
    msg = batch.to_bytes_message()
    print(f"Serialized {n_subset} positions into one message: "
          f"meta={len(msg.header.meta)} bytes, data={len(msg.data)} bytes")

    round_tripped = BatchedFrames.from_bytes_message(msg)
    frames, positions = round_tripped.get_frame_stack_with_positions()
    assert frames.shape == (n_subset, *frame_shape), frames.shape
    data_flat = data.reshape(num_scans, *frame_shape)
    for i, pos in enumerate(positions[: min(5, n_subset)]):
        np.testing.assert_array_equal(frames[i], data_flat[int(pos)])
    print("Round-tripped frame bytes match source data for sampled positions. OK.")

    # --- 4. FrameAccumulator rebuilt from a real BatchedFrames batch ---
    banner("FrameAccumulator.add_batch from wire-format batch")
    acc2 = FrameAccumulator(
        scan_number=scan_number, scan_shape=scan_shape, frame_shape=frame_shape, dtype=data.dtype
    )
    acc2.add_batch(round_tripped)
    print(f"acc2.num_frames_added = {acc2.num_frames_added} (expected {n_subset})")
    assert acc2.num_frames_added == n_subset

    # --- 5. BatchEmitter: drive the subset accumulator out as batched messages ---
    banner("BatchEmitter over subset accumulator")
    emitter = BatchEmitter(acc2, scan_number=scan_number, batch_size_mb=args.batch_size_mb)
    print(f"total_positions={emitter.total_positions}, total_batches={emitter.total_batches}")
    n_messages = 0
    n_frames_emitted = 0
    try:
        while True:
            out_msg = emitter.get_next_batch_message()
            decoded = BatchedFrames.from_bytes_message(out_msg)
            n_frames_emitted += len(decoded.header.headers)
            n_messages += 1
    except StopIteration:
        pass
    print(f"Emitted {n_frames_emitted} frames in {n_messages} messages "
          f"(expected {acc2.num_scans} frames)")
    assert n_frames_emitted == acc2.num_scans

    # --- 6. Center of mass over the subset batch ---
    banner("com_dense_batch over subset batch")
    t0 = time.monotonic()
    com = com_dense_batch(round_tripped, replace_nans=True)
    print(f"com.shape={com.shape} ({time.monotonic() - t0:.2f}s for {n_subset} frames)")
    print(f"com[:, 0, 0] (first scan position's (y, x) COM) = {com[:, 0, 0]}")

    banner("All checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
