import threading
import time

from zmglue.agent import Agent
from zmglue.types import PipelineMessage


def test_get_pipeline(initialized_agent: Agent, orchestrator, pipeline):
    response = initialized_agent.get_pipeline()
    assert isinstance(response, PipelineMessage)
    assert response.pipeline == pipeline
    assert response.pipeline is not None


def test_run(agent: Agent):
    # Start the agent run in a separate thread to allow the test to proceed
    agent.start()

    time.sleep(1)  # Allow some time for the run method to process

    assert len(agent.processes) == len(agent.pipeline.operators)
    agent.stop()
