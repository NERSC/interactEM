import pathlib
import time
from typing import Any

import stempy.io
from distiller_pipeline.emitter import FrameEmitter

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()

# --- Operator State ---
source_dataset_path: pathlib.Path = pathlib.Path()
active_emitter: FrameEmitter | None = None
current_scan_number: int = 1
current_filename: str | None = None

data_dir = pathlib.Path(f"{DATA_DIRECTORY}/raw_data_dir")


@operator
def reader(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global source_dataset_path, active_emitter, current_scan_number
    global current_filename

    # Handle Parameter Updates
    filename = parameters.get("filename", None)
    frame_delay_ns = float(parameters.get("frame_delay_ns", 1000))
    frame_delay_sec = frame_delay_ns / 1_000_000_000.0 if frame_delay_ns > 0 else 0

    if not filename:
        raise ValueError("Filename parameter 'filename' is not set.")

    if filename != current_filename:
        current_filename = filename
        current_scan_number = 1
        active_emitter = None
        logger.info(f"New filename received: {filename}. Resetting scan number to 1.")

    source_dataset_path = data_dir / filename

    # Load Dataset and Create Emitter if Necessary
    if active_emitter is None:
        if not source_dataset_path.exists():
            logger.error(f"Source file not found: {source_dataset_path}")
            time.sleep(1)
            raise FileNotFoundError(f"Source file not found: {source_dataset_path}")
        try:
            logger.info(f"Loading dataset from: {source_dataset_path} for Scan {current_scan_number}")
            loaded_sparse_array = stempy.io.load_electron_counts(source_dataset_path)
            active_emitter = FrameEmitter(
                sparse_array=loaded_sparse_array, scan_number=current_scan_number
            )
            logger.info(
                f"Emitter created for Scan {current_scan_number}. "
                f"Scan Shape: {loaded_sparse_array.scan_shape}, "
                f"Frame Shape: {loaded_sparse_array.frame_shape}, "
                f"Total Frames: {active_emitter.total_frames}."
            )
        except Exception as e:
            logger.error(f"Failed to load dataset or create emitter from {source_dataset_path}: {e}")
            active_emitter = None
            time.sleep(1)
            raise e

    # Process and Send Frames using Emitter
    if active_emitter:
        try:
            result = active_emitter.get_next_frame_message()
            if frame_delay_sec > 0:
                time.sleep(frame_delay_sec)
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
             logger.error(f"Error during frame emission or delay for scan {active_emitter.scan_number}: {e}")
             active_emitter = None
             raise e
    else:
        return None
