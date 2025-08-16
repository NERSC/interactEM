import time
from collections import deque
from typing import Any

import zmq
from distiller_streaming.client import SharedStateClient
from distiller_streaming.emitter import FrameEmitter
from distiller_streaming.util import (
    receive_and_unpack_sparse_array,
)
from stempy.io import SparseArray

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.operators.operator import dependencies, operator

logger = get_logger()

# --- Operator State ---
state_client: SharedStateClient | None = None
current_pub_address: str | None = None
current_data_port: int = 17000

DEFAULT_PUB_ADDRESS = "tcp://localhost:7082"
DEFAULT_DATA_PORT = 17000
DATA_CHECK_INTERVAL = 1.0

emitter_cache: deque[FrameEmitter] = deque()
active_emitter: FrameEmitter | None = None
last_data_check_time: float = 0.0


@dependencies
def setup_and_teardown():
    global state_client, current_pub_address, current_data_port
    global emitter_cache, active_emitter, last_data_check_time

    initial_pub_address = DEFAULT_PUB_ADDRESS
    logger.info(
        f"Initializing SharedStateClient (pub: {initial_pub_address}, data port: {DEFAULT_DATA_PORT})..."
    )
    state_client = SharedStateClient(pub_address=initial_pub_address)
    current_pub_address = initial_pub_address
    current_data_port = DEFAULT_DATA_PORT
    last_data_check_time = 0.0
    state_client.start()
    logger.info("SharedStateClient started.")

    yield

    logger.info("Shutting down operator dependencies...")
    if state_client:
        logger.info("Shutting down SharedStateClient...")
        state_client.shutdown()
        state_client = None
        logger.info("SharedStateClient shut down.")

    current_pub_address = None
    emitter_cache.clear()
    active_emitter = None
    logger.info("Operator dependencies shut down.")


@operator
def grabber(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global state_client, current_pub_address, current_data_port
    global emitter_cache, active_emitter, last_data_check_time

    if not state_client:
        logger.error("SharedStateClient not initialized.")
        time.sleep(1)
        return None

    new_pub_address = str(parameters.get("pub_address", DEFAULT_PUB_ADDRESS))
    if new_pub_address != current_pub_address:
        logger.info(
            f"Pub address changed from '{current_pub_address}' to '{new_pub_address}'. Updating client."
        )
        state_client.update_pub_address(new_pub_address)
        current_pub_address = new_pub_address

    if active_emitter is None and emitter_cache:
        active_emitter = emitter_cache.popleft()
        logger.info(
            f"Starting to process cached emitter (Scan: {active_emitter.scan_number}, "
            f"Frames: {active_emitter.total_frames})"
        )

    if active_emitter:
        try:
            result = active_emitter.get_next_frame_message()
            return result

        except StopIteration:
            scan_num = active_emitter.scan_number
            total_frames = active_emitter.total_frames
            logger.info(
                f"Finished sending all {total_frames} frames "
                f"from emitter (Scan: {scan_num})."
            )
            active_emitter = None

    current_time = time.time()
    if current_time - last_data_check_time < DATA_CHECK_INTERVAL:
        return None

    last_data_check_time = current_time

    data_socket = state_client.get_data_socket()
    if data_socket:
        try:
            new_sparse_array: SparseArray = receive_and_unpack_sparse_array(data_socket)
            scan_number = new_sparse_array.metadata.get("scan_number", 0)
            logger.info(
                f"Received new dataset (Scan: {scan_number}, "
                f"Shape: {new_sparse_array.scan_shape}, Frames: {new_sparse_array.num_scans})."
            )
            batch_size_mb = float(parameters.get("batch_size_mb", 1.0))

            emitter = FrameEmitter(
                sparse_array=new_sparse_array,
                scan_number=scan_number,
                batch_size_mb=batch_size_mb,
            )
            emitter_cache.append(emitter)

            if active_emitter is None and emitter_cache:
                active_emitter = emitter_cache.popleft()
                logger.info(
                    f"Starting to process new emitter (Scan: {active_emitter.scan_number}, "
                    f"Frames: {active_emitter.total_frames})"
                )
                try:
                    return active_emitter.get_next_frame_message()
                except StopIteration:
                    active_emitter = None

        except zmq.Again:
            pass
