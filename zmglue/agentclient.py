import time

import zmq

from zmglue.agent import DEFAULT_AGENT_URI
from zmglue.logger import get_logger
from zmglue.models import (
    URI,
    OperatorID,
    PipelineMessage,
    PortID,
    URIConnectMessage,
    URIConnectResponseMessage,
    URIUpdateMessage,
)
from zmglue.models.messages import OKMessage, PutPipelineNodeMessage
from zmglue.zsocket import Socket, SocketInfo

logger = get_logger("agent-client", "DEBUG")


class AgentClient:
    def __init__(self, id: OperatorID, context: zmq.SyncContext | None = None):
        self.context = zmq.Context() if context is None else context
        self.id = id
        logger.name = f"agent-client-{self.id}"
        self.socket = Socket(
            SocketInfo(
                type=zmq.REQ,
                addresses=DEFAULT_AGENT_URI.query["address"],  # type: ignore
                bind=False,
                parent_id=id,
            ),
            self.context,
        )
        self.socket.bind_or_connect()

    def __del__(self):
        self.close()

    def update_uri(self, uri_update: URIUpdateMessage) -> URIUpdateMessage:
        logger.info(f"Updating URI on Orchestrator: {uri_update}")
        self.socket.send_model(uri_update)
        response = self.socket.recv_model()
        if not isinstance(response, URIUpdateMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")

        logger.info(f"Received URI assignment: {response}")
        return response

    def put_pipeline_node(self, msg: PutPipelineNodeMessage) -> OKMessage:
        self.socket.send_model(msg)
        response = self.socket.recv_model()
        if not isinstance(response, OKMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")
        return response

    def get_pipeline(self) -> PipelineMessage:
        self.socket.send_model(PipelineMessage(node_id=self.id))
        response = self.socket.recv_model()
        if not isinstance(response, PipelineMessage):
            logger.error(f"Received invalid response: {response}")
            raise ValueError("Invalid response")
        return response

    def get_connect_uris(self, port_id: PortID) -> list[URI]:
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

    def close(self):
        self.socket.close()
        self.context.term()
