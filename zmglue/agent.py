import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Event, Thread
from typing import Optional
from uuid import UUID, uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import CommBackend, PipelineMessage, URILocation
from zmglue.models.uri import URI, ZMQAddress
from zmglue.orchestrator import DEFAULT_ORCHESTRATOR_URI
from zmglue.pipeline import Pipeline
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("agent", "DEBUG")

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
DEFAULT_AGENT_URI = URI(
    id=UUID("583cd5b3-c94d-4644-8be7-dbd4f0570e91"),
    comm_backend=CommBackend.ZMQ,
    location=URILocation.agent,
    query={"address": [f"tcp://?hostname=localhost&interface=lo0&port={cfg.AGENT_PORT}"]},  # type: ignore
    hostname="localhost",
)


class Agent:
    def __init__(self):
        self.context = zmq.Context()
        self.req_socket = Socket(
            info=SocketInfo(
                type=zmq.REQ,
                addresses=DEFAULT_ORCHESTRATOR_URI.query["address"],  # type: ignore
                bind=False,
                parent_id=DEFAULT_AGENT_URI.id,
            ),
            context=self.context,
        )
        self.rep_socket = Socket(
            SocketInfo(
                type=zmq.REP,
                addresses=DEFAULT_AGENT_URI.query["address"],  # type: ignore
                bind=True,
                parent_id=DEFAULT_AGENT_URI.id,
            ),
            self.context,
        )

        self.rep_socket.bind_or_connect()
        self.req_socket.bind_or_connect()
        self.pipeline: Pipeline | None = None
        self.processes: dict[str, subprocess.Popen] = {}
        self._running = Event()
        self.thread: Optional[Thread] = None

    def run(self):
        while self.pipeline is None:
            response = self.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)
            else:
                time.sleep(1)

        self.processes = self.start_operators()
        self.server_loop()

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            logger.warning("Agent is already running.")
            return
        self.thread = Thread(target=self.run)
        self.thread.start()
        logger.info("Orchestrator started.")
        self.setup_signal_handlers()

    def stop(self):
        if not self._running.is_set():
            logger.warning("Agent is not running.")
            return
        self._running.clear()
        if self.thread:
            self.thread.join()
        self.shutdown()

    def shutdown(self):
        logger.info("Shutting down agent...")
        for socket in [self.req_socket, self.rep_socket]:
            if socket._socket:
                socket._socket.close()
        self.context.term()
        logger.info("Agent shut down successfully.")

    def server_loop(self):
        try:
            while self._running:
                msg = self.rep_socket.recv_model()
                self.req_socket.send_model(msg)
                response = self.req_socket.recv_model()
                self.rep_socket.send_model(response)
        except KeyboardInterrupt:
            pass
        except zmq.error.ContextTerminated:
            pass

    def terminate_processes(self):
        print(f"Terminating {len(self.processes)} processes...")
        for process in self.processes.values():
            logger.info(f"Terminating process {process.pid}")
            process.terminate()
            process.wait()

    def setup_signal_handlers(self):
        def signal_handler(sig, frame):
            logger.info("Signal received, shutting down processes...")
            self.terminate_processes()
            exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def get_pipeline(self) -> PipelineMessage:
        self.req_socket.send_model(PipelineMessage())
        response = self.req_socket.recv_model()
        if not isinstance(response, PipelineMessage):
            raise ValueError(f"Invalid response: {response}")
        return response

    def start_operators(self) -> dict[str, subprocess.Popen]:
        processes = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return processes
        try:
            pipeline = self.pipeline.to_json()
        except ValidationError as e:
            logger.error(f"No pipeline configuration found: {e}")
            return processes

        for id, op_info in self.pipeline.operators.items():
            script_path = THIS_DIR / "operators" / "operator0.py"
            if script_path.exists():
                args = [
                    sys.executable,  # Use the current Python interpreter
                    str(script_path),
                    "--id",
                    str(id),
                ]
                logger.info(f"Starting process for operator {id}")
                process = subprocess.Popen(
                    args,
                    env={"PYTHONBUFFERED": "1"},
                )
                processes[id] = process
                logger.info(f"Started process {process.pid} for operator {id} ...")
            else:
                logger.error(f"No script found for node {id}")

        return processes
