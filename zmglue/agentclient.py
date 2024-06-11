import time

import zmq

from zmglue.config import cfg
from zmglue.logger import get_logger
from zmglue.models import (
    OperatorID,
    PipelineMessage,
    PortID,
    URIBase,
    URIConnectMessage,
    URIConnectResponseMessage,
    URIUpdateMessage,
    URIZmq,
)
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("container", "DEBUG")


AGENT_URI = URIZmq.from_uri(cfg.AGENT_URI)


class AgentClient:
    def __init__(self, id: OperatorID, context: zmq.SyncContext | None = None):
        self.context = zmq.Context() if context is None else context
        self.id = id
        self.socket = Socket(
            SocketInfo(
                type=zmq.REQ,
                uris=[AGENT_URI],
                bind=False,
            ),
            self.context,
        )
        self.socket.bind_or_connect()

    def update_uri(self, uri_update: URIUpdateMessage) -> URIUpdateMessage:

        logger.info(f"Updating URI on Orchestrator: {uri_update}")
        self.socket.send_model(uri_update)
        response = self.socket.recv_model()
        if not isinstance(response, URIUpdateMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")

        logger.info(f"Received URI assignment: {response}")
        return response

    def get_pipeline(self) -> PipelineMessage:
        self.socket.send_model(PipelineMessage(node_id=self.id))
        response = self.socket.recv_model()
        if not isinstance(response, PipelineMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")
        return response

    def get_connect_uris(self, port_id: PortID) -> list[URIBase]:
        input_connect_uri_request = URIConnectMessage(id=port_id)
        attempt_counter = 0
        max_retries = 5
        while True:
            logger.info(
                f"Asking for input connection URI...{input_connect_uri_request}"
            )
            self.socket.send_model(input_connect_uri_request)
            response = self.socket.recv_model()
            if attempt_counter > max_retries:
                raise Exception(
                    f"Failed to get URI assignment after {max_retries} attempts."
                )

            if not isinstance(response, URIConnectResponseMessage):
                logger.error(f"Received invalid response: {response}")
                attempt_counter += 1
                time.sleep(1)
                continue

            break

        return response.connections
