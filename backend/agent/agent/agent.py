import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Thread
from uuid import UUID

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import CommBackend, PipelineMessage, URILocation
from zmglue.models.uri import URI
from zmglue.orchestrator import DEFAULT_ORCHESTRATOR_URI
from zmglue.pipeline import Pipeline
from zmglue.zsocket import Socket, SocketInfo

try:
    from podman_hpc_client import PodmanHpcClient as PodmanClient
except ImportError:
    # Fallback to podman client if podman-hpc-client is not installed for dev/test
    from podman import PodmanClient

import podman

logger = get_logger("agent", "DEBUG")

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
DEFAULT_AGENT_URI = URI(
    id=UUID("583cd5b3-c94d-4644-8be7-dbd4f0570e91"),
    comm_backend=CommBackend.ZMQ,
    location=URILocation.agent,
    query={
        "address": [
            f"tcp://?hostname=localhost&interface={cfg.AGENT_INTERFACE}&port={cfg.AGENT_PORT}"
        ]
    },  # type: ignore
    hostname="localhost",
)


class Agent:
    def __init__(self):
        self.id = DEFAULT_AGENT_URI.id  # TODO: Update to "real" uuid
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
        self._running = True
        self.thread: Thread | None = None
        self._podman_service_dir = tempfile.TemporaryDirectory(
            prefix="zmglue-", ignore_cleanup_errors=True
        )
        self._podman_service_uri = f"unix://{self._podman_service_dir.name}/podman.sock"

    def _start_podman_service(self):
        args = ["podman", "system", "service", "--time=0", self._podman_service_uri]
        logger.info(f"Starting podman service: {self._podman_service_uri}")

        # We use preexec_fn to create a new process group so that the podman service
        # doesn't get killed when the agent is killed as we needed it to perform
        # cleanup
        self._podman_process = subprocess.Popen(args, preexec_fn=os.setpgrp)

        # Wait for the service to be ready before continuing
        with PodmanClient(base_url=self._podman_service_uri) as client:
            tries = 10
            while tries > 0:
                try:
                    client.version()
                    break
                except podman.errors.exceptions.APIError:
                    logger.debug("Waiting for podman service to start")
                    time.sleep(0.1)
                    tries -= 1

            if tries == 0:
                raise RuntimeError("Podman service didn't successfully start")

            logger.info("Podman service started")

    def _stop_podman_service(self):
        if self._podman_process is not None:
            logger.info("Stopping podman service")
            self._podman_process.terminate()
            self._podman_process.wait()

    def _cleanup_containers(self):
        logger.info("Cleaning up containers...")
        with PodmanClient(base_url=self._podman_service_uri) as client:
            for container in client.containers.list(label=f"zmglue.agent.id={self.id}"):
                logger.info(f"Stopping container {container.id}")
                container.stop()
                logger.info(f"Removing container {container.id}")
                container.remove()

    def run(self):
        self.setup_signal_handlers()
        self._start_podman_service()

        while self.pipeline is None:
            response = self.get_pipeline()
            if response.pipeline:
                self.pipeline = Pipeline.from_pipeline(response.pipeline)
            else:
                time.sleep(1)

        self.processes = self.start_operators()
        self.server_loop()

    def shutdown(self):
        self._running = False
        logger.info("Shutting down agent...")
        for socket in [self.req_socket, self.rep_socket]:
            if socket._socket:
                socket._socket.close()
        self.context.term()
        self._cleanup_containers()
        self._stop_podman_service()
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

    def setup_signal_handlers(self):
        logger.info("Setting up signal handlers...")

        def signal_handler(sig, frame):
            logger.info("Signal received, shutting down processes...")
            if not self._running:
                return
            self.shutdown()
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
        containers = {}
        if not self.pipeline:
            logger.error("No pipeline configuration found...")
            return containers
        try:
            self.pipeline.to_json()
        except ValidationError as e:
            logger.error(f"No pipeline configuration found: {e}")
            return containers

        env = {k: str(v) for k, v in cfg.model_dump().items()}

        with PodmanClient(base_url=self._podman_service_uri) as client:
            for id, op_info in self.pipeline.operators.items():
                container = client.containers.create(
                    image=op_info.image,
                    environment=env,  # For now we have to pass everything through
                    name=f"operator-{id}",
                    command=["--id", str(id)],
                    detach=True,
                    network_mode="host",
                    remove=True,
                    labels={"zmglue.agent.id": str(self.id)},
                )
                container.start()
                containers[id] = container

        return containers
