import json
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.types import MessageType, PipelineJSON, PipelineMessage, URIMessage

logger = get_logger("agent", "DEBUG")

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent


def terminate_processes(processes):
    for process in processes.values():
        logger.info(f"Terminating process {process.pid}")
        process.terminate()
        process.wait()


def setup_signal_handlers(processes):
    def signal_handler(sig, frame):
        logger.info("Signal received, shutting down processes...")
        terminate_processes(processes)
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def agent():
    logger.info("Agent starting...")
    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    rep_socket = context.socket(zmq.REP)

    logger.info(f"Connecting to orchestrator at {cfg.ORCHESTRATOR_PORT}")
    req_socket.connect(f"tcp://localhost:{cfg.ORCHESTRATOR_PORT}")
    logger.info(f"Binding agent to {cfg.AGENT_PORT}")
    rep_socket.bind(f"tcp://*:{cfg.AGENT_PORT}")

    processes = {}

    # Request pipeline configuration
    req_socket.send_json(PipelineMessage().model_dump_json())
    response = req_socket.recv_json()
    logger.info(f"Received pipeline configuration: {response}")

    response = PipelineMessage(**json.loads(response))
    pipeline = response.pipeline
    if pipeline:
        for node in pipeline.nodes:
            script_path = THIS_DIR / "fcontainer.py"
            if script_path.exists():
                args = [
                    "python",
                    str(script_path),
                    "--node-id",
                    str(node.id),
                    "--port-id",
                    str(uuid4()),
                ]
                logger.info(f"Starting process for node {node.image} with id {node.id}")
                process = subprocess.Popen(args)
                processes[node.id] = process
                logger.info(
                    f"Started process {process.pid} for node {node.image} with id {node.id}"
                )
            else:
                logger.error(f"No script found for node {node.image}")

    else:
        logger.error("No pipeline configuration found, shutting down...")
        sys.exit(1)

    setup_signal_handlers(processes)

    try:
        while True:
            msg = rep_socket.recv_json()
            logger.info(f"Received from container: {msg}")

            req_socket.send_json(msg)
            uri_response = req_socket.recv_json()
            logger.info(f"Received URI response from orchestrator: {uri_response}")

            rep_socket.send_json(uri_response)
            logger.info(f"Sent URI to container")
    finally:
        terminate_processes(processes)


if __name__ == "__main__":
    agent()
