import signal
import subprocess
import time
from pathlib import Path
from uuid import UUID, uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.orchestrator import DEFAULT_ORCHESTRATOR_URI
from zmglue.logger import get_logger
from zmglue.pipeline import Pipeline
from zmglue.types import PipelineMessage, ProtocolZmq, URILocation, URIZmq
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("agent", "DEBUG")

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
DEFAULT_AGENT_URI = URIZmq(
    id=UUID("583cd5b3-c94d-4644-8be7-dbd4f0570e91"),
    location=URILocation.agent,
    transport_protocol=ProtocolZmq.tcp,
    hostname="localhost",
    interface="lo0",
    port=cfg.AGENT_PORT,
)


class Agent:
    def __init__(self):
        self.context = zmq.Context()
        self.req_socket = Socket(
            info=SocketInfo(
                type=zmq.REQ,
                uris=[DEFAULT_ORCHESTRATOR_URI],
                bind=False,
            ),
            context=self.context,
        )
        self.rep_socket = Socket(
            SocketInfo(
                type=zmq.REP,
                uris=[DEFAULT_AGENT_URI],
                bind=True,
            ),
            self.context,
        )

        self.rep_socket.bind_or_connect()
        self.req_socket.bind_or_connect()
        self.pipeline: Pipeline | None = None
        self.processes: dict[str, subprocess.Popen] = {}

    def run(self):
        while self.pipeline is None:
            response = self.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)
            else:
                time.sleep(1)

        self.processes = self.start_nodes()
        self.setup_signal_handlers()

        try:
            while True:
                msg = self.rep_socket.recv_model()
                logger.debug(f"Received from container: {msg}")

                self.req_socket.send_model(msg)
                response = self.req_socket.recv_model()
                logger.debug(f"Received response from orchestrator: {response}")

                self.rep_socket.send_model(response)
                logger.info("Sent URI to container")
        finally:
            self.terminate_processes()

    def terminate_processes(self):
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
        logger.info(f"Received pipeline configuration: {response}")
        if not isinstance(response, PipelineMessage):
            raise ValueError(f"Invalid response: {response}")
        return response

    def start_nodes(self) -> dict[str, subprocess.Popen]:
        processes = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return processes
        try:
            pipeline = self.pipeline.to_json()
        except ValidationError as e:
            logger.error(f"No pipeline configuration found: {e}")

        for node in pipeline.operators:
            script_path = THIS_DIR / "fcontainer.py"
            if script_path.exists():
                args = [
                    "python",
                    str(script_path),
                    "--node-id",
                    str(node.id),
                ]
                logger.info(f"Starting process for node {node}")
                process = subprocess.Popen(args)
                processes[node.id] = process
                logger.info(f"Started process {process.pid} for node {node} ...")
            else:
                logger.error(f"No script found for node {node}")

        return processes