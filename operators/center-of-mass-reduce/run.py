from typing import Any

import numpy as np
from distiller_streaming.models import COM, COMMeta, COMPartial, FrameHeader

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import operator

logger = get_logger()


class COMCache:
    """Helper to collect partial COM arrays and metadata for a single scan."""

    def __init__(self, com_partial: COMPartial):
        header = com_partial.header
        self.scan_shape = header.scan_shape
        self.frame_shape = header.frame_shape

        # store COM as (2, rows, cols) with NaN init
        self._com = np.full((2, *self.scan_shape), np.nan, dtype=np.float32)

        self.received_positions: set[int] = set()
        self._headers: dict[int, list[FrameHeader]] = {
            i: [] for i in range(int(np.prod(self.scan_shape)))
        }
        self._counts = np.zeros(self.scan_shape, dtype=np.int32)

        # Track how many messages we’ve processed
        self.message_count = 0

    def add_batch(self, com_partial: COMPartial) -> None:
        header = com_partial.header
        com = com_partial.array
        if com_partial.array.shape != self._com.shape:
            raise ValueError(
                f"Shape mismatch: got {com_partial.array.shape}, expected {self._com.shape}"
            )

        self.message_count += 1

        for h in header.headers:
            flat_idx = np.atleast_1d(h.scan_position_flat)  # ensure array
            y, x = np.unravel_index(flat_idx, self.scan_shape)

            for axis in range(2):
                vals = com[axis, y, x]
                mask = ~np.isnan(vals)
                if np.any(mask):
                    # Fill NaNs or accumulate
                    target = self._com[axis, y[mask], x[mask]]
                    nan_mask = np.isnan(target)
                    # Where target is NaN → set directly
                    target[nan_mask] = vals[mask][nan_mask]
                    # Where target already has a value → accumulate
                    target[~nan_mask] += vals[mask][~nan_mask]
                    self._com[axis, y[mask], x[mask]] = target

            # Increment counts for averaging
            self._counts[y, x] += 1
            self.received_positions.update(flat_idx.tolist())
            for idx in flat_idx:
                self._headers[int(idx)].append(h)

    def is_complete(self) -> bool:
        return len(self.received_positions) == int(np.prod(self.scan_shape))

    def finalize(self) -> np.ndarray:
        """Return averaged COM array with NaNs filled."""
        com = self._com.copy()

        # Average accumulated values by counts
        counts = self._counts.copy()
        counts[counts == 0] = 1
        for axis in range(2):
            com[axis] /= counts

        # Compute one mean per axis (global mean)
        means = np.nanmean(com, axis=(1, 2))  # shape (2,)
        means = np.nan_to_num(means, nan=0.0)

        # Fill NaNs with that per-axis mean
        for axis in range(2):
            nan_mask = np.isnan(com[axis])
            if nan_mask.any():
                com[axis][nan_mask] = means[axis]

        return com


# in-memory store of scan accumulators by scan_number
scan_store: dict[int, COMCache] = {}


@operator
def com_reduce(inputs: BytesMessage | None, parameters: dict[str, Any]) -> BytesMessage | None:
    global scan_store

    if not inputs:
        logger.warning("No input to com_reduce")
        return None

    com_partial = COMPartial.from_bytes_message(inputs)
    header = com_partial.header

    scan_number = header.scan_number
    scan_shape = header.scan_shape
    frame_shape = header.frame_shape
    emit_every = int(parameters.get("emit_every", 100))

    accumulator = scan_store.get(scan_number)
    if accumulator is None:
        accumulator = COMCache(com_partial)
        scan_store[scan_number] = accumulator

    accumulator.add_batch(com_partial)

    should_emit = (
        accumulator.is_complete() or
        (emit_every > 0 and accumulator.message_count % emit_every == 0)
    )

    if not should_emit:
        return None

    combined = accumulator.finalize()
    out_meta = COMMeta(
        scan_number=scan_number,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        headers=accumulator._headers
    )

    out = COM(header=out_meta, array=combined).to_bytes_message()

    if accumulator.is_complete():
        logger.info(f"COM reduction complete for scan {scan_number}")
        del scan_store[scan_number]

    return out
