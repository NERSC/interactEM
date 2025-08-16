import numpy as np
from stempy.io import SparseArray

from distiller_streaming.models import BatchedFrameHeader, FrameHeader
from distiller_streaming.util import (
    extract_header_frame_pairs,
    validate_message,
)
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage

logger = get_logger()


class FrameAccumulator(SparseArray):
    """Accumulates sparse frames for a single scan, tracking which frames have been added."""

    def __init__(
        self,
        scan_number: int,
        scan_shape: tuple[int, int],
        frame_shape: tuple[int, int],
        dtype=np.uint32,
        **kwargs,
    ):
        # Validate shapes
        if not isinstance(scan_shape, tuple) or len(scan_shape) != 2:
            raise ValueError(
                f"Invalid scan_shape: {scan_shape}. Must be a tuple of length 2."
            )
        if not isinstance(frame_shape, tuple) or len(frame_shape) != 2:
            raise ValueError(
                f"Invalid frame_shape: {frame_shape}. Must be a tuple of length 2."
            )

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
        self.num_frames_added = 0

        logger.info(
            f"Initialized FrameAccumulator for scan {scan_number} with shape {scan_shape}x{frame_shape}"
        )

    @classmethod
    def from_message(cls, message: BytesMessage):
        header, _ = validate_message(message)
        accumulator = cls(
            scan_number=header.scan_number,
            scan_shape=header.scan_shape,
            frame_shape=header.frame_shape,
        )
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

    def add_frame(self, header: FrameHeader, frame_data: np.ndarray) -> None:
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
        if header.scan_number != self.scan_number:
            raise ValueError(
                f"Scan number mismatch: header {header.scan_number}, "
                f"accumulator {self.scan_number}"
            )

        # Validate scan shape matches header
        if (header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1) != self.scan_shape:
            raise ValueError(
                f"Scan {self.scan_number}: Mismatch between header scan shape "
                f"{(header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1)} and "
                f"accumulator scan shape {self.scan_shape}"
            )

        # Validate frame shape matches header
        if header.frame_shape != self.frame_shape:
            raise ValueError(
                f"Scan {self.scan_number}: Mismatch between header frame shape "
                f"{header.frame_shape} and accumulator frame shape {self.frame_shape}"
            )
        # Determine which frame slot to use at this scan position
        # This should be based on how many frames we already have at this position
        flat_position = header.scan_position_flat
        frames_at_position = self._frames_per_position.get(flat_position, 0)
        frame_idx = frames_at_position  # Use the next available slot

        # Expand if needed based on local frame count at this position
        if frame_idx >= self.data.shape[1]:
            self.expand_frame_dimension_if_needed(frame_idx + 1)

        # Store the frame
        self.data[flat_position, frame_idx] = frame_data

        # Update tracking
        self._frames_per_position[flat_position] = frames_at_position + 1
        self.num_frames_added += 1

    def add_message(self, message: BytesMessage) -> None:
        """
        Process a BytesMessage that may contain either a single frame or batched frames.

        Args:
            message: BytesMessage containing frame data

        Raises:
            ValueError: If message format is invalid or data doesn't match headers
        """
        meta, data = validate_message(message)

        # Check if this is a batched message
        if isinstance(meta, BatchedFrameHeader):
            self._process_batched_frames(meta, data)
        elif isinstance(meta, FrameHeader):
            self._process_single_frame(meta, data)

    def _process_single_frame(self, header: FrameHeader, data: bytes) -> None:
        frame_data = np.frombuffer(
            data,
            dtype=header.np_dtype,
        )
        self.add_frame(header, frame_data)

    def _process_batched_frames(
        self, batched_header: BatchedFrameHeader, data: bytes
    ) -> None:
        # Verify total size matches
        if len(data) != batched_header.total_batch_size_bytes:
            raise ValueError(
                f"Data size mismatch: expected {batched_header.total_batch_size_bytes} bytes, "
                f"got {len(data)} bytes"
            )

        pairs = extract_header_frame_pairs(data, batched_header.headers)

        # Add each frame
        for header, frame_data in pairs:
            self.add_frame(header, frame_data)

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
