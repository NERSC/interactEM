import time

import pytest

from zmglue.agent import Agent
from zmglue.models import PipelineMessage
from zmglue.pipeline import Pipeline


@pytest.fixture(scope="module")
def init_agent_with_orchestrator(pipeline, orchestrator):
    agent = Agent()
    agent.pipeline = Pipeline.from_pipeline(pipeline)
    yield agent
    agent.stop()
    agent.shutdown()


def test_get_pipeline(init_agent_with_orchestrator: Agent, pipeline):
    response = init_agent_with_orchestrator.get_pipeline()
    assert isinstance(response, PipelineMessage)
    assert response.pipeline is not None
    assert (
        Pipeline.from_pipeline(response.pipeline)
        == init_agent_with_orchestrator.pipeline
    )


def test_start(init_agent_with_orchestrator: Agent):
    # Start the agent run in a separate thread to allow the test to proceed
    init_agent_with_orchestrator.start()

    time.sleep(0.5)  # Allow some time for the run method to process
    assert len(init_agent_with_orchestrator.processes) == len(
        init_agent_with_orchestrator.pipeline.operators
    )
    init_agent_with_orchestrator.stop()
    init_agent_with_orchestrator.shutdown()
