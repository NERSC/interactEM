import io
from enum import StrEnum

import msgspec
import numpy as np

from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject


class NumpyDtype(StrEnum):
    uint8 = "uint8"
    uint16 = "uint16"
    uint32 = "uint32"
    int32 = "int32"
    float32 = "float32"
    float64 = "float64"


class FrameHeader(msgspec.Struct):
    scan_number: int
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]
    frame_shape: tuple[int, int]
    data_size_bytes: int
    frame_number: int | None = None

    dtype: NumpyDtype = NumpyDtype.uint32

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

    @property
    def scan_positions_flat(self) -> list[int]:
        return [self.scan_position_flat]

    @property
    def headers(self) -> list["FrameHeader"]:
        return [self]


class Frame:
    """A single dense 2D detector frame associated with a scan position."""

    def __init__(self, header: FrameHeader, buffer: bytes):
        self.header = header
        if len(buffer) != header.data_size_bytes:
            raise ValueError(
                f"Buffer size {len(buffer)} does not match header size {header.data_size_bytes}."
            )
        self.buffer = buffer
        self._cached_array = None  # Cache for expensive array creation

    @property
    def array(self) -> np.ndarray:
        # Cache the array to avoid repeated np.frombuffer calls
        if self._cached_array is None:
            flat = np.frombuffer(self.buffer, dtype=self.header.np_dtype)
            self._cached_array = flat.reshape(self.header.frame_shape)
        return self._cached_array


class BatchedFrameHeader(msgspec.Struct):
    scan_number: int
    headers: list[FrameHeader]
    batch_size_bytes: int
    total_batches: int | None = None
    total_frames: int | None = None
    current_batch_index: int | None = None

    def __post_init__(self):
        # Validate headers not empty
        if not self.headers:
            raise ValueError("headers list is empty")

        # Validate all headers have same scan number
        scan_numbers = {h.scan_number for h in self.headers}
        if len(scan_numbers) != 1:
            raise ValueError("All headers must have the same scan number.")

        # Validate cumulative data size
        total_size = sum(h.data_size_bytes for h in self.headers)
        if total_size != self.batch_size_bytes:
            raise ValueError(
                f"Cumulative data size does not match total header size: {total_size} != {self.batch_size_bytes}"
            )

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


class BatchedFrames(msgspec.Struct):
    header: BatchedFrameHeader
    data: bytes

    def to_bytes_message(self):
        header_bytes = msgspec.msgpack.encode(self.header)

        return BytesMessage(
            header=MessageHeader(
                subject=MessageSubject.BYTES,
                meta=header_bytes,
            ),
            data=self.data,
        )

    @classmethod
    def from_bytes_message(cls, message: BytesMessage) -> "BatchedFrames":
        if isinstance(message.header.meta, bytes):
            header = msgspec.msgpack.decode(
                message.header.meta, type=BatchedFrameHeader
            )
        else:
            header = msgspec.convert(message.header.meta, BatchedFrameHeader)
        return cls(header=header, data=message.data)

    @classmethod
    def from_np_arrays(
        cls, header: BatchedFrameHeader, arrays: list[np.ndarray]
    ) -> "BatchedFrames":
        data = b"".join(d.tobytes() for d in arrays)
        return cls(header=header, data=data)

    @classmethod
    def from_frames(cls, frames: list[Frame]) -> "BatchedFrames":
        header = BatchedFrameHeader(
            scan_number=frames[0].header.scan_number,
            headers=[frame.header for frame in frames],
            batch_size_bytes=sum(frame.header.data_size_bytes for frame in frames),
        )
        data = b"".join(frame.buffer for frame in frames)
        return cls(header=header, data=data)

    @property
    def frame_iterator(self):
        return iter(self.data)

    def iter_frames(self):
        """Iterate over individual Frame objects."""
        offset = 0
        for frame_header in self.header.headers:
            # Validate enough bytes remain for this frame
            if offset + frame_header.data_size_bytes > len(self.data):
                raise ValueError(
                    f"Insufficient data for frame at position "
                    f"({frame_header.STEM_row_in_scan}, {frame_header.STEM_x_position_in_row}). "
                    f"Expected {frame_header.data_size_bytes} bytes at offset {offset}, "
                    f"but only {len(self.data) - offset} bytes remaining."
                )
            frame_data = self.data[offset : offset + frame_header.data_size_bytes]
            yield Frame(header=frame_header, buffer=frame_data)

            offset += frame_header.data_size_bytes

        # Validate all bytes were consumed
        if offset != len(self.data):
            raise ValueError(f"Unused bytes detected: {len(self.data) - offset}")

    def get_frame_stack_with_positions(self) -> tuple[np.ndarray, np.ndarray]:
        """Return all dense frames in this batch as a single stacked array,
        plus a parallel array of the flat scan position each frame belongs to.

        :return: (frames, position_indices) where frames has shape
            (num_frames, *frame_shape) and position_indices has shape (num_frames,).
        """
        headers = self.header.headers
        frame_shape = self.header.frame_shape
        if not headers:
            return np.empty((0, *frame_shape), dtype=np.uint32), np.array(
                [], dtype=np.int32
            )

        dtype = headers[0].np_dtype
        frame_size = frame_shape[0] * frame_shape[1]

        all_values = np.frombuffer(self.data, dtype=dtype)
        frames = all_values.reshape((len(headers), *frame_shape))
        assert frames.size == all_values.size, (
            "Batch data size does not match expected frame count/shape "
            f"(frame_size={frame_size}, num_frames={len(headers)})"
        )

        positions = np.array(self.header.scan_positions_flat, dtype=np.int32)

        return frames, positions

    @classmethod
    def create_synthetic_batch(
        cls,
        scan_size: int = 128,
        frame_shape: tuple[int, int] = (256, 256),
        events_per_frame: int = 100,
    ) -> "BatchedFrames":
        """Create synthetic BatchedFrames (dense frames) for testing."""
        total_positions = scan_size * scan_size
        scan_number = 0

        # Generate headers for all frames
        headers = []
        all_frame_data = []

        np.random.seed(42)  # Reproducible results

        for position_idx in range(total_positions):
            row = position_idx // scan_size
            col = position_idx % scan_size

            # Generate a dense frame with a Gaussian-ish blob of counts
            # scattered around a (possibly drifting) center.
            center_x, center_y = frame_shape[0] // 2, frame_shape[1] // 2

            # Add some drift to make it more realistic
            drift_x = np.random.randint(-20, 20)
            drift_y = np.random.randint(-20, 20)

            events_x = np.random.normal(
                center_x + drift_x, 15, events_per_frame
            ).astype(np.int32)
            events_y = np.random.normal(
                center_y + drift_y, 15, events_per_frame
            ).astype(np.int32)

            events_x = np.clip(events_x, 0, frame_shape[0] - 1)
            events_y = np.clip(events_y, 0, frame_shape[1] - 1)

            frame_data = np.zeros(frame_shape, dtype=np.uint32)
            np.add.at(frame_data, (events_x, events_y), 1)

            header = FrameHeader(
                scan_number=scan_number,
                frame_number=position_idx,
                nSTEM_positions_per_row_m1=scan_size,
                nSTEM_rows_m1=scan_size,
                STEM_x_position_in_row=col,
                STEM_row_in_scan=row,
                modules=[0, 1, 2, 3],
                frame_shape=frame_shape,
                data_size_bytes=frame_data.nbytes,
            )

            headers.append(header)
            all_frame_data.append(frame_data)

        # Create batched header
        batch_size_bytes = sum(data.nbytes for data in all_frame_data)
        batched_header = BatchedFrameHeader(
            scan_number=scan_number,
            headers=headers,
            batch_size_bytes=batch_size_bytes,
        )

        # Combine all frame data
        combined_data = b"".join(data.tobytes() for data in all_frame_data)

        return cls(header=batched_header, data=combined_data)


# Type alias for compatibility
COMPartialHeader = BatchedFrameHeader


class COMPartial:
    def __init__(self, header: COMPartialHeader, array: np.ndarray):
        self.header = header
        self.array = array

    def to_bytes_message(self) -> BytesMessage:
        # serialize header
        header_json = msgspec.json.encode(self.header)

        # serialize np array
        bio = io.BytesIO()
        np.savez(bio, com=self.array)
        bio.seek(0)

        return BytesMessage(
            header=MessageHeader(
                subject=MessageSubject.BYTES,
                meta=header_json,
            ),
            data=bio.getvalue(),
        )

    @classmethod
    def from_bytes_message(cls, message: BytesMessage) -> "COMPartial":
        # Handle both bytes and dict
        if isinstance(message.header.meta, bytes):
            header = msgspec.json.decode(message.header.meta, type=COMPartialHeader)
        else:
            header = msgspec.convert(message.header.meta, COMPartialHeader)

        with io.BytesIO(message.data) as bio:
            npz = np.load(bio)
            array = npz["com"]
        return cls(header=header, array=array)


FlatScanIdx = int


class COMMeta(msgspec.Struct):
    scan_number: int
    scan_shape: tuple[int, int]
    frame_shape: tuple[int, int]
    headers: dict[FlatScanIdx, list[FrameHeader]] = msgspec.field(default_factory=dict)


class COM(COMPartial):
    def __init__(self, header: COMMeta, array: np.ndarray):
        self.header = header
        self.array = array

    @classmethod
    def from_bytes_message(cls, message: BytesMessage) -> "COM":
        # Handle both bytes and dict
        if isinstance(message.header.meta, bytes):
            header = msgspec.json.decode(message.header.meta, type=COMMeta)
        else:
            header = msgspec.convert(message.header.meta, COMMeta)

        with io.BytesIO(message.data) as bio:
            npz = np.load(bio)
            array = npz["com"]
        return cls(header=header, array=array)
