
import numpy as np
from stempy.io import SparseArray

from distiller_streaming.models import BatchedFrameHeader, BatchedFrames, FrameHeader
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage

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
        self.frame_shape = tuple(int(x) for x in sparse_array.frame_shape)
        self.scan_shape = tuple(int(x) for x in sparse_array.scan_shape)
        self.batch_size_bytes = int(batch_size_mb * 1024 * 1024)

        # Calculate total frames considering multiple frames per position
        self.total_positions = int(sparse_array.num_scans)
        self.frames_per_position = (
            sparse_array.data.shape[1] if sparse_array.data.size > 0 else 1
        )
        self.total_frames = self.total_positions * self.frames_per_position

        self._scan_positions = [
            np.unravel_index(i, self.scan_shape) for i in range(self.total_positions)
        ]

        # Pre-compute integer scan positions for performance
        self._scan_positions_int = [
            (int(pos[0]), int(pos[1])) for pos in self._scan_positions
        ]

        # Indexes to track current position/frame
        self._position_index = 0
        self._frame_index = 0

        self._frames_emitted = 0
        self._messages_emitted = 0
        self._iterator = self._batch_generator()
        self._finished = False

        # Pre-compute template dictionary for frame headers (avoids dict unpacking overhead)
        self._frame_header_template = {
            "scan_number": self.scan_number,
            "nSTEM_positions_per_row_m1": self.scan_shape[1],
            "nSTEM_rows_m1": self.scan_shape[0],
            # TODO: add module info in stempy
            "modules": [0, 1, 2, 3],
            "frame_shape": self.frame_shape,
        }

        # Pre-compute position bytes - moves expensive computation out of hot loop
        self._position_bytes = []
        for position_idx in range(self.total_positions):
            position_frames = self._sparse_array.data[position_idx]
            position_bytes = sum(
                position_frames[frame_idx].nbytes
                for frame_idx in range(self.frames_per_position)
            )
            self._position_bytes.append(position_bytes)

        logger.debug(
            "FrameEmitter initialized for Scan %d with %d positions, "
            "%d frames per position (%d total frames), "
            "max batch size=%.1f MB (%d bytes).",
            self.scan_number,
            self.total_positions,
            self.frames_per_position,
            self.total_frames,
            batch_size_mb,
            self.batch_size_bytes,
        )

    def is_finished(self) -> bool:
        return self._finished

    def _batch_generator(self):
        batch_headers = []
        batch_data = []
        current_batch_bytes = 0

        # Process positions in scan order
        for position_idx in range(self.total_positions):
            scan_pos_int = self._scan_positions_int[position_idx]
            position_frames = self._sparse_array.data[position_idx]

            # Use pre-computed position bytes
            position_bytes = self._position_bytes[position_idx]

            # Check if adding this position would exceed batch size
            if (
                current_batch_bytes > 0
                and current_batch_bytes + position_bytes >= self.batch_size_bytes
            ):
                # Yield current batch before processing this position
                yield batch_headers, batch_data
                batch_headers = []
                batch_data = []
                current_batch_bytes = 0

            # Add all frames for this position
            for frame_idx in range(self.frames_per_position):
                frame_data = position_frames[frame_idx]
                ret_header = FrameHeader(
                    STEM_x_position_in_row=scan_pos_int[1],
                    STEM_row_in_scan=scan_pos_int[0],
                    data_size_bytes=frame_data.nbytes,
                    **self._frame_header_template,
                )
                batch_headers.append(ret_header)
                batch_data.append(frame_data)
                current_batch_bytes += frame_data.nbytes

        # Yield any remaining frames
        if batch_headers:
            yield batch_headers, batch_data

        logger.info(
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
            headers, data = next(self._iterator)
            total_bytes = sum(arr.nbytes for arr in data)
            batched_header = BatchedFrameHeader(
                scan_number=self.scan_number,
                headers=headers,
                batch_size_bytes=total_bytes,
            )

            self._frames_emitted += len(headers)
            self._messages_emitted += 1
            logger.debug(
                "FrameEmitter for Scan %d: Emitted %.2f MB for %d frames.",
                self.scan_number,
                total_bytes / 1024 / 1024,
                len(headers),
            )
            return BatchedFrames.from_np_arrays(
                header=batched_header, arrays=data
            ).to_bytes_message()
        except StopIteration:
            self._finished = True
            logger.info(
                f"FrameEmitter for Scan {self.scan_number}: Finished after emitting "
                f"{self._frames_emitted} frames in {self._messages_emitted} messages."
            )
            raise
