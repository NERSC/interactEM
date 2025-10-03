import json
import time
from typing import Any

from distiller_streaming.client import SharedStateClient

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import dependencies, operator

logger = get_logger()

# --- Operator State ---
_state_client: SharedStateClient | None = None
_current_pub_address: str | None = None

DEFAULT_PUB_ADDRESS = "tcp://localhost:7082"

@dependencies
def setup_and_teardown():
    global _state_client, _current_pub_address

    initial_pub_address = DEFAULT_PUB_ADDRESS  # Default, can be overridden by params
    logger.info(f"Initializing SharedStateClient (pub: {initial_pub_address})...")
    _state_client = SharedStateClient(pub_address=initial_pub_address)
    _current_pub_address = initial_pub_address
    _state_client.start()
    logger.info("SharedStateClient started.")

    yield

    logger.info("Shutting down state-client operator dependencies...")
    if _state_client:
        logger.info("Shutting down SharedStateClient...")
        _state_client.shutdown()
        _state_client = None
        logger.info("SharedStateClient shut down.")

    _current_pub_address = None
    logger.info("State-client operator dependencies shut down.")


# --- Operator Kernel ---
@operator
def state_monitor(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global _state_client, _current_pub_address

    if not _state_client:
        logger.error("SharedStateClient not initialized.")
        time.sleep(1)
        return None

    new_pub_address = parameters.get("pub_address", DEFAULT_PUB_ADDRESS)

    if new_pub_address != _current_pub_address:
        logger.info(
            f"Pub address changed from '{_current_pub_address}' to '{new_pub_address}'. Updating client."
        )
        try:
            _state_client.update_pub_address(new_pub_address)
            _current_pub_address = new_pub_address
        except Exception as e:
            logger.error(f"Failed to update client pub address: {e}")

    latest_state = _state_client.get_latest_state()

    if latest_state:
        try:
            (
                df_receivers,
                _,
            ) = latest_state.get_receiver_dataframe_and_totals()
            df_aggregators = latest_state.get_aggregator_dataframe()
            df_node_groups = latest_state.get_node_group_dataframe()

            state_data_for_display = {
                "Receivers": df_receivers.to_dict(orient="records")
                if df_receivers is not None
                else [],
                "Aggregators": df_aggregators.to_dict(orient="records")
                if df_aggregators is not None
                else [],
                "Node Groups": df_node_groups.to_dict(orient="records")
                if df_node_groups is not None
                else [],
            }

            serialized_data = json.dumps(state_data_for_display).encode("utf-8")
            time.sleep(0.5)

            return BytesMessage(
                header=MessageHeader(subject=MessageSubject.BYTES),
                data=serialized_data,
            )
        except Exception as e:
            logger.error(f"Error processing or serializing state data with JSON: {e}")
            time.sleep(0.5)
            return None
    else:
        # No state received yet or client not connected
        logger.debug("No state data available from client.")
        time.sleep(0.5)
        return None
