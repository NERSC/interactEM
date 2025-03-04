import multiprocessing
import signal
import sys
from enum import Enum
from typing import Any

import msgpack
import zmq
from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    BytesMessage,
    MessageHeader,
    MessageSubject,
)
from interactem.operators.operator import dependencies, operator

logger = get_logger()


class FourdCameraHeader:
    def __init__(
        self,
        scan_number=0,
        frame_number=0,
        num_frames_this_thread=0,
        nSTEM_positions_per_row_m1=0,
        nSTEM_rows_m1=0,
        STEM_x_position_in_row=0,
        STEM_row_in_scan=0,
        thread_id=0,
        module=0,
    ):
        self.scan_number = scan_number
        self.frame_number = frame_number
        self.num_frames_this_thread = num_frames_this_thread
        self.nSTEM_positions_per_row_m1 = nSTEM_positions_per_row_m1
        self.nSTEM_rows_m1 = nSTEM_rows_m1
        self.STEM_x_position_in_row = STEM_x_position_in_row
        self.STEM_row_in_scan = STEM_row_in_scan
        self.thread_id = thread_id
        self.module = module

    @staticmethod
    def from_msgpack(data):
        unpacked_data = msgpack.unpackb(data)
        return FourdCameraHeader(
            scan_number=unpacked_data[0],
            frame_number=unpacked_data[1],
            num_frames_this_thread=unpacked_data[2],
            nSTEM_positions_per_row_m1=unpacked_data[3],
            nSTEM_rows_m1=unpacked_data[4],
            STEM_x_position_in_row=unpacked_data[5],
            STEM_row_in_scan=unpacked_data[6],
            thread_id=unpacked_data[7],
            module=unpacked_data[8],
        )

    def __repr__(self):
        return (
            f"FourdCameraHeader(scan_number={self.scan_number}, frame_number={self.frame_number}, "
            f"num_frames_this_thread={self.num_frames_this_thread}, "
            f"nSTEM_positions_per_row_m1={self.nSTEM_positions_per_row_m1}, "
            f"nSTEM_rows_m1={self.nSTEM_rows_m1}, "
            f"STEM_x_position_in_row={self.STEM_x_position_in_row}, "
            f"STEM_row_in_scan={self.STEM_row_in_scan}, "
            f"thread_id={self.thread_id}, module={self.module})"
        )

    def to_dict(self):
        return {
            "scan_number": self.scan_number,
            "frame_number": self.frame_number,
            "num_frames_this_thread": self.num_frames_this_thread,
            "nSTEM_positions_per_row_m1": self.nSTEM_positions_per_row_m1,
            "nSTEM_rows_m1": self.nSTEM_rows_m1,
            "STEM_x_position_in_row": self.STEM_x_position_in_row,
            "STEM_row_in_scan": self.STEM_row_in_scan,
            "thread_id": self.thread_id,
            "module": self.module,
        }


def zmq_worker(port):
    context = zmq.Context()
    pull_socket = context.socket(zmq.PULL)
    push_socket = context.socket(zmq.PUSH)
    pull_socket.bind(f"tcp://192.168.127.2:{port}")
    push_socket.connect("ipc:///tmp/hello")
    print(f"Process bound to port {port}")

    while True:
        try:
            msgs = pull_socket.recv_multipart()
        except zmq.ZMQError as e:
            print(f"ZMQError on port {port}: {e}")
            continue
        try:
            push_socket.send_multipart(msgs)
        except zmq.ZMQError as e:
            print(f"Error sending zeromq message {e}")


class ServerState(Enum):
    READY = "ready"
    NOT_READY = "not_ready"


def checkin_server():
    print("Starting checkin server...")
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    port = 16000
    bind_address = f"tcp://192.168.127.2:{port}"
    socket.bind(bind_address)

    server_state = ServerState.READY  # Initial state of the server

    while True:
        try:
            _ = socket.recv_string()
            if server_state == ServerState.READY:
                reply = ServerState.READY.value
            else:
                reply = ServerState.NOT_READY.value
            socket.send_string(reply)

        except zmq.ZMQError as e:
            print(f"Error during receive/send: {e}")


def signal_handler(sig, frame, processes):
    print("Shutting down...")
    for p in processes:
        p.terminate()
    sys.exit(0)


def create_zmq_processes() -> list[multiprocessing.Process]:
    ports = [6001, 6002, 6003, 6004]
    processes = []
    signal.signal(
        signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, processes)
    )
    for port in ports:
        p = multiprocessing.Process(target=zmq_worker, args=(port,))
        p.start()
        processes.append(p)

    p = multiprocessing.Process(target=checkin_server)
    p.start()
    processes.append(p)
    return processes


def teardown_zmq_processes(processes: list[multiprocessing.Process]):
    for p in processes:
        p.join()


@dependencies
def zmq_processes():
    logger.info("Creating ZMQ processes...")
    processes = create_zmq_processes()
    yield
    logger.info("Tearing down ZMQ processes...")
    teardown_zmq_processes(processes)


ctx = zmq.Context()
socket = ctx.socket(zmq.PULL)
socket.bind("ipc:///tmp/hello")

first_time = True


@operator
def receive_from_zmq_processes_and_send(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    global first_time
    msgs = socket.recv_multipart()
    if len(msgs) != 2:
        logger.warning("Received incorrect number of messages, returning None.")
        return None

    header = msgs[0]
    header = FourdCameraHeader.from_msgpack(header).to_dict()
    data = msgs[1]
    header = MessageHeader(subject=MessageSubject.BYTES, meta=header)
    if first_time:
        logger.info(f"Received header: {header}")
        first_time = False
    return BytesMessage(header=header, data=data)