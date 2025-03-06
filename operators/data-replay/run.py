import asyncio
import itertools
from pathlib import Path
from typing import Any

import numpy as np
import stempy.io as stio
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import DATA_DIRECTORY, operator
from pydantic import BaseModel, ValidationError

logger = get_logger()


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]


# Setup data paths
path = Path(f"{DATA_DIRECTORY}/raw_data_dir")
scan_num = 684
scan_name_path = Path(f"data_scan{scan_num:010}*.data")
files = path.glob(str(scan_name_path))
iFiles = sorted(files)

# Read the first frame to get the scan dimensions
iFiles_str = [str(ii) for ii in iFiles]
reader = stio.reader(iFiles_str, stio.FileVersion.VERSION5, backend="multi-pass")
block0 = reader.read_frames(0)
scan_dimensions = block0[0].header.scan_dimensions
n_cols, n_rows = scan_dimensions
frame_dimensions = block0[0].header.frame_dimensions
logger.info(f"Sending scan {scan_num} with dimensions {scan_dimensions}.")
scan_positions = range(scan_dimensions[0] * scan_dimensions[1])
scan_positions_cycle = itertools.cycle(scan_positions)
scan_num = -1
send_count = 0


@operator
def save(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global reader, scan_positions_cycle, scan_num, send_count
    position = next(scan_positions_cycle)
    if position == 0:
        logger.info(f"Finished scan {scan_num}")
        logger.info(f"Sent {send_count} frames.")
        scan_num += 1
        logger.info(f"Starting scan {scan_num}")
    block = reader.read_frames(position)
    row_idx, col_idx = np.unravel_index(position, (n_rows, n_cols))
    try:
        header = FrameHeader(
            scan_number=scan_num,
            frame_number=position,
            nSTEM_positions_per_row_m1=n_cols,
            nSTEM_rows_m1=n_rows,
            STEM_x_position_in_row=col_idx,  # type: ignore
            STEM_row_in_scan=row_idx,  # type: ignore
            modules=[0, 1, 2, 3],
        )
    except ValidationError as e:
        logger.error(f"Invalid message: {e}")
        return None

    send_count += 1

    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES, meta=header.model_dump()),
        data=block[0].data.tobytes(),
    )