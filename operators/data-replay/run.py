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

# Initialize global variables
reader = None
scan_positions_cycle = None
n_cols = 0
n_rows = 0
send_count = 0
current_scan_num = -1


def read_scan_metadata(scan_num: int) -> tuple[stio.reader, itertools.cycle, int, int]:
    scan_name_path = Path(f"data_scan{scan_num:010}*.data")
    files = path.glob(str(scan_name_path))
    iFiles = sorted(files)
    iFiles_str = [str(ii) for ii in iFiles]
    reader = stio.reader(iFiles_str, stio.FileVersion.VERSION5, backend="multi-pass")
    block0 = reader.read_frames(0)
    scan_dimensions = block0[0].header.scan_dimensions
    n_cols, n_rows = scan_dimensions
    logger.info(f"Sending scan {scan_num} with dimensions {scan_dimensions}.")
    scan_positions = range(scan_dimensions[0] * scan_dimensions[1])
    scan_positions_cycle = itertools.cycle(scan_positions)
    return reader, scan_positions_cycle, n_cols, n_rows


@operator
def save(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global reader, scan_positions_cycle, n_cols, n_rows, send_count, current_scan_num
    
    scan_num = parameters.get("scan_num", None)
    if scan_num is None:
        logger.error("Missing scan_num parameter.")
        raise ValueError("Missing scan_num parameter.")
    
    # Only read new metadata when the scan number changes
    if scan_num != current_scan_num:
        logger.info(f"New scan number detected: {scan_num}, loading metadata")
        reader, scan_positions_cycle, n_cols, n_rows = read_scan_metadata(scan_num)
        current_scan_num = scan_num
        send_count = 0
    
    if scan_positions_cycle is None:
        _msg = "scan_positions_cycle is None. Make sure metadata is loaded properly."
        logger.error(_msg)
        raise ValueError("scan_positions_cycle is None. Make sure metadata is loaded properly.")
        
    position = next(scan_positions_cycle)
    if position == 0 and send_count > 0:
        logger.info(f"Completed full cycle of scan {scan_num}")
        logger.info(f"Sent {send_count} frames.")
    
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