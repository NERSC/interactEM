from enum import Enum

import numpy as np
from pydantic import BaseModel, field_validator


class NumpyDtype(str, Enum):
    uint8 = "uint8"
    uint16 = "uint16"
    uint32 = "uint32"
    int32 = "int32"
    float32 = "float32"
    float64 = "float64"


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int | None = None
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]
    frame_shape: tuple[int, int]
    data_size_bytes: int
    dtype: NumpyDtype = NumpyDtype.uint32

    @field_validator("dtype", mode="before")
    def _coerce_dtype(cls, v):
        if isinstance(v, NumpyDtype):
            return v
        if isinstance(v, np.dtype):
            name = v.name
            return NumpyDtype(name)
        if isinstance(v, type) and issubclass(v, np.generic):
            return NumpyDtype(np.dtype(v).name)
        if isinstance(v, str):
            try:
                name = np.dtype(v).name
            except Exception:
                raise ValueError(f"Unsupported dtype string: {v}")
            try:
                return NumpyDtype(name)
            except ValueError:
                raise ValueError(f"dtype {name} not in allowed NumpyDtype enum")
        raise ValueError("Unsupported dtype type")

    @property
    def np_dtype(self) -> np.dtype:
        return np.dtype(self.dtype.value)

    @property
    def scan_shape(self) -> tuple[int, int]:
        return (self.nSTEM_rows_m1, self.nSTEM_positions_per_row_m1)

    @property
    def scan_position_flat(self) -> int:
        return (
            self.STEM_row_in_scan * self.nSTEM_positions_per_row_m1
            + self.STEM_x_position_in_row
        )


class BatchedFrameHeader(BaseModel):
    scan_number: int
    headers: list[FrameHeader]
    total_batch_size_bytes: int

    @property
    def scan_shape(self) -> tuple[int, int]:
        return self.headers[0].scan_shape

    @property
    def frame_shape(self) -> tuple[int, int]:
        return self.headers[0].frame_shape

    @property
    def scan_positions_flat(self) -> list[int]:
        return [h.scan_position_flat for h in self.headers]

    @property
    def scan_positions(self) -> list[tuple[int, int]]:
        return [(h.STEM_row_in_scan, h.STEM_x_position_in_row) for h in self.headers]
