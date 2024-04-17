import argparse
import json
import socket as libsocket
import sys
from uuid import UUID, uuid4

import zmq
from pydantic import ValidationError

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.types import Protocol, ProtocolZmq, URIAssignMessage, URIMessage

logger = get_logger("container", "DEBUG")


def find_free_port():
    with libsocket.socket(libsocket.AF_INET, libsocket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(libsocket.SOL_SOCKET, libsocket.SO_REUSEADDR, 1)
        return s.getsockname()[1], libsocket.gethostname()


def main(node_id: UUID, port_id: UUID):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    agent_address = f"tcp://localhost:{cfg.AGENT_PORT}"
    socket.connect(agent_address)

    try:
        port, hostname = find_free_port()
    except Exception as e:
        print(f"Error finding an available port: {e}")
        sys.exit(1)

    logger.info(f"Found free port {port} on host {hostname}")

    uri_request = URIAssignMessage(
        node_id=node_id,
        protocol=Protocol.Zmq,
        transport_protocol=ProtocolZmq.tcp,
        port_id=port_id,
        hostname=hostname,
        port=port,
    )

    logger.info(f"Asking agent for a URI: {uri_request}")
    socket.send_json(uri_request.model_dump_json())
    response = socket.recv_json()

    try:
        response = URIAssignMessage(**json.loads(response))
    except ValidationError as e:
        logger.error(e)

    print(f"Received response: {response}")

    # # Assume the response contains the URI to bind to
    # if response.get("uri"):
    #     base_uri = BaseURI(protocol="Zmq", uri=response["uri"])
    #     bind_address = base_uri.to_address()
    #     # Now bind to the received address
    #     bind_socket = context.socket(zmq.REP)
    #     bind_socket.bind(bind_address)
    #     print(f"Bound to {bind_address}")
    #     # Wait for a message
    #     message = bind_socket.recv_string()
    #     print(f"Received message: {message}")
    #     bind_socket.close()

    socket.close()
    context.term()


parser = argparse.ArgumentParser()
parser.add_argument("--node-id", type=UUID, required=True)
parser.add_argument("--port-id", type=UUID, required=True)
args = parser.parse_args()


if __name__ == "__main__":
    node_id: UUID = args.node_id
    port_id: UUID = args.port_id
    main(node_id, port_id)
