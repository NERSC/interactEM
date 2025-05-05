from collections.abc import Generator

import numpy as np
from stempy.io import SparseArray

from distiller_streaming.models import FrameHeader
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject

logger = get_logger()

class FrameEmitter:
    """
    Manages iterating through frames of a SparseArray and generating BytesMessages for each frame.
    """

    def __init__(self, sparse_array: SparseArray, scan_number: int):
        if not isinstance(sparse_array, SparseArray):
            raise TypeError("sparse_array must be a stempy.io.SparseArray")
        if not isinstance(scan_number, int):
            raise TypeError("scan_number must be an integer")

        self._sparse_array = sparse_array
        self.scan_number = scan_number

        # Calculate total frames considering multiple frames per position
        self.total_positions = int(sparse_array.num_scans)
        self.frames_per_position = (
            sparse_array.data.shape[1] if sparse_array.data.size > 0 else 1
        )
        self.total_frames = self.total_positions * self.frames_per_position

        # Indexes to track current position/frame (helps with test)
        self._position_index = 0
        self._frame_index = 0

        self._frames_emitted = 0
        self._iterator = self._frame_generator()
        self._finished = False

        logger.debug(
            f"FrameEmitter initialized for Scan {self.scan_number} with {self.total_positions} positions, "
            f"{self.frames_per_position} frames per position ({self.total_frames} total frames)."
        )

    def is_finished(self) -> bool:
        return self._finished

    def _create_frame_message(
        self,
        scan_position_index: int,
        frame_index: int = 0,
    ) -> BytesMessage:
        """
        Internal helper to create a single frame message.
        Raises exceptions on failure instead of returning None.

        Args:
            scan_position_index: Flattened index of the scan position
            frame_index: Index of frame at this position (default: 0)

        Returns:
            BytesMessage for the frame data
        """
        sparse_array = self._sparse_array
        current_scan_number = self.scan_number

        # Bounds check
        if scan_position_index < 0 or scan_position_index >= self.total_positions:
            raise IndexError(f"Invalid scan_position_index ({scan_position_index}).")

        # Check frame index bounds
        if frame_index < 0 or frame_index >= sparse_array.data.shape[1]:
            raise IndexError(
                f"Invalid frame_index {frame_index} for position {scan_position_index}. "
                f"Valid range: 0 to {sparse_array.data.shape[1] - 1}"
            )

        # --- Frame Data Extraction ---
        frame_data_sparse = sparse_array.data[scan_position_index, frame_index]

        # Validate frame data exists and is the right type
        if frame_data_sparse is None:
            raise ValueError(
                f"No data found for position {scan_position_index}, frame {frame_index}"
            )

        if not isinstance(frame_data_sparse, np.ndarray):
            raise TypeError(
                f"Expected ndarray for position {scan_position_index}, frame {frame_index}, "
                f"got {type(frame_data_sparse)}"
            )

        # Ensure data is uint32
        if frame_data_sparse.dtype != np.uint32:
            frame_data_sparse = frame_data_sparse.astype(np.uint32, copy=False)

        frame_data_bytes = frame_data_sparse.tobytes()

        # --- Metadata and Header Creation ---
        scan_shape = sparse_array.scan_shape
        if not scan_shape or len(scan_shape) != 2:
            raise ValueError(
                f"Invalid scan_shape {scan_shape} in sparse_array for frame {scan_position_index}."
            )

        frame_shape = sparse_array.frame_shape
        if not frame_shape or len(frame_shape) != 2:
            raise ValueError(
                f"Invalid frame_shape {frame_shape} in sparse_array for frame {scan_position_index}."
            )

        # Calculate 2D position
        position_2d = np.unravel_index(scan_position_index, scan_shape)

        header_meta = FrameHeader(
            scan_number=current_scan_number,
            nSTEM_positions_per_row_m1=scan_shape[1],
            nSTEM_rows_m1=scan_shape[0],
            STEM_x_position_in_row=int(position_2d[1]),
            STEM_row_in_scan=int(position_2d[0]),
            modules=sparse_array.metadata.get("modules", [0, 1, 2, 3]),
            frame_shape=frame_shape,
        )

        # Create BytesMessage
        output_message = BytesMessage(
            header=MessageHeader(
                subject=MessageSubject.BYTES, meta=header_meta.model_dump()
            ),
            data=frame_data_bytes,
        )
        return output_message

    def _frame_generator(self) -> Generator[BytesMessage, None, None]:
        """
        Internal generator that yields valid BytesMessages.
        Handles multiple frames per position and error skipping.
        """
        logger.debug(
            f"FrameEmitter internal generator started for Scan {self.scan_number}."
        )

        for position_idx in range(self.total_positions):
            for frame_idx in range(self.frames_per_position):
                try:
                    message = self._create_frame_message(
                        scan_position_index=position_idx, frame_index=frame_idx
                    )
                    self._position_index = position_idx
                    self._frame_index = frame_idx
                    self._frames_emitted += 1
                    yield message

                except Exception as e:
                    logger.error(
                        f"Scan {self.scan_number}: Unexpected error at position {position_idx}, frame {frame_idx}: {str(e)}"
                    )
                    raise

        logger.debug(
            f"FrameEmitter internal generator finished for Scan {self.scan_number}. "
            f"Emitted {self._frames_emitted}/{self.total_frames} frames."
        )

    def get_next_frame_message(self) -> BytesMessage:
        """
        Gets the next valid frame message from the internal generator.

        Returns:
            - BytesMessage: The next successfully processed frame message.

        Raises:
            - StopIteration: If all frames have already been sent or skipped due to errors.
            - Exception: Any unexpected exceptions during frame processing will bubble up.
        """
        if self._finished:
            raise StopIteration("FrameEmitter is finished.")

        try:
            next_item = next(self._iterator)
            return next_item
        except StopIteration:
            self._finished = True
            logger.debug(
                f"FrameEmitter for Scan {self.scan_number}: Finished after emitting {self._frames_emitted} frames."
            )
            raise
