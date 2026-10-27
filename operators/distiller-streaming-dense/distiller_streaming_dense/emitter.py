import numpy as np

from distiller_streaming_dense.accumulator import FrameAccumulator
from distiller_streaming_dense.models import (
    BatchedFrameHeader,
    BatchedFrames,
    FrameHeader,
    NumpyDtype,
)
from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage

logger = get_logger()


class BatchEmitter:
    """
    Manages iterating through dense frames of a FrameAccumulator and
    generating BytesMessages for each frame. Supports batching multiple
    frames into a single message, where the batch limit is defined by a
    maximum total data size (in MB) rather than a fixed number of frames.
    """

    def __init__(
        self,
        frame_array: FrameAccumulator,
        scan_number: int,
        batch_size_mb: float = 1.0,
    ):
        if not isinstance(frame_array, FrameAccumulator):
            raise TypeError("frame_array must be a FrameAccumulator")
        if not isinstance(scan_number, int):
            raise TypeError("scan_number must be an integer")
        if batch_size_mb <= 0:
            raise ValueError("batch_size_mb must be positive")

        self._frame_array = frame_array
        self.scan_number = scan_number
        self.frame_shape = tuple(int(x) for x in frame_array.frame_shape)
        self.scan_shape = tuple(int(x) for x in frame_array.scan_shape)
        self.batch_size_bytes = int(batch_size_mb * 1024 * 1024)

        self.total_positions = int(frame_array.num_scans)
        self.total_frames = self.total_positions

        self._scan_positions = [
            np.unravel_index(i, self.scan_shape) for i in range(self.total_positions)
        ]

        # Pre-compute integer scan positions for performance
        self._scan_positions_int = [
            (int(pos[0]), int(pos[1])) for pos in self._scan_positions
        ]

        self._frames_emitted = 0
        self._messages_emitted = 0
        self._iterator = self._batch_generator()
        self.finished = False

        # Pre-compute template dictionary for frame headers (avoids dict unpacking overhead)
        try:
            wire_dtype = NumpyDtype(np.dtype(frame_array.dtype).name)
        except ValueError:
            raise ValueError(
                f"dtype '{frame_array.dtype}' is not supported on the wire "
                f"(must be one of {[d.value for d in NumpyDtype]})"
            )

        self._frame_header_template = {
            "scan_number": self.scan_number,
            "nSTEM_positions_per_row_m1": self.scan_shape[1],
            "nSTEM_rows_m1": self.scan_shape[0],
            # TODO: add module info
            "modules": [0, 1, 2, 3],
            "frame_shape": self.frame_shape,
            "dtype": wire_dtype,
        }

        # Pre-compute position bytes - moves expensive computation out of hot loop
        data_flat = self._frame_array.data_flat
        self._position_bytes = [
            data_flat[position_idx].nbytes for position_idx in range(self.total_positions)
        ]

        self.total_batches, self.total_frames_expected = (
            self._calculate_batch_and_frame_totals()
        )

        logger.debug(
            "BatchEmitter initialized for Scan %d with %d positions, "
            "%d total frames, "
            "max batch size=%.1f MB (%d bytes), "
            "estimated %d batches.",
            self.scan_number,
            self.total_positions,
            self.total_frames,
            batch_size_mb,
            self.batch_size_bytes,
            self.total_batches,
        )

    def _calculate_batch_and_frame_totals(self) -> tuple[int, int]:
        if not self._position_bytes:
            return 0, 0

        batch_count = 0
        frame_count = 0
        current_batch_bytes = 0

        for position_bytes in self._position_bytes:
            # Check if adding this position would exceed batch size
            if (
                current_batch_bytes > 0
                and current_batch_bytes + position_bytes >= self.batch_size_bytes
            ):
                # Would exceed batch size, so finish current batch
                batch_count += 1
                current_batch_bytes = position_bytes
            else:
                # Add to current batch
                current_batch_bytes += position_bytes

            frame_count += 1

        # Count the final batch if it has any data
        if current_batch_bytes > 0:
            batch_count += 1

        return batch_count, frame_count

    def _batch_generator(self):
        batch_headers = []
        batch_data = []
        current_batch_bytes = 0
        current_batch_index = 0

        data_flat = self._frame_array.data_flat

        # Process positions in scan order
        for position_idx in range(self.total_positions):
            scan_pos_int = self._scan_positions_int[position_idx]
            frame_data = data_flat[position_idx]

            # Use pre-computed position bytes
            position_bytes = self._position_bytes[position_idx]

            # Check if adding this position would exceed batch size
            if (
                current_batch_bytes > 0
                and current_batch_bytes + position_bytes >= self.batch_size_bytes
            ):
                # Yield current batch before processing this position
                yield batch_headers, batch_data, current_batch_index
                batch_headers = []
                batch_data = []
                current_batch_bytes = 0
                current_batch_index += 1

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
            yield batch_headers, batch_data, current_batch_index

        logger.info(
            f"BatchEmitter batched generator finished for Scan {self.scan_number}. "
            f"Emitted {self._frames_emitted} frames in {self._messages_emitted} messages."
        )

    def get_next_batch_message(self) -> BytesMessage:
        """
        Gets the next batch of frames as a BytesMessage.
        """
        if self.finished:
            raise StopIteration("BatchEmitter is finished.")

        try:
            headers, data, batch_index = next(self._iterator)
            total_bytes = sum(arr.nbytes for arr in data)
            batched_header = BatchedFrameHeader(
                scan_number=self.scan_number,
                headers=headers,
                batch_size_bytes=total_bytes,
                total_batches=self.total_batches,
                total_frames=self.total_frames_expected,
                current_batch_index=batch_index,
            )

            self._frames_emitted += len(headers)
            self._messages_emitted += 1
            logger.debug(
                "BatchEmitter for Scan %d: Emitted %.2f MB for %d frames.",
                self.scan_number,
                total_bytes / 1024 / 1024,
                len(headers),
            )
            return BatchedFrames.from_np_arrays(
                header=batched_header, arrays=data
            ).to_bytes_message()
        except StopIteration:
            self.finished = True
            logger.info(
                f"BatchEmitter for Scan {self.scan_number}: Finished after emitting "
                f"{self._frames_emitted} frames in {self._messages_emitted} messages."
            )
            raise
