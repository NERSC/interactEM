
from pydantic import BaseModel


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int | None = None
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]
    frame_shape: tuple[int, int]












