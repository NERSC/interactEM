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
import pandas as pd
import zmq
from pydantic import BaseModel, Field, ValidationError


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


def receive_and_unpack_sparse_array(

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
