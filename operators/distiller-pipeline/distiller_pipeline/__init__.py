import multiprocessing
import multiprocessing.synchronize
import os
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Generator
from enum import Enum
from typing import Any

import msgpack
import numpy as np
import pandas as pd
import stempy.image as stim
import zmq
from pydantic import BaseModel, Field
from stempy.io import SparseArray

from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)

logger = get_logger()


# --- Enum Mappings ---
class StateLocation:
    RECEIVER = 0
    AGGREGATOR = 1
    NODE = 2


class MessagingStatus:
    IDLE = 0
    BEFORE_SEND_FRAMES = 1
    AFTER_SEND_FRAMES = 2
    WAITING_FOR_UPSTREAM_FRAMES = 3
    WAITING_FOR_DOWNSTREAM_READY_FRAMES = 4
    WAITING_FOR_DOWNSTREAM_READY_MULTISCAN = 5
    STREAMING = 6
    FINISHED_SEND = 7
    PROCESSING = 8
    WRITING_TO_PM = 9
    FINISHED_WRITING_TO_PM = 10
    WRITING = 11
    PULLING_FROM_FPGA = 12


def state_location_to_string(location_int: int) -> str:
    mapping = {
        StateLocation.RECEIVER: "RECEIVER",
        StateLocation.AGGREGATOR: "AGGREGATOR",
        StateLocation.NODE: "NODE",
    }
    return mapping.get(location_int, "UNKNOWN")


def messaging_status_to_string(status_int: int) -> str:
    mapping = {
        MessagingStatus.IDLE: "Idle",
        MessagingStatus.BEFORE_SEND_FRAMES: "B-Frames",
        MessagingStatus.AFTER_SEND_FRAMES: "A-Frames",
        MessagingStatus.WAITING_FOR_UPSTREAM_FRAMES: "WU-Frames",
        MessagingStatus.WAITING_FOR_DOWNSTREAM_READY_FRAMES: "WD-FRAMES",
        MessagingStatus.WAITING_FOR_DOWNSTREAM_READY_MULTISCAN: "WD-Multi",
        MessagingStatus.STREAMING: "Streaming",
        MessagingStatus.FINISHED_SEND: "Fin-Send",
        MessagingStatus.PROCESSING: "Processing",
        MessagingStatus.WRITING_TO_PM: "WritingPM",
        MessagingStatus.FINISHED_WRITING_TO_PM: "FinWritePM",
        MessagingStatus.WRITING: "Writing",
        MessagingStatus.PULLING_FROM_FPGA: "Pulling",
    }
    return mapping.get(status_int, "UNKNOWN")


# --- Pydantic Models (Mirroring C++ Structs) ---
def decode_str(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return str(value)  # Fallback for non-UTF8 bytes
    return str(value)


def parse_nested_dict(
    data: dict, inner_parser: Callable[[Any], Any], depth: int
) -> dict:
    """
    Recursively parse a nested dictionary with string keys expected to be integers.

    Args:
        data: The dictionary to parse.
        inner_parser: The function to apply to the innermost values.
        depth: The current nesting depth (starts at the desired level, e.g., 2 for two levels).

    Returns:
        The parsed dictionary with integer keys.

    Raises:
        ValueError: If keys cannot be converted to int or structure is invalid.
        TypeError: If input is not a dictionary at expected levels.
    """
    if depth < 1:
        raise ValueError("Depth must be at least 1")
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict at depth {depth}, got {type(data)}")

    parsed = {}
    for k, v in data.items():
        try:
            int_key = int(k)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid key '{k}' at depth {depth}, expected integer")

        if depth == 1:
            parsed[int_key] = inner_parser(v)
        else:
            parsed[int_key] = parse_nested_dict(v, inner_parser, depth - 1)
    return parsed


class ReceiverInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    module: int = 0
    n_messages: int = 0
    scan_number: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "ReceiverInfo":
        if len(data) < 4:
            raise ValueError(f"Invalid data format for ReceiverInfo: {data}")
        return cls(
            status=int(data[0]),
            module=int(data[1]),
            n_messages=int(data[2]),
            scan_number=int(data[3]),
        )


class ReceiversInfo(BaseModel):
    n_messages: int = 0
    receivers: dict[int, dict[int, ReceiverInfo]] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "ReceiversInfo":
        if len(data) < 2:
            raise ValueError(f"Invalid data format for ReceiversInfo: {data}")
        n_messages = int(data[0])
        receivers = parse_nested_dict(data[1], ReceiverInfo.from_msgpack, depth=2)
        return cls(n_messages=n_messages, receivers=receivers)


class AggregatorInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    module: int = 0
    n_messages: int = 0
    scan_number: int = 0
    thread_id: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "AggregatorInfo":
        if len(data) < 5:
            raise ValueError(f"Invalid data format for AggregatorInfo: {data}")
        return cls(
            status=int(data[0]),
            module=int(data[1]),
            n_messages=int(data[2]),
            scan_number=int(data[3]),
            thread_id=int(data[4]),
        )


class AggregatorsInfo(BaseModel):
    n_messages: int = 0
    aggregators: dict[int, dict[int, AggregatorInfo]] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "AggregatorsInfo":
        if len(data) < 2:
            raise ValueError(f"Invalid data format for AggregatorsInfo: {data}")
        n_messages = int(data[0])
        aggregators = parse_nested_dict(data[1], AggregatorInfo.from_msgpack, depth=2)
        return cls(n_messages=n_messages, aggregators=aggregators)


class NodeGroupThreadInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    n_messages: int = 0
    scan_number: int = 0
    short_id: int = 0
    mpi_rank: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "NodeGroupThreadInfo":
        if not isinstance(data, list) or len(data) < 5:
            raise ValueError(f"Invalid data format for NodeGroupThreadInfo: {data}")
        return cls(
            status=int(data[0]),
            n_messages=int(data[1]),
            scan_number=int(data[2]),
            short_id=int(data[3]),
            mpi_rank=int(data[4]),
        )


class NodeInfo(BaseModel):
    n_messages: int = 0
    node_id: str = "0"
    node_group_thread_info: dict[int, dict[int, dict[int, NodeGroupThreadInfo]]] = (
        Field(default_factory=dict)
    )

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "NodeInfo":
        if not isinstance(data, list) or len(data) < 3:
            raise ValueError(f"Invalid data format for NodeInfo: {data}")

        n_messages = int(data[0])
        node_id = decode_str(data[1])
        node_group_thread_info = parse_nested_dict(
            data[2], NodeGroupThreadInfo.from_msgpack, depth=3
        )
        return cls(
            n_messages=n_messages,
            node_id=node_id,
            node_group_thread_info=node_group_thread_info,
        )


class SharedState(BaseModel):
    receiver_map: dict[str, ReceiversInfo] = Field(default_factory=dict)
    aggregator_map: dict[str, AggregatorsInfo] = Field(default_factory=dict)
    node_map: dict[str, NodeInfo] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "SharedState":
        if not isinstance(data, list) or len(data) < 3:
            raise ValueError(f"Invalid data format for SharedState: {data}")

        receiver_map = {
            decode_str(k): ReceiversInfo.from_msgpack(v) for k, v in data[0].items()
        }

        aggregator_map = {
            decode_str(k): AggregatorsInfo.from_msgpack(v) for k, v in data[1].items()
        }

        node_map = {decode_str(k): NodeInfo.from_msgpack(v) for k, v in data[2].items()}

        return cls(
            receiver_map=receiver_map,
            aggregator_map=aggregator_map,
            node_map=node_map,
        )

    def get_receiver_dataframe_and_totals(
        self,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        """Prepares a DataFrame and totals for receiver information."""
        receiver_totals = {
            rec_id: recs_info.n_messages
            for rec_id, recs_info in self.receiver_map.items()
        }
        receiver_data = [
            {
                "Module": info.module,
                "Thread ID": thread_id,
                "Status": messaging_status_to_string(info.status),
                "No. Messages": info.n_messages,
                "Scan No.": info.scan_number,
            }
            for recs_info in self.receiver_map.values()
            for threads_dict in recs_info.receivers.values()
            for thread_id, info in threads_dict.items()
        ]

        if not receiver_data:
            df_receivers = pd.DataFrame(
                columns=["Module", "Thread ID", "Status", "No. Messages", "Scan No."]
            )
        else:
            df_receivers = pd.DataFrame(receiver_data)
            df_receivers = df_receivers.sort_values(by=["Module", "Thread ID"])

        sorted_receiver_totals = dict(sorted(receiver_totals.items()))
        return df_receivers, sorted_receiver_totals

    def get_aggregator_dataframe(
        self,
    ) -> pd.DataFrame:
        """Prepares a DataFrame and totals for aggregator information."""
        aggregator_data = [
            {
                "Module": info.module,
                "Status": messaging_status_to_string(info.status),
                "Scan No.": info.scan_number,
            }
            for aggs_info in self.aggregator_map.values()
            for threads_dict in aggs_info.aggregators.values()
            for info in threads_dict.values()
        ]

        if not aggregator_data:
            df_aggregators = pd.DataFrame(columns=["Module", "Status", "Scan No."])
        else:
            df_aggregators = pd.DataFrame(aggregator_data)
            df_aggregators = df_aggregators.sort_values(by=["Module"])

        return df_aggregators

    def get_node_group_dataframe(
        self,
    ) -> pd.DataFrame:
        """Prepares a DataFrame for node group information."""
        node_group_data = []

        for node_key in sorted(self.node_map.keys()):
            node_info = self.node_map[node_key]

            # --- Aggregate thread info per (mpi_rank, short_id) group ---
            aggregated_groups: dict[tuple[int, int], dict[str, Any]] = defaultdict(
                lambda: {
                    "n_messages": 0,
                    "status": MessagingStatus.IDLE,
                    "scan_num": float("inf"),
                }
            )

            # Flatten the nested dictionary iteration
            all_threads_info = [
                (mpi_rank, short_id, thread_id, thread_info)
                for mpi_rank, short_id_dict in node_info.node_group_thread_info.items()
                for short_id, thread_id_dict in short_id_dict.items()
                for thread_id, thread_info in thread_id_dict.items()
            ]

            # Sort by mpi_rank, short_id, then thread_id.
            # Sorting by thread_id ensures the status assignment below matches
            # the original logic (implicitly taking the status of the last thread_id).
            all_threads_info.sort()

            # Process the flattened list to aggregate data
            for mpi_rank, short_id, _thread_id, ng_thread_info in all_threads_info:
                group_key = (mpi_rank, short_id)
                aggregated_groups[group_key]["n_messages"] += ng_thread_info.n_messages
                # Status gets overwritten by later threads in the sorted list (highest thread_id)
                aggregated_groups[group_key]["status"] = ng_thread_info.status
                aggregated_groups[group_key]["scan_num"] = min(
                    aggregated_groups[group_key]["scan_num"],
                    ng_thread_info.scan_number,
                )
            # --- End Aggregation ---

            # --- Create DataFrame rows from aggregated data ---
            for (mpi_rank, short_id), data in sorted(aggregated_groups.items()):
                scan_num_str = str(data["scan_num"])
                node_group_data.append(
                    {
                        "Node ID": node_info.node_id,
                        "MPI Rank": mpi_rank,
                        "ShortID": short_id,
                        "Status": messaging_status_to_string(data["status"]),
                        "Scan No.": scan_num_str,
                    }
                )
            # --- End DataFrame Row Creation ---

        # Create the final DataFrame
        df_node_groups = pd.DataFrame(node_group_data)

        # Ensure consistent sorting (although data is likely already sorted)
        if not df_node_groups.empty:
            df_node_groups = df_node_groups.sort_values(
                by=["Node ID", "MPI Rank", "ShortID"]
            ).reset_index(drop=True)
        else:
            df_node_groups = pd.DataFrame(
                columns=["Node ID", "MPI Rank", "ShortID", "Status", "Scan No."]
            )

        return df_node_groups

    def print(self: "SharedState") -> None:
        # --- Prepare DataFrames using methods from SharedState ---
        df_receivers, receiver_totals = self.get_receiver_dataframe_and_totals()
        df_aggregators = self.get_aggregator_dataframe()
        df_node_groups = self.get_node_group_dataframe()

        # --- Configure Pandas Display ---
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        pd.set_option("display.colheader_justify", "left")

        # --- Clear Screen ---
        try:
            os.system("clear")
        except OSError:
            logger.info("\n" * 50)

        # --- Print Receivers ---
        logger.info("--- Receivers ---")
        if not df_receivers.empty:
            # Ensure correct columns are present before printing
            cols_to_print = [
                "Module",
                "Thread ID",
                "Status",
                "No. Messages",
                "Scan No.",
            ]
            logger.info(df_receivers[cols_to_print].to_string(index=False))
            # Print totals after the table
            for rec_id, total in receiver_totals.items():
                logger.info(f"Total Messages for {rec_id}: {total}")
        else:
            logger.info("No receiver data.")
        logger.info("\n")

        # --- Print Aggregators ---
        logger.info("--- Aggregators ---")
        if not df_aggregators.empty:
            # Ensure correct columns are present before printing
            cols_to_print = ["Module", "Status", "Scan No."]
            logger.info(df_aggregators[cols_to_print].to_string(index=False))
        else:
            logger.info("No aggregator data.")
        logger.info("\n")

        # --- Print Node Groups ---
        logger.info("--- Node Groups ---")
        if not df_node_groups.empty:
            df_node_groups = df_node_groups.sort_values(
                by=["Node ID", "MPI Rank", "ShortID"],
            )
            # Ensure correct columns are present before printing
            cols_to_print = ["Node ID", "MPI Rank", "ShortID", "Status", "Scan No."]
            logger.info(df_node_groups[cols_to_print].to_string(index=False))
        else:
            logger.info("No node group data.")
        logger.info("\n")

        sys.stdout.flush()


class SharedStateMsg(BaseModel):
    sequence: int = 0
    state_location_origin: int = 0
    key: str = ""
    properties: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    shared_state: SharedState = Field(default_factory=SharedState)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "SharedStateMsg":
        if not isinstance(data, list) or len(data) < 6:
            raise ValueError(f"Invalid data format for SharedStateMsg: {data}")

        sequence = int(data[0])
        state_location_origin = int(data[1])
        key = decode_str(data[2])

        properties_raw = data[3]
        if not isinstance(properties_raw, dict):
            raise TypeError(f"Expected dict for properties, got {type(properties_raw)}")
        properties = {decode_str(k): decode_str(v) for k, v in properties_raw.items()}

        body = decode_str(data[4])

        shared_state_raw = data[5]
        if not isinstance(shared_state_raw, list):
            raise TypeError(
                f"Expected list for shared_state, got {type(shared_state_raw)}"
            )
        shared_state = SharedState.from_msgpack(shared_state_raw)

        return cls(
            sequence=sequence,
            state_location_origin=state_location_origin,
            key=key,
            properties=properties,
            body=body,
            shared_state=shared_state,
        )


def unpack_sparse_array(
    packed_data: bytes,
) -> SparseArray:
    unpacked_data = msgpack.unpackb(packed_data, raw=False)

    scan_number = unpacked_data.get("scan_number")
    scan_shape = tuple(unpacked_data["scan_shape"])
    frame_shape = tuple(unpacked_data["frame_shape"])
    raw_data = unpacked_data["data"]  # Expected: list[list[list[int]]]
    metadata = unpacked_data.get("metadata", {})

    num_scan_positions = len(raw_data)
    expected_scan_positions = np.prod(scan_shape) if scan_shape else 0

    if expected_scan_positions != num_scan_positions:
        raise ValueError(
            f"Inconsistent unpacked data: scan_shape {scan_shape} product ({expected_scan_positions}) "
            f"does not match outer data length {num_scan_positions}"
        )

    # Determine frames_per_scan safely, handle empty scans
    frames_per_scan = len(raw_data[0]) if num_scan_positions > 0 else 0

    # Create the outer numpy array with dtype=object
    data_array = np.empty(scan_shape + (frames_per_scan,), dtype=object)

    for i in range(num_scan_positions):
        scan_index = np.unravel_index(i, scan_shape)
        if len(raw_data[i]) != frames_per_scan:
            raise ValueError(
                f"Inconsistent frame count at scan position {i} (index {scan_index}): "
                f"expected {frames_per_scan}, got {len(raw_data[i])}"
            )
        for j in range(frames_per_scan):
            data_array[scan_index + (j,)] = np.array(raw_data[i][j], dtype=np.uint32)

    # --- Instantiate SparseArray ---
    sparse_array = SparseArray(
        data=data_array,
        scan_shape=scan_shape,
        frame_shape=frame_shape,
        metadata=metadata,
    )
    sparse_array.metadata["frames_per_scan"] = frames_per_scan
    if scan_number is not None:
        sparse_array.metadata["scan_number"] = scan_number

    return sparse_array


def receive_and_unpack_sparse_array(
    socket: zmq.Socket,
) -> SparseArray:
    packed_data = socket.recv(copy=False)

    return unpack_sparse_array(bytes(packed_data.buffer))


class UpdateType(Enum):
    NODES_CONNECTED = "NODES_CONNECTED"
    NODES_DISCONNECTED = "NODES_DISCONNECTED"
    STATE_UPDATE = "STATE_UPDATE"


class BaseUpdate(BaseModel):
    update_type: UpdateType


class NodeConnectedUpdate(BaseUpdate):
    update_type: UpdateType = UpdateType.NODES_CONNECTED
    head_node_id: str


class NodeDisconnectedUpdate(BaseUpdate):
    update_type: UpdateType = UpdateType.NODES_DISCONNECTED


class StateUpdate(BaseUpdate):
    update_type: UpdateType = UpdateType.STATE_UPDATE
    shared_state: SharedState


class SharedStateClient:
    """
    Manages subscription to shared state updates in a background process
    and provides methods to receive head node status changes.
    """

    DATA_PORT = 17000

    def __init__(self, pub_address: str):
        self.pub_address = pub_address
        self._process: multiprocessing.Process | None = None
        self._stop_event = multiprocessing.Event()

        # IPC for receiving updates from the background process
        self._ipc_context = zmq.Context()
        self._update_pull_socket = self._ipc_context.socket(zmq.PULL)
        ipc_dir = "/tmp"
        os.makedirs(ipc_dir, exist_ok=True)
        self._update_pull_address = (
            f"ipc://{os.path.join(ipc_dir, f'interactem_state_updates_{os.getpid()}')}"
        )
        self._cleanup_ipc_file()

        try:
            self._update_pull_socket.bind(self._update_pull_address)
        except zmq.ZMQError as e:
            logger.info(
                f"[Client] Error binding IPC socket {self._update_pull_address}: {e}."
            )
            self._cleanup_ipc_file()
            try:
                self._update_pull_socket.bind(self._update_pull_address)
                logger.info("[Client] Successfully bound IPC socket after cleanup.")
            except Exception as bind_e:
                logger.info(
                    f"[Client] Failed to bind IPC socket even after cleanup: {bind_e}"
                )
                raise e

        self._update_poller = zmq.Poller()
        self._update_poller.register(self._update_pull_socket, zmq.POLLIN)

        self.current_head_node_id: str | None = None
        self._latest_state: SharedState | None = None

        # Data socket management
        self._zmq_data_context: zmq.Context = zmq.Context()
        self._data_pull_socket: zmq.Socket | None = None
        self._connected_node_id: str | None = None

    def _cleanup_ipc_file(self):
        """Removes the IPC socket file if it exists."""
        ipc_socket_path = self._update_pull_address.replace("ipc://", "")
        try:
            if os.path.exists(ipc_socket_path):
                os.unlink(ipc_socket_path)
                logger.info(
                    f"[Client] Removed existing IPC socket file: {ipc_socket_path}"
                )
        except OSError as e:
            logger.info(
                f"[Client] Error removing IPC socket file {ipc_socket_path}: {e}"
            )
        except Exception as e:
            logger.info(f"[Client] Unexpected error removing IPC file: {e}")

    @staticmethod
    def _setup_zmq_sockets(
        pub_address: str, update_push_address: str
    ) -> tuple[zmq.Context, zmq.Socket, zmq.Socket, zmq.Poller]:
        """Initializes and connects ZMQ sockets for communication."""
        context = zmq.Context()
        poller = zmq.Poller()

        try:
            # Connect Subscriber
            subscriber = context.socket(zmq.SUB)
            subscriber.connect(pub_address)
            subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
            poller.register(subscriber, zmq.POLLIN)

            # Connect Pusher
            update_pusher = context.socket(zmq.PUSH)
            update_pusher.setsockopt(zmq.LINGER, 0)
            update_pusher.connect(update_push_address)

            return context, subscriber, update_pusher, poller

        except Exception as e:
            # Simple cleanup on failure
            if "subscriber" in locals() and not subscriber.closed:
                subscriber.close()
            if "update_pusher" in locals() and not update_pusher.closed:
                update_pusher.close()
            if not context.closed:
                context.term()
            raise e

    @staticmethod
    def _process_incoming_message(
        subscriber: zmq.Socket,
        update_pusher: zmq.Socket,
        last_head_node_id: str | None,
    ) -> str | None:
        """Process incoming messages and detect head node changes."""
        try:
            message_bytes = subscriber.recv(zmq.NOBLOCK)
            unpacked_list = msgpack.unpackb(
                message_bytes, raw=True, use_list=True, strict_map_key=False
            )
            shared_state_msg = SharedStateMsg.from_msgpack(unpacked_list)

            # Skip heartbeat messages
            if shared_state_msg.body == "HUGZ":
                return last_head_node_id

            # Process state update
            shared_state_data = shared_state_msg.shared_state
            update_pusher.send_pyobj(StateUpdate(shared_state=shared_state_data))

            # Check for head node changes
            new_head_node_id = None
            if shared_state_data.node_map:
                for node_info in shared_state_data.node_map.values():
                    if any(
                        0 in short_id_dict
                        for short_id_dict in node_info.node_group_thread_info.values()
                    ):
                        new_head_node_id = node_info.node_id
                        break

            # Send notifications if head node status changed
            if new_head_node_id != last_head_node_id:
                if new_head_node_id is not None:
                    update_pusher.send_pyobj(
                        NodeConnectedUpdate(head_node_id=new_head_node_id)
                    )
                else:
                    update_pusher.send_pyobj(NodeDisconnectedUpdate())
                return new_head_node_id

            return last_head_node_id

        except zmq.Again:
            # No message available
            return last_head_node_id
        except Exception:
            # Let errors propagate to main loop
            raise

    @staticmethod
    def _cleanup_zmq_resources(
        context: zmq.Context,
        subscriber: zmq.Socket,
        update_pusher: zmq.Socket,
        poller: zmq.Poller,
    ):
        """Close ZMQ sockets and terminate context."""
        # Clean up subscriber
        if subscriber and not subscriber.closed:
            if poller:
                try:
                    poller.unregister(subscriber)
                except KeyError:
                    pass
            subscriber.close()

        # Clean up pusher
        if update_pusher and not update_pusher.closed:
            update_pusher.close()

        # Clean up context
        if context and not context.closed:
            context.term()

    @staticmethod
    def _run_background_process(
        pub_address: str,
        update_push_address: str,
        stop_event: multiprocessing.synchronize.Event,
    ):
        """Background process that monitors for state updates and node changes."""
        logger.info(f"[BGProc:{os.getpid()}] Starting background process")

        try:
            # Set up ZMQ resources
            context, subscriber, update_pusher, poller = (
                SharedStateClient._setup_zmq_sockets(pub_address, update_push_address)
            )

            last_head_node_id = None

            # Main monitoring loop
            while not stop_event.is_set():
                try:
                    socks = dict(poller.poll(100))  # 100ms timeout

                    # Process messages when available
                    if subscriber in socks and socks[subscriber] == zmq.POLLIN:
                        last_head_node_id = SharedStateClient._process_incoming_message(
                            subscriber, update_pusher, last_head_node_id
                        )

                except zmq.ZMQError as e:
                    if e.errno == zmq.ETERM:
                        break  # Context terminated, exit loop
                    # For other errors, pause briefly to avoid busy-looping
                    time.sleep(0.1)

        except Exception as e:
            logger.info(
                f"[BGProc:{os.getpid()}] Error in background process: {type(e).__name__}: {e}"
            )
        finally:
            # Ensure resources are cleaned up
            SharedStateClient._cleanup_zmq_resources(
                context,
                subscriber,
                update_pusher,
                poller,
            )
            logger.info(f"[BGProc:{os.getpid()}] Background process finished")

    def start(self):
        """Starts the background subscriber process."""
        if self._process is not None and self._process.is_alive():
            logger.info("[Client] Process already running.")
            return

        logger.info(f"[Client] Starting background process for {self.pub_address}")
        self._stop_event.clear()

        # Start the background process
        self._process = multiprocessing.Process(
            target=SharedStateClient._run_background_process,
            args=(self.pub_address, self._update_pull_address, self._stop_event),
            daemon=True,
        )
        self._process.start()
        logger.info(f"[Client] Background process started (PID: {self._process.pid})")

    def _handle_node_connected_update(self, update: NodeConnectedUpdate) -> None:
        """Handle node connected updates"""
        if self.current_head_node_id != update.head_node_id:
            logger.info(f"[Client] Head node connected: {update.head_node_id}")
        self.current_head_node_id = update.head_node_id

    def _handle_node_disconnected_update(self, _: NodeDisconnectedUpdate) -> None:
        """Handle node disconnected updates"""
        if self.current_head_node_id is not None:
            logger.info("[Client] Head node disconnected")
        self.current_head_node_id = None

    def _handle_state_update(self, update: StateUpdate) -> None:
        """Handle full state updates"""
        self._latest_state = update.shared_state

    def receive_update(self, timeout_ms: int = 0) -> None:
        """
        Checks for and processes updates from the background process.

        Args:
            timeout_ms: Poll timeout in milliseconds. 0 for non-blocking.
        """
        if self._update_pull_socket is None or self._update_pull_socket.closed:
            raise RuntimeError("[Client] ZMQ socket is closed or not initialized")

        # Function map for dispatch
        update_handlers = {
            UpdateType.NODES_CONNECTED: self._handle_node_connected_update,
            UpdateType.NODES_DISCONNECTED: self._handle_node_disconnected_update,
            UpdateType.STATE_UPDATE: self._handle_state_update,
        }

        try:
            socks = dict(self._update_poller.poll(timeout_ms))
            if (
                self._update_pull_socket in socks
                and socks[self._update_pull_socket] == zmq.POLLIN
            ):
                update = self._update_pull_socket.recv_pyobj(zmq.NOBLOCK)
                if not isinstance(update, BaseUpdate):
                    raise TypeError(f"[Client] Expected BaseUpdate, got {type(update)}")

                handler = update_handlers.get(update.update_type)
                if handler:
                    handler(update)
                else:
                    raise RuntimeError(
                        f"[Client] Unknown update type: {update.update_type}"
                    )

        except zmq.Again:
            pass  # No messages available
        except zmq.ZMQError as e:
            logger.error(f"[Client] ZMQ Error: {e}")
            if e.errno == zmq.ETERM:
                self._close_ipc_resources()
        except Exception as e:
            logger.error(f"[Client] Error processing update: {e}")
            raise

    def get_current_head_node_id(self) -> str | None:
        """Returns the last known head node ID, checking for updates first."""
        self.receive_update(timeout_ms=0)
        return self.current_head_node_id

    def get_latest_state(self) -> SharedState | None:
        """Returns the most recently received SharedState object."""
        self.receive_update(timeout_ms=0)
        return self._latest_state

    def update_pub_address(self, new_pub_address: str, shutdown_timeout_sec: int = 5):
        """
        Updates the publisher address and restarts the background process.
        """
        if new_pub_address == self.pub_address:
            return

        logger.info(
            f"[Client] Updating address: {self.pub_address} → {new_pub_address}"
        )

        # Shutdown current process and IPC
        self.shutdown(timeout_sec=shutdown_timeout_sec)

        # Update address
        self.pub_address = new_pub_address

        # Re-initialize IPC and socket
        self._ipc_context = zmq.Context()
        self._update_pull_socket = self._ipc_context.socket(zmq.PULL)
        self._cleanup_ipc_file()

        # Try to bind socket, with one retry after cleanup
        try:
            self._update_pull_socket.bind(self._update_pull_address)
        except zmq.ZMQError:
            self._cleanup_ipc_file()
            try:
                self._update_pull_socket.bind(self._update_pull_address)
            except Exception:
                logger.info("[Client] Failed to bind IPC socket after cleanup")
                self._close_ipc_resources()
                return

        # Register with poller and restart process
        self._update_poller = zmq.Poller()
        self._update_poller.register(self._update_pull_socket, zmq.POLLIN)
        self.start()

    def get_data_socket(self) -> zmq.Socket | None:
        """
        Returns a connected socket to the current head node's data port.
        """
        self.receive_update(timeout_ms=0)
        new_head_node_id = self.current_head_node_id

        # Handle head node change
        if new_head_node_id != self._connected_node_id:
            # Close existing connection
            if self._data_pull_socket:
                self._data_pull_socket.close()
                self._data_pull_socket = None

            # Connect to new head node if available
            if new_head_node_id:
                data_pull_addr = f"tcp://{new_head_node_id}:{self.DATA_PORT}"
                try:
                    self._data_pull_socket = self._zmq_data_context.socket(zmq.SUB)
                    if not self._data_pull_socket:
                        raise RuntimeError("Unable to create data socket")
                    self._data_pull_socket.setsockopt(zmq.LINGER, 0)
                    self._data_pull_socket.setsockopt(zmq.RCVTIMEO, 1000)
                    self._data_pull_socket.setsockopt_string(zmq.SUBSCRIBE, "")
                    self._data_pull_socket.connect(data_pull_addr)
                    self._connected_node_id = new_head_node_id
                    logger.info(f"[Client] Connected to data port: {data_pull_addr}")
                except Exception as e:
                    self._data_pull_socket = None
                    self._connected_node_id = None
                    raise RuntimeError(f"[Client] Data socket connection failed: {e}")
            else:
                self._connected_node_id = None

        return self._data_pull_socket

    def _close_data_socket(self) -> None:
        """Close the data socket if it exists."""
        if self._data_pull_socket:
            self._data_pull_socket.close()
            self._data_pull_socket = None
        self._connected_node_id = None

    def _close_ipc_resources(self):
        """Safely close client-side IPC resources."""
        # Unregister and close socket
        if self._update_pull_socket:
            try:
                self._update_poller.unregister(self._update_pull_socket)
            except KeyError:
                pass
            self._update_pull_socket.close()
            self._update_pull_socket = None

        # Terminate context
        if self._ipc_context and not self._ipc_context.closed:
            self._ipc_context.term()

        # Close data socket
        self._close_data_socket()

        # Clean up IPC file
        self._cleanup_ipc_file()

    def shutdown(self, timeout_sec: int = 5):
        """Stop the background process and clean up resources."""
        if self._process is not None and self._process.is_alive():
            # Signal process to stop
            self._stop_event.set()
            self._process.join(timeout=timeout_sec)

            # Force terminate if needed
            if self._process.is_alive():
                try:
                    self._process.terminate()
                    self._process.join(2)
                    if self._process.is_alive():
                        self._process.kill()
                        self._process.join(1)
                except Exception as e:
                    logger.info(f"[Client] Error terminating process: {e}")

            self._process = None

        # Clean up IPC resources
        self._close_ipc_resources()
        logger.info("[Client] Shutdown complete")

    def __del__(self):
        """Cleanup when object is garbage collected."""
        self.shutdown(timeout_sec=2)


class FrameHeader(BaseModel):
    scan_number: int
    frame_number: int | None = None
    nSTEM_positions_per_row_m1: int
    nSTEM_rows_m1: int
    STEM_x_position_in_row: int
    STEM_row_in_scan: int
    modules: list[int]
    frame_shape: tuple[int, int]


class FrameAccumulator(SparseArray):
    """Accumulates sparse frames for a single scan, tracking which frames have been added."""

    def __init__(
        self,
        scan_number: int,
        scan_shape: tuple[int, int],
        frame_shape: tuple[int, int],
        dtype=np.uint32,
        **kwargs,
    ):
        # Validate shapes
        if not isinstance(scan_shape, tuple) or len(scan_shape) != 2:
            raise ValueError(
                f"Invalid scan_shape: {scan_shape}. Must be a tuple of length 2."
            )
        if not isinstance(frame_shape, tuple) or len(frame_shape) != 2:
            raise ValueError(
                f"Invalid frame_shape: {frame_shape}. Must be a tuple of length 2."
            )

        self.scan_number = scan_number
        num_scan_positions = int(np.prod(scan_shape))

        # Initialize data storage
        initial_data = np.empty((num_scan_positions, 1), dtype=object)
        empty_array = np.array([], dtype=np.uint32)
        for i in range(num_scan_positions):
            initial_data[i, 0] = empty_array

        # Initialize parent
        super().__init__(
            data=initial_data,
            scan_shape=scan_shape,
            frame_shape=frame_shape,
            dtype=dtype,
            **kwargs,
        )

        self._frames_per_position = {}
        self.num_frames_added = 0

        logger.info(
            f"Initialized FrameAccumulator for scan {scan_number} with shape {scan_shape}x{frame_shape}"
        )

    @property
    def frames_added_indices(self) -> set[int]:
        """Set of scan position indices for which at least one frame has been added."""
        return set(self._frames_per_position.keys())

    @property
    def num_positions_with_frames(self) -> int:
        """Number of scan positions that have at least one frame."""
        return len(self._frames_per_position)

    def add_frame(self, header: FrameHeader, frame_data: np.ndarray) -> None:
        """
        Adds a sparse frame's data at the position specified in the header.
        If a frame already exists at this position, adds it as an additional frame
        rather than overwriting.

        Args:
            header: Frame header containing position information
            frame_data: NumPy array containing sparse frame data

        Raises:
            ValueError: If header dimensions don't match accumulator dimensions
            IndexError: If calculated position is out of bounds
        """
        if header.scan_number != self.scan_number:
            raise ValueError(
                f"Scan number mismatch: header {header.scan_number}, "
                f"accumulator {self.scan_number}"
            )

        # Validate scan shape matches header
        if (header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1) != self.scan_shape:
            raise ValueError(
                f"Scan {self.scan_number}: Mismatch between header scan shape "
                f"{(header.nSTEM_rows_m1, header.nSTEM_positions_per_row_m1)} and "
                f"accumulator scan shape {self.scan_shape}"
            )

        # Validate frame shape matches header
        if header.frame_shape != self.frame_shape:
            raise ValueError(
                f"Scan {self.scan_number}: Mismatch between header frame shape "
                f"{header.frame_shape} and accumulator frame shape {self.frame_shape}"
            )

        # Calculate flat index from 2D position
        scan_position_flat = (
            header.STEM_row_in_scan * header.nSTEM_positions_per_row_m1
            + header.STEM_x_position_in_row
        )

        # Ensure position is within bounds
        if not (0 <= scan_position_flat < self.num_scans):
            raise IndexError(
                f"Invalid scan position {scan_position_flat}. Max expected: {self.num_scans - 1}"
            )

        # Count frames already at this position
        frames_at_position = self._frames_per_position.get(scan_position_flat, 0)

        # If this is the first frame at this position
        if frames_at_position == 0:
            # Store at index 0
            self.data[scan_position_flat, 0] = frame_data
        else:
            current_frames_dim = self.data.shape[1]

            # Check if we need to expand the data array
            if frames_at_position >= current_frames_dim:
                # Increase the frame dimension by exactly one
                new_frame_dim = frames_at_position + 1
                new_shape = (self.data.shape[0], new_frame_dim)
                new_data = np.empty(new_shape, dtype=object)

                # Copy existing data
                new_data[:, :current_frames_dim] = self.data

                # Initialize remaining slots with empty arrays
                empty_array = np.array([], dtype=self.dtype)
                for i in range(self.data.shape[0]):
                    for j in range(current_frames_dim, new_frame_dim):
                        new_data[i, j] = empty_array

                # Replace data with expanded array
                self.data = new_data

            # Store the new frame at the next available index
            self.data[scan_position_flat, frames_at_position] = frame_data

        # Update tracking information
        self._frames_per_position[scan_position_flat] = frames_at_position + 1
        self.num_frames_added += 1


def get_summed_diffraction_pattern(
    accumulator: FrameAccumulator, subsample_step: int = 2
) -> np.ndarray:
    """Calculate summed diffraction pattern from frames in accumulator."""
    scan_number = accumulator.scan_number
    num_frames = accumulator.num_frames_added

    if num_frames == 0:
        raise ValueError(f"Scan {scan_number}: No frames available for summing")

    # Get indices to sum
    added_indices = sorted(accumulator.frames_added_indices)
    indices_to_sum = added_indices[::subsample_step]

    if not indices_to_sum:
        raise ValueError(f"Scan {scan_number}: No frames left after subsampling")

    # Save original shape
    original_shape = accumulator.shape
    accumulator.ravel_scans()

    try:
        subset = accumulator[indices_to_sum]

        if not isinstance(subset, SparseArray):
            raise TypeError(f"Expected SparseArray subset, got {type(subset)}")

        summed_dp = subset.sum(axis=subset.scan_axes, dtype=np.float64)

        if summed_dp is None or summed_dp.sum() == 0:
            raise ValueError(f"Scan {scan_number}: Summed DP is empty")

        return summed_dp

    finally:
        if accumulator.shape != original_shape:
            accumulator.shape = original_shape


def calculate_diffraction_center(diffraction_pattern: np.ndarray) -> tuple[int, int]:
    """
    Calculates the beam center from a diffraction pattern using center of mass.

    Args:
        diffraction_pattern: 2D NumPy array of the diffraction pattern
        scan_number: Optional scan number for logging purposes

    Returns:
        Tuple of (center_x, center_y) coordinates

    Raises:
        ValueError: If diffraction pattern is empty or center calculation fails
    """
    # Validate input
    if diffraction_pattern is None or diffraction_pattern.size == 0:
        raise ValueError("Empty diffraction pattern")

    # Calculate center of mass using stempy function
    center_yx = stim.com_dense(diffraction_pattern)

    # Validate result
    if center_yx is None or center_yx.size == 0 or np.isnan(center_yx).any():
        raise ValueError("Center calculation failed")

    # Convert to integer coordinates (x,y)
    center = (int(center_yx[1, 0]), int(center_yx[0, 0]))

    logger.debug(f"Calculated center at {center}")
    return center


def get_diffraction_center(
    accumulator: FrameAccumulator, subsample_step: int = 2
) -> tuple[int, int]:
    """
    Convenience function that calculates the diffraction center from an accumulator.

    Args:
        accumulator: FrameAccumulator containing sparse frames
        subsample_step: Step size for subsampling positions

    Returns:
        Tuple of (center_x, center_y) coordinates

    Raises:
        ValueError: If calculation fails at any stage
    """
    # Get the summed diffraction pattern
    summed_dp = get_summed_diffraction_pattern(
        accumulator, subsample_step=subsample_step
    )

    # Calculate center from the pattern
    return calculate_diffraction_center(summed_dp)


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
