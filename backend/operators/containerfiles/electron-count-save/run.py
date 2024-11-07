import asyncio
import pathlib
from typing import Any, cast

import h5py
import numpy as np
import stempy
import stempy.image as stim
import stempy.io
from pydantic import BaseModel, ValidationError

from core.logger import get_logger
from core.models.messages import BytesMessage
from operators.operator import operator

logger = get_logger("operator_main", "DEBUG")


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


open_files: dict[int, h5py.File] = {}
WRITE_PATH = pathlib.Path("/mnt/output_dir/")


def test_can_open(path: pathlib.Path):
    try:
        arr: stim.SparseArray = stempy.io.load_electron_counts(path)
        total_bytes = arr.data.nbytes
        total_mb = total_bytes / (1024 * 1024)  # Convert bytes to megabytes
        logger.info(f"Total size of arr.data: {total_mb*1024*1024:.2f} B")
        logger.info(f"Total size of arr.data: {total_mb:.2f} MB")
        print(arr.data[0][0])
    except Exception as e:
        logger.error(f"Failed to open file {path}: {e}")
        return False
    return True


count_for_this_scan = 0


@operator
def save(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    suffix = parameters.get("suffix", "")
    global count_for_this_scan
    if not inputs:
        return None
    try:
        header = FrameHeader(**inputs.header.meta)
    except ValidationError:
        logger.error("Invalid message")
        return None

    scan_shape = (header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1)
    frame_shape = (576, 576)
    f = open_files.get(header.scan_number, None)
    if not f:
        logger.info(f"Scan {header.scan_number - 1} has {count_for_this_scan} frames")
        count_for_this_scan = 1
        logger.info(f"Starting scan {header.scan_number}")
        keys_to_remove = list(open_files.keys())
        for k in keys_to_remove:
            open_files[k].close()
            test_can_open(WRITE_PATH / f"{k}.h5")
            del open_files[k]

        fpath = WRITE_PATH / (f"{header.scan_number}" + f"{suffix}" + ".h5")
        logger.info(f"Opening file {fpath}")
        f = h5py.File(fpath, "a")
        open_files[header.scan_number] = f

        if "electron_events" not in f:
            group = f.create_group("electron_events")
            group.attrs["version"] = stim.SparseArray.VERSION
            scan_positions_ds = group.create_dataset(
                "scan_positions", data=np.arange((np.prod(scan_shape),)[0])
            )
            frames_ds = group.create_dataset(
                "frames",
                (np.prod(scan_shape),),
                dtype=h5py.special_dtype(vlen=np.uint32),
            )

            frames_ds.attrs["Nx"] = frame_shape[0]
            frames_ds.attrs["Ny"] = frame_shape[1]
            scan_positions_ds.attrs["Nx"] = scan_shape[1]
            scan_positions_ds.attrs["Ny"] = scan_shape[0]

    group = cast(h5py.Group, f["electron_events"])
    scan_positions_ds = cast(h5py.Dataset, group["scan_positions"])
    frames_ds = cast(h5py.Dataset, group["frames"])

    arr = np.frombuffer(inputs.data, dtype=np.uint32)
    position = (header.STEM_row_in_scan, header.STEM_x_position_in_row)
    flat_index = np.ravel_multi_index(position, scan_shape)
    frames_ds[flat_index] = arr
    count_for_this_scan += 1
    return None


async def async_main():
    op = save()
    await op.start()


def main():
    # Run the async main function using asyncio.run
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


if __name__ == "__main__":
    main()
