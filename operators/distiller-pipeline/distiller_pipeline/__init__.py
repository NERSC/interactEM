import multiprocessing
import multiprocessing.synchronize
import os
import sys
import time
from collections import defaultdict
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


class ReceiverInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    module: int = 0
    n_messages: int = 0
    scan_number: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "ReceiverInfo":
        if isinstance(data, list) and len(data) >= 4:
            try:
                return cls(
                    status=data[0],
                    module=data[1],
                    n_messages=data[2],
                    scan_number=data[3],
                )
            except (ValidationError, ValueError, TypeError):
                pass

        return cls()


class ReceiversInfo(BaseModel):
    n_messages: int = 0
    receivers: dict[int, dict[int, ReceiverInfo]] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "ReceiversInfo":
        instance_data: dict[str, Any] = {
            "n_messages": 0,
            "receivers": {},
        }
        if isinstance(data, list) and len(data) >= 2:
            try:
                instance_data["n_messages"] = int(data[0])
            except (ValueError, TypeError):
                pass

            if isinstance(data[1], dict):
                try:
                    instance_data["receivers"] = {
                        int(module): {
                            int(thread_id): ReceiverInfo.from_msgpack(info_data)
                            for thread_id, info_data in threads_map.items()
                        }
                        for module, threads_map in data[1].items()
                    }
                except (ValueError, TypeError):
                    instance_data["receivers"] = {}

        try:
            return cls(**instance_data)
        except ValidationError:
            return cls()


class AggregatorInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    module: int = 0
    n_messages: int = 0
    scan_number: int = 0
    thread_id: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "AggregatorInfo":
        if isinstance(data, list) and len(data) >= 5:
            try:
                return cls(
                    status=data[0],
                    module=data[1],
                    n_messages=data[2],
                    scan_number=data[3],
                    thread_id=data[4],
                )
            except (ValidationError, ValueError, TypeError):
                pass
        return cls()


class AggregatorsInfo(BaseModel):
    n_messages: int = 0
    aggregators: dict[int, dict[int, AggregatorInfo]] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "AggregatorsInfo":
        instance_data: dict[str, Any] = {
            "n_messages": 0,
            "aggregators": {},
        }
        if isinstance(data, list) and len(data) >= 2:
            try:
                instance_data["n_messages"] = int(data[0])
            except (ValueError, TypeError):
                pass

            if isinstance(data[1], dict):
                try:
                    instance_data["aggregators"] = {
                        int(module): {
                            int(thread_id): AggregatorInfo.from_msgpack(info_data)
                            for thread_id, info_data in threads_map.items()
                        }
                        for module, threads_map in data[1].items()
                    }
                except (ValueError, TypeError):
                    instance_data["aggregators"] = {}

        try:
            return cls(**instance_data)
        except ValidationError:
            return cls()


class NodeGroupThreadInfo(BaseModel):
    status: int = MessagingStatus.IDLE
    n_messages: int = 0
    scan_number: int = 0
    short_id: int = 0
    mpi_rank: int = 0

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "NodeGroupThreadInfo":
        if isinstance(data, list) and len(data) >= 5:
            try:
                return cls(
                    status=data[0],
                    n_messages=data[1],
                    scan_number=data[2],
                    short_id=data[3],
                    mpi_rank=data[4],
                )
            except (ValidationError, ValueError, TypeError):
                pass
        return cls()


class NodeInfo(BaseModel):
    n_messages: int = 0
    node_id: str = "0"
    node_group_thread_info: dict[int, dict[int, dict[int, NodeGroupThreadInfo]]] = (
        Field(default_factory=dict)
    )

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "NodeInfo":
        instance_data: dict[str, Any] = {
            "n_messages": 0,
            "node_id": "0",
            "node_group_thread_info": {},
        }
        if isinstance(data, list) and len(data) >= 3:
            try:
                instance_data["n_messages"] = int(data[0])
            except (ValueError, TypeError):
                pass

            node_id_raw = data[1]
            try:
                instance_data["node_id"] = (
                    node_id_raw.decode("utf-8")
                    if isinstance(node_id_raw, bytes)
                    else str(node_id_raw)
                )
            except UnicodeDecodeError:
                instance_data["node_id"] = str(node_id_raw)

            if isinstance(data[2], dict):
                try:
                    instance_data["node_group_thread_info"] = {
                        int(mpi_rank): {
                            int(short_id): {
                                int(thread_id): NodeGroupThreadInfo.from_msgpack(
                                    info_data,
                                )
                                for thread_id, info_data in threads_map.items()
                            }
                            for short_id, threads_map in short_ids_map.items()
                        }
                        for mpi_rank, short_ids_map in data[2].items()
                    }
                except (ValueError, TypeError):
                    instance_data["node_group_thread_info"] = {}

        try:
            return cls(**instance_data)
        except ValidationError:
            return cls()


class SharedState(BaseModel):
    receiver_map: dict[str, ReceiversInfo] = Field(default_factory=dict)
    aggregator_map: dict[str, AggregatorsInfo] = Field(default_factory=dict)
    node_map: dict[str, NodeInfo] = Field(default_factory=dict)

    @classmethod
    def from_msgpack(cls, data: list[Any]) -> "SharedState":
        instance_data: dict[str, Any] = {
            "receiver_map": {},
            "aggregator_map": {},
            "node_map": {},
        }
        if isinstance(data, list) and len(data) >= 3:
            if isinstance(data[0], dict):
                try:
                    instance_data["receiver_map"] = {
                        (
                            k.decode("utf-8") if isinstance(k, bytes) else str(k)
                        ): ReceiversInfo.from_msgpack(v)
                        for k, v in data[0].items()
                    }
                except (UnicodeDecodeError, ValueError, TypeError):
                    instance_data["receiver_map"] = {}

            if isinstance(data[1], dict):
                try:
                    instance_data["aggregator_map"] = {
                        (
                            k.decode("utf-8") if isinstance(k, bytes) else str(k)
                        ): AggregatorsInfo.from_msgpack(v)
                        for k, v in data[1].items()
                    }
                except (UnicodeDecodeError, ValueError, TypeError):
                    instance_data["aggregator_map"] = {}

            if isinstance(data[2], dict):
                try:
                    instance_data["node_map"] = {
                        (
                            k.decode("utf-8") if isinstance(k, bytes) else str(k)
                        ): NodeInfo.from_msgpack(v)
                        for k, v in data[2].items()
                    }
                except (UnicodeDecodeError, ValueError, TypeError):
                    instance_data["node_map"] = {}

        try:
            return cls(**instance_data)
        except ValidationError:
            return cls()

    def get_receiver_dataframe_and_totals(
        self,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        """Prepares a DataFrame and totals for receiver information."""
        receiver_data = []
        receiver_totals = {}
        for rec_id in sorted(self.receiver_map.keys()):
            recs_info = self.receiver_map[rec_id]
            receiver_totals[rec_id] = recs_info.n_messages
            for module in sorted(recs_info.receivers.keys()):
                threads_dict = recs_info.receivers[module]
                for thread_id in sorted(threads_dict.keys()):
                    info = threads_dict[thread_id]
                    receiver_data.append(
                        {
                            # "Rec ID": rec_id, # Optional
                            "Module": info.module,
                            "Thread ID": thread_id,
                            "Status": messaging_status_to_string(info.status),
                            "No. Messages": info.n_messages,
                            "Scan No.": info.scan_number,
                        },
                    )
        df_receivers = pd.DataFrame(receiver_data)
        return df_receivers, receiver_totals

    def get_aggregator_dataframe_and_totals(
        self,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        """Prepares a DataFrame and totals for aggregator information."""
        aggregator_data = []
        aggregator_totals = {}
        for agg_id in sorted(self.aggregator_map.keys()):
            aggs_info = self.aggregator_map[agg_id]
            aggregator_totals[agg_id] = aggs_info.n_messages
            for module in sorted(aggs_info.aggregators.keys()):
                threads_dict = aggs_info.aggregators[module]
                for thread_id in sorted(threads_dict.keys()):
                    info = threads_dict[thread_id]
                    aggregator_data.append(
                        {
                            # "Agg ID": agg_id, # Optional
                            "Module": info.module,
                            # "Thread ID": thread_id, # Optional
                            "Status": messaging_status_to_string(info.status),
                            # "No. Messages": info.n_messages,
                            "Scan No.": info.scan_number,
                        },
                    )
        df_aggregators = pd.DataFrame(aggregator_data)
        return df_aggregators, aggregator_totals

    def get_node_group_dataframe_and_totals(
        self,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        """Prepares a DataFrame and totals for node group information."""
        node_group_data = []
        node_totals = {}
        for node_key in sorted(self.node_map.keys()):
            node_info = self.node_map[node_key]
            node_totals[node_info.node_id] = node_info.n_messages

            aggregated_groups: dict[tuple[int, int], dict[str, Any]] = defaultdict(
                lambda: {
                    "n_messages": 0,
                    "status": MessagingStatus.IDLE,
                    "scan_num": float("inf"),
                },
            )
            for mpi_rank in sorted(node_info.node_group_thread_info.keys()):
                short_id_dict = node_info.node_group_thread_info[mpi_rank]
                for short_id in sorted(short_id_dict.keys()):
                    thread_id_dict = short_id_dict[short_id]
                    group_key = (mpi_rank, short_id)
                    for thread_id in sorted(thread_id_dict.keys()):
                        ng_thread_info = thread_id_dict[thread_id]
                        aggregated_groups[group_key]["n_messages"] += (
                            ng_thread_info.n_messages
                        )
                        aggregated_groups[group_key]["status"] = ng_thread_info.status
                        aggregated_groups[group_key]["scan_num"] = min(
                            aggregated_groups[group_key]["scan_num"],
                            ng_thread_info.scan_number,
                        )

            for (mpi_rank, short_id), data in sorted(aggregated_groups.items()):
                scan_num_str = (
                    str(data["scan_num"]) if data["scan_num"] != float("inf") else "0"
                )
                node_group_data.append(
                    {
                        "Node ID": node_info.node_id,
                        "MPI Rank": mpi_rank,
                        "ShortID": short_id,
                        "Status": messaging_status_to_string(data["status"]),
                        "Scan No.": scan_num_str,
                    },
                )
        df_node_groups = pd.DataFrame(node_group_data)
        return df_node_groups, node_totals

    def print(self: "SharedState") -> None:
        # --- Prepare DataFrames using methods from SharedState ---
        df_receivers, receiver_totals = self.get_receiver_dataframe_and_totals()
        df_aggregators, aggregator_totals = self.get_aggregator_dataframe_and_totals()
        df_node_groups, node_totals = self.get_node_group_dataframe_and_totals()

        # --- Configure Pandas Display ---
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        pd.set_option("display.colheader_justify", "left")

        # --- Clear Screen ---
        try:
            os.system("clear")
        except OSError:
            print("\n" * 50)

        # --- Print Receivers ---
        print("--- Receivers ---")
        if not df_receivers.empty:
            # Ensure correct columns are present before printing
            cols_to_print = [
                "Module",
                "Thread ID",
                "Status",
                "No. Messages",
                "Scan No.",
            ]
            print(df_receivers[cols_to_print].to_string(index=False))
            # Print totals after the table
            for rec_id, total in receiver_totals.items():
                print(f"Total Messages for {rec_id}: {total}")
        else:
            print("No receiver data.")
        print("\n")

        # --- Print Aggregators ---
        print("--- Aggregators ---")
        if not df_aggregators.empty:
            # Ensure correct columns are present before printing
            cols_to_print = ["Module", "Status", "Scan No."]
            print(df_aggregators[cols_to_print].to_string(index=False))
        else:
            print("No aggregator data.")
        print("\n")

        # --- Print Node Groups ---
        print("--- Node Groups ---")
        if not df_node_groups.empty:
            df_node_groups = df_node_groups.sort_values(
                by=["Node ID", "MPI Rank", "ShortID"],
            )
            # Ensure correct columns are present before printing
            cols_to_print = ["Node ID", "MPI Rank", "ShortID", "Status", "Scan No."]
            print(df_node_groups[cols_to_print].to_string(index=False))
        else:
            print("No node group data.")
        print("\n")

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
        instance_data: dict[str, Any] = {
            "sequence": 0,
            "state_location_origin": 0,
            "key": "",
            "properties": {},
            "body": "",
            "shared_state": SharedState(),
        }
        if isinstance(data, list) and len(data) >= 6:
            try:
                instance_data["sequence"] = int(data[0])
                instance_data["state_location_origin"] = int(data[1])
            except (ValueError, TypeError):
                pass

            key_raw = data[2]
            try:
                instance_data["key"] = (
                    key_raw.decode("utf-8")
                    if isinstance(key_raw, bytes)
                    else str(key_raw)
                )
            except UnicodeDecodeError:
                instance_data["key"] = str(key_raw)

            properties_raw = data[3]
            if isinstance(properties_raw, dict):
                try:
                    instance_data["properties"] = {
                        (k.decode("utf-8") if isinstance(k, bytes) else str(k)): (
                            v.decode("utf-8") if isinstance(v, bytes) else str(v)
                        )
                        for k, v in properties_raw.items()
                    }
                except (UnicodeDecodeError, ValueError, TypeError):
                    instance_data["properties"] = {}

            body_raw = data[4]
            try:
                instance_data["body"] = (
                    body_raw.decode("utf-8")
                    if isinstance(body_raw, bytes)
                    else str(body_raw)
                )
            except UnicodeDecodeError:
                instance_data["body"] = str(body_raw)

            if isinstance(data[5], list):
                instance_data["shared_state"] = SharedState.from_msgpack(data[5])

        try:
            return cls(**instance_data)
        except ValidationError:
            return cls()


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
            print(
                f"[Client] Error binding IPC socket {self._update_pull_address}: {e}."
            )
            self._cleanup_ipc_file()
            try:
                self._update_pull_socket.bind(self._update_pull_address)
                print("[Client] Successfully bound IPC socket after cleanup.")
            except Exception as bind_e:
                print(
                    f"[Client] Failed to bind IPC socket even after cleanup: {bind_e}"
                )
                raise e

        self._update_poller = zmq.Poller()
        self._update_poller.register(self._update_pull_socket, zmq.POLLIN)

        self.current_head_node_id: str | None = None
        self._latest_state: SharedState | None = None

    def _cleanup_ipc_file(self):
        """Removes the IPC socket file if it exists."""
        ipc_socket_path = self._update_pull_address.replace("ipc://", "")
        try:
            if os.path.exists(ipc_socket_path):
                os.unlink(ipc_socket_path)
                print(f"[Client] Removed existing IPC socket file: {ipc_socket_path}")
        except OSError as e:
            print(f"[Client] Error removing IPC socket file {ipc_socket_path}: {e}")
        except Exception as e:
            print(f"[Client] Unexpected error removing IPC file: {e}")

    @staticmethod
    def _run_background_process(
        pub_address: str,
        update_push_address: str,
        stop_event: multiprocessing.synchronize.Event,
    ):
        print(
            f"[BGProc:{os.getpid()}] Starting. Publisher: {pub_address}, Updates: {update_push_address}"
        )

        context = zmq.Context()
        subscriber = context.socket(zmq.SUB)
        update_pusher = context.socket(zmq.PUSH)
        poller = zmq.Poller()

        last_head_node_id: str | None = None
        sub_connected = False
        push_connected = False

        try:
            # Connect Subscriber
            print(f"[BGProc:{os.getpid()}] Connecting SUB socket to {pub_address}...")
            subscriber.connect(pub_address)
            subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
            poller.register(subscriber, zmq.POLLIN)
            sub_connected = True
            print(f"[BGProc:{os.getpid()}] SUB socket connected.")

            # Connect Pusher
            print(
                f"[BGProc:{os.getpid()}] Connecting PUSH socket to {update_push_address}..."
            )
            update_pusher.setsockopt(zmq.LINGER, 0)
            update_pusher.connect(update_push_address)
            push_connected = True
            print(f"[BGProc:{os.getpid()}] PUSH socket connected.")

            print(f"[BGProc:{os.getpid()}] Waiting for messages...")
            while not stop_event.is_set():
                socks = dict(poller.poll(100))

                if subscriber in socks and socks[subscriber] == zmq.POLLIN:
                    try:
                        message_bytes = subscriber.recv(zmq.NOBLOCK)
                        unpacked_list = msgpack.unpackb(
                            message_bytes, raw=True, use_list=True, strict_map_key=False
                        )
                        shared_state_msg = SharedStateMsg.from_msgpack(unpacked_list)

                        if shared_state_msg.body != "HUGZ":
                            shared_state_data = shared_state_msg.shared_state

                            # --- Send full state update ---
                            state_update_msg = StateUpdate(
                                shared_state=shared_state_data
                            )
                            update_pusher.send_pyobj(state_update_msg)
                            # -----------------------------

                            current_head_node_id = None
                            if shared_state_data and shared_state_data.node_map:
                                for node_info in shared_state_data.node_map.values():
                                    if 0 in node_info.node_group_thread_info:
                                        current_head_node_id = node_info.node_id
                                        break

                            if current_head_node_id != last_head_node_id:
                                if current_head_node_id is not None:
                                    print(
                                        f"[BGProc:{os.getpid()}] Head node connected: {current_head_node_id}"
                                    )
                                    update_msg = NodeConnectedUpdate(
                                        head_node_id=current_head_node_id
                                    )
                                    update_pusher.send_pyobj(update_msg)
                                else:
                                    if last_head_node_id is not None:
                                        print(
                                            f"[BGProc:{os.getpid()}] Head node disconnected."
                                        )
                                    update_msg = NodeDisconnectedUpdate()
                                    update_pusher.send_pyobj(update_msg)
                                last_head_node_id = current_head_node_id

                    except zmq.Again:
                        pass
                    except (
                        msgpack.UnpackException,
                        ValidationError,
                        IndexError,
                        UnicodeDecodeError,
                    ) as e:
                        print(f"[BGProc:{os.getpid()}] Error processing message: {e}")
                    except zmq.ZMQError as e:
                        print(f"[BGProc:{os.getpid()}] ZMQ Error during recv/send: {e}")
                        if e.errno == zmq.EHOSTUNREACH or e.errno == zmq.ETERM:
                            print(
                                f"[BGProc:{os.getpid()}] IPC connection likely lost. Exiting."
                            )
                            break
                    except Exception as e:
                        print(
                            f"[BGProc:{os.getpid()}] Unexpected error: {type(e).__name__}: {e}"
                        )

                if not socks:
                    time.sleep(0.05)

        except zmq.ZMQError as e:
            print(f"[BGProc:{os.getpid()}] ZMQ Error during setup/connect: {e}")
        except Exception as e:
            print(f"[BGProc:{os.getpid()}] Fatal error: {type(e).__name__}: {e}")
        finally:
            print(f"[BGProc:{os.getpid()}] Stopping...")
            # Cleanup ZMQ
            if sub_connected and subscriber and not subscriber.closed:
                try:
                    poller.unregister(subscriber)
                except KeyError:
                    pass
                subscriber.close()
            if push_connected and update_pusher and not update_pusher.closed:
                update_pusher.close()
            if context and not context.closed:
                context.term()
            print(f"[BGProc:{os.getpid()}] Cleanup complete.")

    def start(self):
        """Starts the background subscriber process."""
        if self._process is not None and self._process.is_alive():
            print("[Client] Process already running.")
            return

        print(
            f"[Client] Starting background process for pub_address: {self.pub_address}..."
        )
        self._stop_event.clear()
        # Ensure the process context is clean before starting
        # Use 'fork' on Unix-like systems if possible and not already set globally
        try:
            if multiprocessing.get_start_method(allow_none=True) is None:
                multiprocessing.set_start_method("fork")
        except (ValueError, RuntimeError) as e:
            print(f"[Client] Warning: Could not set start method to 'fork': {e}")

        self._process = multiprocessing.Process(
            target=SharedStateClient._run_background_process,  # Use static method
            args=(self.pub_address, self._update_pull_address, self._stop_event),
            daemon=True,  # Ensure process exits if main process exits uncleanly
        )
        self._process.start()
        print(f"[Client] Background process started (PID: {self._process.pid}).")

    def receive_update(self, timeout_ms: int = 0) -> BaseUpdate | None:
        """
        Checks for and receives updates (connection status or full state)
        from the background process. Updates internal state accordingly.

        Args:
            timeout_ms: Poll timeout in milliseconds. 0 for non-blocking.

        Returns:
            The received update message (NodeConnectedUpdate, NodeDisconnectedUpdate,
            StateUpdate) or None if no update or timeout.
        """
        update: BaseUpdate | None = None
        if self._update_pull_socket is None or self._update_pull_socket.closed:
            return None

        try:
            socks = dict(self._update_poller.poll(timeout_ms))
            if (
                self._update_pull_socket in socks
                and socks[self._update_pull_socket] == zmq.POLLIN
            ):
                try:
                    update = self._update_pull_socket.recv_pyobj(zmq.NOBLOCK)
                    if isinstance(update, NodeConnectedUpdate):
                        if self.current_head_node_id != update.head_node_id:
                            print(
                                f"[Client] Received NODES_CONNECTED: {update.head_node_id}"
                            )
                        self.current_head_node_id = update.head_node_id
                    elif isinstance(update, NodeDisconnectedUpdate):
                        if self.current_head_node_id is not None:
                            print("[Client] Received NODES_DISCONNECTED")
                        self.current_head_node_id = None
                    elif isinstance(update, StateUpdate):  # Handle new state update
                        self._latest_state = update.shared_state
                        # Optionally print or log state reception
                        # print("[Client] Received STATE_UPDATE")
                    else:
                        print(f"[Client] Received unknown update type: {type(update)}")
                        update = None

                except zmq.Again:
                    pass
                except (AttributeError, EOFError, ImportError, IndexError) as e:
                    print(f"[Client] Error deserializing update: {e}")
                    update = None
                except Exception as e:
                    print(f"[Client] Error receiving update: {e}")
                    update = None
        except zmq.ZMQError as e:
            print(f"[Client] ZMQ Error during poll/recv: {e}")
            if e.errno == zmq.ETERM:
                print("[Client] ZMQ Context terminated during receive.")
                self._close_ipc_resources()
            update = None
        except ValueError as e:
            print(f"[Client] ValueError during poll (potential context issue): {e}")
            update = None

        return update

    def get_current_head_node_id(self) -> str | None:
        """Returns the last known head node ID, checking for updates first."""
        self.receive_update(timeout_ms=0)  # Check for updates non-blockingly
        return self.current_head_node_id

    def get_latest_state(self) -> SharedState | None:
        """
        Returns the most recently received SharedState object.
        Checks for pending updates first.
        """
        self.receive_update(timeout_ms=0)  # Ensure latest updates are processed
        return self._latest_state

    def update_pub_address(self, new_pub_address: str, shutdown_timeout_sec: int = 5):
        """
        Updates the publisher address the background process subscribes to.
        This involves stopping the current process and starting a new one.
        """
        if new_pub_address == self.pub_address:
            print(
                f"[Client] New address '{new_pub_address}' is the same as current. No update needed."
            )
            return

        print(
            f"[Client] Updating publisher address from '{self.pub_address}' to '{new_pub_address}'..."
        )

        # 1. Shutdown the current process and client-side IPC
        print("[Client] Shutting down existing background process and IPC...")
        self.shutdown(timeout_sec=shutdown_timeout_sec)

        # 2. Update the address
        self.pub_address = new_pub_address
        print(f"[Client] Publisher address updated to: {self.pub_address}")

        # 3. Re-initialize client-side IPC and restart the process
        print("[Client] Re-initializing IPC socket...")
        self._ipc_context = zmq.Context()
        self._update_pull_socket = self._ipc_context.socket(zmq.PULL)
        self._cleanup_ipc_file()  # Clean before binding again
        try:
            self._update_pull_socket.bind(self._update_pull_address)
        except zmq.ZMQError as e:
            print(
                f"[Client] Error binding IPC socket {self._update_pull_address} on restart: {e}"
            )
            self._cleanup_ipc_file()
            try:
                self._update_pull_socket.bind(self._update_pull_address)
                print(
                    "[Client] Successfully bound IPC socket after cleanup on restart."
                )
            except Exception as bind_e:
                print(f"[Client] Failed to bind IPC socket on restart: {bind_e}")
                # If binding fails here, the client might be unusable.
                self._close_ipc_resources()  # Ensure cleanup
                return  # Exit the update method

        self._update_poller = zmq.Poller()
        self._update_poller.register(self._update_pull_socket, zmq.POLLIN)

        print("[Client] Restarting background process with new address...")
        self.start()  # Start will use the updated self.pub_address

        print("[Client] Publisher address update complete.")

    def _close_ipc_resources(self):
        """Safely close client-side IPC context and socket."""
        print("[Client] Closing client-side IPC resources...")
        # Unregister before closing socket
        if (
            hasattr(self, "_update_poller")
            and self._update_pull_socket
            and not self._update_pull_socket.closed
        ):
            try:
                self._update_poller.unregister(self._update_pull_socket)
            except KeyError:
                pass  # Ignore if already unregistered
            except Exception as e:
                print(f"[Client] Error unregistering poller: {e}")

        if (
            hasattr(self, "_update_pull_socket")
            and self._update_pull_socket
            and not self._update_pull_socket.closed
        ):
            self._update_pull_socket.close()
        self._update_pull_socket = None  # Mark as closed

        if (
            hasattr(self, "_ipc_context")
            and self._ipc_context
            and not self._ipc_context.closed
        ):
            self._ipc_context.term()
        self._ipc_context = None  # Mark as terminated

        # Attempt to remove the IPC socket file
        self._cleanup_ipc_file()

    def shutdown(self, timeout_sec: int = 5):
        """Signals the background process to stop and cleans up resources."""
        print("[Client] Initiating shutdown...")
        if self._process is not None and self._process.is_alive():
            print("[Client] Setting stop event for background process...")
            self._stop_event.set()
            print(
                f"[Client] Waiting up to {timeout_sec}s for background process (PID: {self._process.pid}) to join..."
            )
            self._process.join(timeout=timeout_sec)
            if self._process.is_alive():
                print(
                    f"[Client] Background process (PID: {self._process.pid}) did not terminate gracefully. Terminating..."
                )
                try:
                    self._process.terminate()
                    self._process.join(1)
                    if self._process.is_alive():
                        print(
                            f"[Client] Process (PID: {self._process.pid}) still alive after SIGTERM, sending SIGKILL..."
                        )
                        self._process.kill()
                        self._process.join(1)
                except ProcessLookupError:
                    print(
                        f"[Client] Process (PID: {self._process.pid}) already terminated."
                    )
                except Exception as e:
                    print(
                        f"[Client] Error terminating process {self._process.pid}: {e}"
                    )
            else:
                print(f"[Client] Background process (PID: {self._process.pid}) joined.")
            self._process = None
        else:
            print("[Client] Background process not running or already stopped.")

        # Drain final messages and close client-side IPC resources
        self._close_ipc_resources()

        print("[Client] Shutdown complete.")

    def __del__(self):
        """Attempt graceful shutdown if the client object is garbage collected."""
        print("[Client] __del__ called. Initiating shutdown...")
        self.shutdown(timeout_sec=2)  # Use a short timeout for GC
