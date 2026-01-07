import pathlib
from typing import Any

import stempy.io
from distiller_streaming.emitter import BatchEmitter
from stempy.contrib import FileSuffix, get_scan_path

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()

# --- Operator State ---
source_dataset_path: pathlib.Path = pathlib.Path()
active_emitter: BatchEmitter | None = None
scan_id: int | None = None
current_scan_number: int = 1
current_scan_id: int | None = None
cached_sparse_array: tuple[int, Any] | None = None

data_dir = pathlib.Path(f"{DATA_DIRECTORY}/counted_data_dir")


@operator
def reader(
    inputs: BytesMessage | None, parameters: dict[str, Any], trigger=None
) -> BytesMessage | None:
    """Emit counted data batches only when explicitly triggered."""
    if trigger is None:
        return None

    global source_dataset_path, active_emitter, current_scan_number
    global current_scan_id, cached_sparse_array

    scan_id = parameters.get("scan_id", None)
    file_suffix = parameters.get("file_suffix", "STANDARD")
    batch_size_mb = parameters.get("batch_size_mb", 1.0)
    cache_last_file = parameters.get("cache_last_file", False)

    if not scan_id:
        raise ValueError("Parameter 'scan_id' is not set.")

    if not cache_last_file:
        cached_sparse_array = None

    if not file_suffix:
        raise ValueError("Parameter 'file_suffix' is not set.")

    if file_suffix == "STANDARD":
        file_suffix_enum = FileSuffix.STANDARD
    elif file_suffix == "CENTERED":
        file_suffix_enum = FileSuffix.CENTERED
    else:
        raise ValueError(f"Invalid file_suffix: {file_suffix}")

    if scan_id != current_scan_id:
        current_scan_id = scan_id
        current_scan_number = 1
        active_emitter = None
        cached_sparse_array = None
        logger.info(f"New scan_id received: {scan_id}. Resetting scan number to 1.")

    source_dataset_path, scan_num, scan_id = get_scan_path(data_dir, scan_id=scan_id, version=1, file_suffix=file_suffix_enum)

    # Load Dataset and create emitter if necessary
    if active_emitter is None:
        if not source_dataset_path.exists():
            logger.error(f"Source file not found: {source_dataset_path}")
            raise FileNotFoundError(f"Source file not found: {source_dataset_path}")
        try:
            logger.info(
                f"Loading dataset from: {source_dataset_path} for Scan {current_scan_number}"
            )
            cached_array = (
                cached_sparse_array[1]
                if cache_last_file
                and cached_sparse_array
                and cached_sparse_array[0] == scan_id
                else None
            )

            loaded_sparse_array = cached_array or stempy.io.load_electron_counts(
                source_dataset_path
            )

            if cache_last_file:
                cached_sparse_array = (scan_id, loaded_sparse_array) # type: ignore

            active_emitter = BatchEmitter(
                sparse_array=loaded_sparse_array,
                scan_number=current_scan_number,
                batch_size_mb=batch_size_mb,
            )
            logger.info(
                f"Emitter created for Scan {current_scan_number}. "
                f"Scan Shape: {loaded_sparse_array.scan_shape}, "
                f"Frame Shape: {loaded_sparse_array.frame_shape}, "
                f"Total Frames: {active_emitter.total_frames}. "
                f"Batch size: {batch_size_mb} MB)."
            )
        except Exception as e:
            logger.error(
                f"Failed to load dataset or create emitter from {source_dataset_path}: {e}"
            )
            active_emitter = None
            raise e

    # Process and Send Frames using Emitter
    if active_emitter:
        try:
            # This will send a BytesMessage containing a batch of frames
            result = active_emitter.get_next_batch_message()
            return result

        except StopIteration:
            scan_num = active_emitter.scan_number
            total_frames = active_emitter.total_frames
            logger.info(
                f"Finished sending all {total_frames} frames "
                f"for Scan Number: {scan_num} (Emitter exhausted)."
            )
            current_scan_number += 1
            active_emitter = None
            return None
        except Exception as e:
            logger.error(
                f"Error during frame emission for scan {active_emitter.scan_number}: {e}"
            )
            active_emitter = None
            raise e

    return None
