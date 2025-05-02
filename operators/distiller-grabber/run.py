import asyncio
import time
from typing import Any

import zmq
import zmq.asyncio
from distiller_pipeline import (
    SharedStateClient,
)

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import async_operator, dependencies

logger = get_logger()

# --- Operator State ---
_state_client: SharedStateClient | None = None
_zmq_context: zmq.asyncio.Context | None = None
_data_pull_socket: zmq.asyncio.Socket | None = None
_connected_node_id: str | None = None
_current_pub_address: str | None = None


@dependencies
def setup_and_teardown():
    global _state_client, _current_pub_address, _zmq_context
    global _data_pull_socket, _connected_node_id

    # Initialize ZMQ Context
    logger.info("Initializing async ZMQ context.")
    _zmq_context = zmq.asyncio.Context()

    # Initialize SharedStateClient
    initial_pub_address = "tcp://localhost:7082"  # Default, will be updated
    logger.info(f"Initializing SharedStateClient (pub: {initial_pub_address})...")
    _state_client = SharedStateClient(pub_address=initial_pub_address)
    _current_pub_address = initial_pub_address
    _state_client.start()  # Note: Client's internal process is still synchronous
    logger.info("SharedStateClient started.")

    yield  # Let the operator run

    # --- Teardown ---
    logger.info("Shutting down operator dependencies...")
    if _state_client:
        logger.info("Shutting down SharedStateClient...")
        _state_client.shutdown()
        _state_client = None
        logger.info("SharedStateClient shut down.")

    if _data_pull_socket:
        logger.info("Closing data pull socket...")
        _data_pull_socket.close()
        _data_pull_socket = None
        logger.info("Data pull socket closed.")

    if _zmq_context:
        logger.info("Terminating async ZMQ context.")
        # Context termination should happen after sockets are closed
        time.sleep(1)
        _zmq_context.term()
        _zmq_context = None
        logger.info("Async ZMQ context terminated.")

    _connected_node_id = None
    _current_pub_address = None
    logger.info("Operator dependencies shut down.")

DATA_PORT = 15000

# --- Operator Kernel ---
@async_operator
async def state_receiver(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global _state_client, _current_pub_address, _connected_node_id
    global _zmq_context, _data_pull_socket

    if not _state_client or not _zmq_context:
        logger.error("SharedStateClient or ZMQ Context not initialized.")
        await asyncio.sleep(1)
        return None

    # --- 1. Handle Parameter Updates ---
    new_pub_address = parameters.get("pub_address", "tcp://localhost:7082")

    if new_pub_address != _current_pub_address:
        logger.info(
            f"Pub address changed from '{_current_pub_address}' to '{new_pub_address}'. Updating client."
        )
        try:
            _state_client.update_pub_address(new_pub_address)
            _current_pub_address = new_pub_address
            # Reset connection state
            if _data_pull_socket:
                _data_pull_socket.close()
                _data_pull_socket = None
            _connected_node_id = None
        except Exception as e:
            logger.error(f"Failed to update client pub address: {e}")

    # --- 2. Check for Head Node Updates from Client ---
    _state_client.receive_update(timeout_ms=0)
    new_head_node_id = _state_client.get_current_head_node_id()

    # --- 3. Manage Data Pull Socket Connection ---
    if new_head_node_id != _connected_node_id:
        logger.info(
            f"Head node change detected. Old: '{_connected_node_id}', New: '{new_head_node_id}'."
        )

        # Close existing connection if it exists
        if _data_pull_socket:
            logger.info(f"Closing connection to old head node '{_connected_node_id}'.")
            _data_pull_socket.close()
            _data_pull_socket = None

        # Connect to new head node if specified
        if new_head_node_id:
            data_pull_addr = f"tcp://{new_head_node_id}.chn.perlmutter.nersc.gov:{DATA_PORT}"
            logger.info(f"Attempting to connect PULL socket to {data_pull_addr}...")
            try:
                # Create and connect async ZMQ socket
                _data_pull_socket = _zmq_context.socket(zmq.PULL)
                # Set linger to 0 for faster close
                _data_pull_socket.setsockopt(zmq.LINGER, 0)
                _data_pull_socket.connect(data_pull_addr)
                _connected_node_id = new_head_node_id
                logger.info(f"Successfully connected PULL socket to {data_pull_addr}.")
            except (zmq.ZMQError, OSError, Exception) as e:
                logger.error(
                    f"Failed to connect PULL socket to {data_pull_addr}: {type(e).__name__}: {e}"
                )
                if _data_pull_socket:  # Ensure socket is closed on connect error
                    _data_pull_socket.close()
                _data_pull_socket = None
                _connected_node_id = None
        else:
            # No new head node, ensure state reflects no connection
            _connected_node_id = None
            logger.info("Head node is None. No active data connection.")

    # --- 4. Attempt to Pull Data ---
    if _data_pull_socket:
        try:
            # Receive non-blockingly using await and NOBLOCK flag
            msg = await _data_pull_socket.recv(flags=zmq.NOBLOCK)
            logger.debug(f"Received {len(msg)} bytes from data pull socket.")
            # --- 5. Return Data ---
            return BytesMessage(
                header=MessageHeader(subject=MessageSubject.BYTES, meta={}), data=msg
            )
        except zmq.Again:
            # Expected when no message is available with NOBLOCK
            logger.debug("No data available on pull socket (zmq.Again).")
            return None
        except (zmq.ZMQError, asyncio.CancelledError, Exception) as e:
            logger.error(
                f"Error reading from data pull socket for '{_connected_node_id}': {type(e).__name__}: {e}"
            )
            # Assume connection is broken, close and clear state
            if _data_pull_socket:
                _data_pull_socket.close()
            _data_pull_socket = None
            _connected_node_id = None
            return None
    else:
        # No active connection
        logger.debug("No data pull connection active.")
        return None
