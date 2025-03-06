import asyncio
from collections import defaultdict
from pprint import pprint
from typing import Any

import msgpack
import numpy as np
from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)
from interactem.operators.operator import operator
from pydantic import BaseModel

logger = get_logger()


class FourdCameraHeader(BaseModel):
    scan_number: int
    frame_number: int
    num_frames_this_thread: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    thread_id: int
    module: int

    @staticmethod
    def from_msgpack(data: bytes) -> "FourdCameraHeader":
        unpacked_data = msgpack.unpackb(data)
        return FourdCameraHeader(
            scan_number=unpacked_data[0],
            frame_number=unpacked_data[1],
            num_frames_this_thread=unpacked_data[2],
            nSTEM_positions_per_row_m1=unpacked_data[3],
            nSTEM_rows_m1=unpacked_data[4],
            STEM_x_position_in_row=unpacked_data[5],
            STEM_row_in_scan=unpacked_data[6],
            thread_id=unpacked_data[7],
            module=unpacked_data[8],
        )


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]

    @classmethod
    def from_headers(cls, headers: dict[int, FourdCameraHeader]) -> "FrameHeader":
        header = headers[0]
        return cls(
            scan_number=header.scan_number,
            frame_number=header.frame_number,
            nSTEM_positions_per_row_m1=header.nSTEM_positions_per_row_m1,
            nSTEM_rows_m1=header.nSTEM_rows_m1,
            STEM_x_position_in_row=header.STEM_x_position_in_row,
            STEM_row_in_scan=header.STEM_row_in_scan,
            modules=list(headers.keys()),
        )


class FrameCache:
    def __init__(self):
        self.frames: dict[tuple[int, int], dict[int, list[bytes]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.headers: dict[tuple[int, int], dict[int, FourdCameraHeader]] = defaultdict(
            dict
        )

    def add_frame(self, header: FourdCameraHeader, data: bytes) -> bool:
        key = (header.scan_number, header.frame_number)
        self.frames[key][header.module].append(data)
        self.headers[key][header.module] = header

        if len(self.frames[key]) == 4:
            return True
        return False

    def get_complete_frame(
        self, header: FourdCameraHeader
    ) -> tuple[FrameHeader, np.ndarray]:
        key = (header.scan_number, header.frame_number)
        module_buffers = []

        # Create numpy buffers for each module
        for module in sorted(self.frames[key].keys()):
            module_data = b"".join(self.frames[key][module])
            module_array = np.frombuffer(module_data, dtype=np.uint16)
            module_buffers.append(module_array)

        # Stack the module buffers to form the complete frame
        complete_header = FrameHeader.from_headers(self.headers[key])
        nSTEM_positions_per_row = 576
        nSTEM_rows = 576
        frame_array = np.stack(module_buffers, axis=0).reshape(
            (nSTEM_rows, nSTEM_positions_per_row)
        )

        # Clean up the cache
        del self.frames[key]
        del self.headers[key]

        return complete_header, frame_array


frame_cache = FrameCache()


first_time = True


@operator
def assemble(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    if inputs is None:
        return None
    global first_time
    header_data = inputs.header.meta
    frame_data = inputs.data

    fourd_header = FourdCameraHeader(**header_data)
    is_complete = frame_cache.add_frame(fourd_header, frame_data)

    if is_complete:
        complete_header, complete_frame = frame_cache.get_complete_frame(fourd_header)
        new_header = MessageHeader(
            subject=MessageSubject.BYTES, meta=complete_header.model_dump()
        )
        if first_time:
            pprint(f"Complete frame: {new_header}")
            print(f"Complete frame: {complete_frame}")
            first_time = False
        return BytesMessage(header=new_header, data=complete_frame.tobytes())