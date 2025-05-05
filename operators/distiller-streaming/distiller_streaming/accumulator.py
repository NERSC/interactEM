import numpy as np
from stempy.io import SparseArray

from distiller_streaming.models import FrameHeader
from interactem.core.logger import get_logger

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
        empty_array = np.array([], dtype=np.uint32)
        for i in range(num_scan_positions):
            initial_data[i, 0] = empty_array

        # Initialize parent
        super().__init__(
            data=initial_data,
            scan_shape=scan_shape,
            frame_shape=frame_shape,
            dtype=dtype,
            **kwargs,
        )

        self._frames_per_position = {}
        self.num_frames_added = 0

        logger.info(
            f"Initialized FrameAccumulator for scan {scan_number} with shape {scan_shape}x{frame_shape}"
        )

    @property
    def frames_added_indices(self) -> set[int]:
        """Set of scan position indices for which at least one frame has been added."""
        return set(self._frames_per_position.keys())

    @property
    def num_positions_with_frames(self) -> int:
        """Number of scan positions that have at least one frame."""
        return len(self._frames_per_position)

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

        # Calculate flat index from 2D position
        scan_position_flat = (
            header.STEM_row_in_scan * header.nSTEM_positions_per_row_m1
            + header.STEM_x_position_in_row
        )

        # Ensure position is within bounds
        if not (0 <= scan_position_flat < self.num_scans):
            raise IndexError(
                f"Invalid scan position {scan_position_flat}. Max expected: {self.num_scans - 1}"
            )

        # Count frames already at this position
        frames_at_position = self._frames_per_position.get(scan_position_flat, 0)

        # If this is the first frame at this position
        if frames_at_position == 0:
            # Store at index 0
            self.data[scan_position_flat, 0] = frame_data
        else:
            current_frames_dim = self.data.shape[1]

            # Check if we need to expand the data array
            if frames_at_position >= current_frames_dim:
                # Increase the frame dimension by exactly one
                new_frame_dim = frames_at_position + 1
                new_shape = (self.data.shape[0], new_frame_dim)
                new_data = np.empty(new_shape, dtype=object)

                # Copy existing data
                new_data[:, :current_frames_dim] = self.data

                # Initialize remaining slots with empty arrays
                empty_array = np.array([], dtype=self.dtype)
                for i in range(self.data.shape[0]):
                    for j in range(current_frames_dim, new_frame_dim):
                        new_data[i, j] = empty_array

                # Replace data with expanded array
                self.data = new_data

            # Store the new frame at the next available index
            self.data[scan_position_flat, frames_at_position] = frame_data

        # Update tracking information
        self._frames_per_position[scan_position_flat] = frames_at_position + 1
        self.num_frames_added += 1
