from threading import Thread

import pytest

from zmglue.agent import Agent
from zmglue.agentclient import AgentClient
from zmglue.models import (
    URI,
    OperatorID,
    PipelineJSON,
    PipelineMessage,
    URIConnectMessage,
    URIUpdateMessage,
)
from zmglue.models.base import CommBackend, Protocol, URILocation
from zmglue.models.uri import ZMQAddress
from zmglue.orchestrator import Orchestrator
from zmglue.pipeline import Pipeline


@pytest.fixture(scope="module")
def uri_update_msg(operator_0_output_0_id: OperatorID) -> URIUpdateMessage:
    return URIUpdateMessage(
        id=operator_0_output_0_id,
        location=URILocation.port,
        hostname="sam",
        comm_backend=CommBackend.ZMQ,
        query={
            "address": [
                ZMQAddress(
                    protocol=Protocol.tcp, hostname="sam", port=5555
                ).to_address()
            ]
        },
    )


@pytest.fixture(scope="module")
def connect_msg(operator_0_output_0_id: OperatorID) -> URIConnectMessage:
    return URIConnectMessage(id=operator_0_output_0_id)


@pytest.fixture(scope="module")
def pipeline_msg(operator_0_id: OperatorID) -> PipelineMessage:
    return PipelineMessage(node_id=operator_0_id)


@pytest.fixture(scope="module")
def agent_server_loop(pipeline: PipelineJSON, orchestrator: Orchestrator):
    agent = Agent()
    agent.pipeline = Pipeline.from_pipeline(pipeline)
    thread = Thread(target=agent.server_loop, daemon=True).start()
    yield agent
    agent._running.clear()
    agent.stop()
    agent.shutdown()


@pytest.fixture
def agent_client(operator_0_id: OperatorID) -> AgentClient:
    return AgentClient(operator_0_id)


# Tests
def test_update_uri(
    agent_client: AgentClient,
    agent_server_loop,
    uri_update_msg,
):
    response = agent_client.update_uri(uri_update_msg)
    assert isinstance(response, URIUpdateMessage)
    returned_addr = ZMQAddress.from_address(response.query["address"][0])
    sent_addr = ZMQAddress.from_address(uri_update_msg.query["address"][0])
    assert returned_addr.port == sent_addr.port


def test_get_pipeline(
    agent_client: AgentClient, agent_server_loop, operator_0_id, pipeline
):
    assert agent_client.id == operator_0_id
    response = agent_client.get_pipeline()
    assert isinstance(response, PipelineMessage)
    assert response.pipeline is not None
    response_pipeline = Pipeline.from_pipeline(response.pipeline)
    assert response_pipeline


def test_get_connect_uris(
    agent_client: AgentClient, agent_server_loop, operator_1_input_0_id
):
    uris = agent_client.get_connect_uris(operator_1_input_0_id)

    assert isinstance(uris, list)
    assert len(uris) > 0
    assert isinstance(uris[0], URI)
    assert uris[0].hostname == "sam"


def test_close(agent_client: AgentClient):
    agent_client.close()
    assert agent_client.socket._socket.closed is True
    assert agent_client.context.closed is True
