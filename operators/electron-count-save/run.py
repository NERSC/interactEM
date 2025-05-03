import pathlib
from typing import Any, cast

import h5py
import numpy as np
import stempy.image as stim
from pydantic import BaseModel, ValidationError

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


open_files: dict[int, h5py.File] = {}
WRITE_PATH = pathlib.Path(f"{DATA_DIRECTORY}/output_dir/")


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
