from collections.abc import Generator

import numpy as np
from stempy.io import SparseArray

from distiller_streaming.models import FrameHeader
from distiller_streaming.util import create_batch_message
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject

logger = get_logger()


class FrameEmitter:
    """
    Manages iterating through frames of a SparseArray and generating BytesMessages for each frame.
    Supports batching multiple frames into a single message, where the batch limit is defined
    by a maximum total data size (in MB) rather than a fixed number of frames.
    """

    def __init__(
        self, sparse_array: SparseArray, scan_number: int, batch_size_mb: float = 1.0
    ):
        if not isinstance(sparse_array, SparseArray):
            raise TypeError("sparse_array must be a stempy.io.SparseArray")
        if not isinstance(scan_number, int):
            raise TypeError("scan_number must be an integer")
        if batch_size_mb <= 0:
            raise ValueError("batch_size_mb must be positive")

        self._sparse_array = sparse_array
        self.scan_number = scan_number
        self.batch_size_bytes = int(batch_size_mb * 1024 * 1024)

        # Calculate total frames considering multiple frames per position
        self.total_positions = int(sparse_array.num_scans)
        self.frames_per_position = (
            sparse_array.data.shape[1] if sparse_array.data.size > 0 else 1
        )
        self.total_frames = self.total_positions * self.frames_per_position

        # Indexes to track current position/frame
        self._position_index = 0
        self._frame_index = 0

        self._frames_emitted = 0
        self._messages_emitted = 0
        self._iterator = self._batched_frame_generator()
        self._finished = False

        logger.debug(
            f"FrameEmitter initialized for Scan {self.scan_number} with {self.total_positions} positions, "
            f"{self.frames_per_position} frames per position ({self.total_frames} total frames), "
            f"max batch size={batch_size_mb} MB ({self.batch_size_bytes} bytes)."
        )

    def is_finished(self) -> bool:
        return self._finished

    def _create_frame_header(
        self,
        scan_position_index: int,
        frame_index: int = 0,
    ) -> tuple[FrameHeader, np.ndarray]:
        """
        Internal helper to create frame header and data.

        Returns:
            Tuple of (FrameHeader, frame_data_bytes)
        """
        sparse_array = self._sparse_array

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

        # Metadata and Header Creation
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
        scan_position = np.unravel_index(scan_position_index, scan_shape)

        header = FrameHeader(
            scan_number=self.scan_number,
            frame_number=frame_index if self.frames_per_position > 1 else None,
            nSTEM_positions_per_row_m1=scan_shape[1],
            nSTEM_rows_m1=scan_shape[0],
            STEM_x_position_in_row=int(scan_position[1]),
            STEM_row_in_scan=int(scan_position[0]),
            modules=sparse_array.metadata.get("modules", [0, 1, 2, 3]),
            frame_shape=frame_shape,
            data_size_bytes=frame_data_sparse.nbytes,
        )

        return header, frame_data_sparse

    def _create_frame_message(
        self,
        scan_position_index: int,
        frame_index: int = 0,
    ) -> BytesMessage:
        header, arr = self._create_frame_header(scan_position_index, frame_index)
        return BytesMessage(
            header=MessageHeader(
                subject=MessageSubject.BYTES, meta=header.model_dump()
            ),
            data=arr.tobytes(),
        )

    def _batched_frame_generator(self) -> Generator[BytesMessage, None, None]:
        """
        Internal generator that yields batched BytesMessages based on total byte size.
        """
        logger.debug(
            f"FrameEmitter batched generator started for Scan {self.scan_number} "
            f"with max batch size={self.batch_size_bytes} bytes."
        )

        batch_headers = []
        batch_data = []
        current_batch_bytes = 0

        for position_idx in range(self.total_positions):
            for frame_idx in range(self.frames_per_position):
                try:
                    header_data = self._create_frame_header(position_idx, frame_idx)
                    header, data = header_data

                    batch_headers.append(header)
                    batch_data.append(data)
                    current_batch_bytes += len(data)

                    self._position_index = position_idx
                    self._frame_index = frame_idx
                    self._frames_emitted += 1

                    # Yield batch if size limit reached or exceeded
                    if current_batch_bytes >= self.batch_size_bytes:
                        message = create_batch_message(batch_headers, batch_data)
                        self._messages_emitted += 1
                        yield message
                        batch_headers = []
                        batch_data = []
                        current_batch_bytes = 0

                except Exception as e:
                    logger.error(
                        f"Scan {self.scan_number}: Unexpected error at position {position_idx}, frame {frame_idx}: {str(e)}"
                    )
                    raise

        # Yield any remaining frames
        if batch_headers:
            message = create_batch_message(batch_headers, batch_data)
            self._messages_emitted += 1
            yield message

        logger.debug(
            f"FrameEmitter batched generator finished for Scan {self.scan_number}. "
            f"Emitted {self._frames_emitted} frames in {self._messages_emitted} messages."
        )

    def get_next_frame_message(self) -> BytesMessage:
        """
        Gets the next valid frame message from the internal generator.
        May return a single frame or batched frames depending on the configured size limit.
        """
        if self._finished:
            raise StopIteration("FrameEmitter is finished.")

        try:
            return next(self._iterator)
        except StopIteration:
            self._finished = True
            logger.debug(
                f"FrameEmitter for Scan {self.scan_number}: Finished after emitting "
                f"{self._frames_emitted} frames in {self._messages_emitted} messages."
            )
            raise
