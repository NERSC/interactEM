import numpy as np

from distiller_streaming.models import (
    BatchedFrameHeader,
    BatchedFrames,
    Frame,
    FrameHeader,
    SparseArrayWithoutValidation,
)
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage

logger = get_logger()


class FrameAccumulator(SparseArrayWithoutValidation):
    """Accumulates sparse frames for a single scan, tracking which frames have been added."""

    PERCENTAGE_COMPLETE_THRESHOLD = 0.99

    def __init__(
        self,
        scan_number: int,
        scan_shape: tuple[int, int],
        frame_shape: tuple[int, int],
        dtype=np.uint32,
        **kwargs,
    ):
        self.scan_number = scan_number
        num_scan_positions = int(np.prod(scan_shape))

        # Initialize data storage
        initial_data = np.empty((num_scan_positions, 1), dtype=object)
        empty_array = np.array([], dtype=dtype)
        for i in range(num_scan_positions):
            initial_data[i, 0] = empty_array

        # Initialize parent
        if "dtype" not in kwargs:
            kwargs["dtype"] = dtype

        super().__init__(
            data=initial_data,
            scan_shape=scan_shape,
            frame_shape=frame_shape,
            **kwargs,
        )

        self._frames_per_position = {}
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
    def frames_added_indices(self) -> set[int]:
        """Set of scan position indices for which at least one frame has been added."""
        return set(self._frames_per_position.keys())

    def add_frame(self, frame: Frame) -> None:
        """
        Adds a sparse frame's data at the position specified in the header.
        If a frame already exists at this position, adds it as an additional frame
        rather than overwriting.

        Args:
            header: Frame header containing position information
            frame_data: NumPy array containing sparse frame data

        Raises:
            ValueError: If header dimensions don't match accumulator dimensions
            IndexError: If calculated position is out of bounds
        """
        header = frame.header
        # Determine which frame slot to use at this scan position
        # This should be based on how many frames we already have at this position
        flat_position = header.scan_position_flat
        frames_at_position = self._frames_per_position.get(flat_position, 0)
        frame_idx = frames_at_position  # Use the next available slot

        # Expand if needed based on local frame count at this position
        if frame_idx >= self.data.shape[1]:
            self.expand_frame_dimension_if_needed(frame_idx + 1)

        # Store the frame
        self.data[flat_position, frame_idx] = frame.array

        # Update tracking
        self._frames_per_position[flat_position] = frames_at_position + 1
        self._num_frames_added += 1

    @property
    def num_frames_added(self):
        return self._num_frames_added

    def add_batch(self, batch: BatchedFrames):
        headers = batch.header.headers
        self._total_batches_expected = batch.header.total_batches
        self._total_frames_expected = batch.header.total_frames

        # Extract all scan positions at once
        scan_positions = np.array([h.scan_position_flat for h in headers])

        # Group frames by scan position to determine required frame dimensions
        position_counts = {}
        position_frame_indices = {}

        for i, pos in enumerate(scan_positions):
            if pos not in position_counts:
                position_counts[pos] = 0
                position_frame_indices[pos] = []
            position_frame_indices[pos].append(i)
            position_counts[pos] += 1

        # Determine max frames needed at any position
        max_total_frames = max(
            self._frames_per_position.get(pos, 0) + count
            for pos, count in position_counts.items()
        )

        # Expand frame dimension once if needed
        if max_total_frames > self.data.shape[1]:
            self.expand_frame_dimension_if_needed(max_total_frames)

        # Pre-parse all frame data at once using numpy's advanced slicing
        offset = 0
        frame_arrays = []

        # Use numpy to efficiently slice the data buffer
        dtype = headers[0].np_dtype
        itemsize = dtype.itemsize

        for header in headers:
            # Validate enough bytes remain for this frame
            count = header.data_size_bytes // itemsize
            # Create view without copying data
            arr = np.frombuffer(batch.data, dtype=dtype, count=count, offset=offset)
            frame_arrays.append(arr)
            offset += header.data_size_bytes

        # Validate all bytes were consumed
        if offset != len(batch.data):
            raise ValueError(f"Unused bytes detected: {len(batch.data) - offset}")

        # Now assign all frames to their positions
        for pos, frame_indices in position_frame_indices.items():
            start_frame_idx = self._frames_per_position.get(pos, 0)

            for local_idx, global_idx in enumerate(frame_indices):
                frame_slot = start_frame_idx + local_idx
                self.data[pos, frame_slot] = frame_arrays[global_idx]

            # Update frame count for this position
            self._frames_per_position[pos] = start_frame_idx + len(frame_indices)
            # Increment total frame counter
            self._num_frames_added += len(frame_indices)

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

    def expand_frame_dimension_if_needed(self, required_frames: int) -> None:
        """
        Expand the frame dimension of the data array if needed to accommodate more frames.

        Args:
            required_frames: The number of frame slots required
        """
        current_frames = self.data.shape[1]

        if required_frames <= current_frames:
            return

        # Create new expanded array
        new_data = np.empty((self.data.shape[0], required_frames), dtype=object)

        # Copy existing data
        new_data[:, :current_frames] = self.data

        # Initialize new slots with empty arrays
        empty_array = np.array([], dtype=self.dtype)
        for i in range(self.data.shape[0]):
            for j in range(current_frames, required_frames):
                new_data[i, j] = empty_array

        # Replace data
        self.data = new_data
