import numpy as np

from distiller_streaming_dense.models import (
    BatchedFrameHeader,
    BatchedFrames,
    Frame,
    FrameHeader,
)
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage

logger = get_logger()


class FrameAccumulator:
    """Accumulates dense frames for a single scan, tracking which positions
    have received a frame.

    Backing storage is a single dense 4D array of shape
    (*scan_shape, *frame_shape) -- one frame per scan position.
    """

    PERCENTAGE_COMPLETE_THRESHOLD = 0.99

    def __init__(
        self,
        scan_number: int,
        scan_shape: tuple[int, int],
        frame_shape: tuple[int, int],
        dtype=np.uint32,
        metadata: dict | None = None,
    ):
        self.scan_number = scan_number
        self.scan_shape = scan_shape
        self.frame_shape = frame_shape
        self.dtype = dtype
        self.metadata = metadata if metadata is not None else {}

        self.data = np.zeros((*scan_shape, *frame_shape), dtype=dtype)

        self._frames_added: set[int] = set()
        self.num_batches_added = 0
        self._num_frames_added = 0
        self._total_batches_expected: int | None = None
        self._total_frames_expected: int | None = None

        logger.info(
            f"Initialized FrameAccumulator for scan {scan_number} with shape {scan_shape}x{frame_shape}"
        )

    @classmethod
    def from_message(cls, message: BytesMessage, add: bool = False):
        batch = BatchedFrames.from_bytes_message(message)
        accumulator = cls(
            scan_number=batch.header.scan_number,
            scan_shape=batch.header.scan_shape,
            frame_shape=batch.header.frame_shape,
        )
        if not add:
            return accumulator

        accumulator.add_batch(batch)
        return accumulator

    @classmethod
    def from_batch(cls, batch: BatchedFrames):
        accumulator = cls(
            scan_number=batch.header.scan_number,
            scan_shape=batch.header.scan_shape,
            frame_shape=batch.header.frame_shape,
        )
        accumulator.add_batch(batch)
        accumulator._total_batches_expected = batch.header.total_batches
        accumulator._total_frames_expected = batch.header.total_frames
        return accumulator

    @classmethod
    def from_header(cls, header: FrameHeader | BatchedFrameHeader):
        accumulator = cls(
            scan_number=header.scan_number,
            scan_shape=header.scan_shape,
            frame_shape=header.frame_shape,
        )
        return accumulator

    @property
    def num_scans(self) -> int:
        return int(np.prod(self.scan_shape))

    @property
    def shape(self) -> tuple[int, ...]:
        return (*self.scan_shape, *self.frame_shape)

    @property
    def scan_axes(self) -> tuple[int, ...]:
        return tuple(range(len(self.scan_shape)))

    @property
    def frame_axes(self) -> tuple[int, ...]:
        return tuple(range(len(self.scan_shape), len(self.shape)))

    @property
    def data_flat(self) -> np.ndarray:
        """View of data with scan axes flattened: (num_scans, *frame_shape)."""
        return self.data.reshape(self.num_scans, *self.frame_shape)

    def ravel_scans(self) -> None:
        """Flatten the scan dimensions of this accumulator in place."""
        self.data = self.data_flat
        self.scan_shape = (self.num_scans,)

    def sum(self, axis=None, dtype=None):
        return np.sum(self.data, axis=axis, dtype=dtype)

    @property
    def frames_added_indices(self) -> set[int]:
        """Set of flat scan position indices that have received a frame."""
        return set(self._frames_added)

    def add_frame(self, frame: Frame) -> None:
        """Writes a dense frame's data at the position specified in the header.

        If a frame already exists at this position, it is overwritten -- there
        is only one frame slot per scan position.
        """
        header = frame.header
        flat_position = header.scan_position_flat

        self.data_flat[flat_position] = frame.array

        self._frames_added.add(flat_position)
        self._num_frames_added += 1

    @property
    def num_frames_added(self):
        return self._num_frames_added

    def add_batch(self, batch: BatchedFrames):
        self._total_batches_expected = batch.header.total_batches
        self._total_frames_expected = batch.header.total_frames

        frames, positions = batch.get_frame_stack_with_positions()

        data_flat = self.data_flat
        for pos, frame in zip(positions, frames, strict=True):
            data_flat[int(pos)] = frame
            self._frames_added.add(int(pos))

        self._num_frames_added += len(positions)

    def add_message(self, message: BytesMessage) -> None:
        batch = BatchedFrames.from_bytes_message(message)
        self.add_batch(batch)
        self.num_batches_added += 1

    @property
    def finished(self) -> bool:
        if self._total_frames_expected is None:
            return False
        return (
            self.num_frames_added
            >= self.PERCENTAGE_COMPLETE_THRESHOLD * self._total_frames_expected
        )

    def clear(self) -> None:
        """Clear stored frames and reset counters so the accumulator releases memory."""
        self.data = np.zeros((*self.scan_shape, *self.frame_shape), dtype=self.dtype)
        self._frames_added.clear()
        self.num_batches_added = 0
        self._num_frames_added = 0
        self._total_batches_expected = None
        self._total_frames_expected = None
