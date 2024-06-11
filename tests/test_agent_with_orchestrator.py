import threading
import time

from zmglue.agent import Agent
from zmglue.models import PipelineMessage


def test_get_pipeline(init_agent_with_orchestrator: Agent, pipeline):
    response = init_agent_with_orchestrator.get_pipeline()
    assert isinstance(response, PipelineMessage)
    assert response.pipeline == pipeline
    assert response.pipeline is not None


def test_start(init_agent_with_orchestrator: Agent):
    # Start the agent run in a separate thread to allow the test to proceed
    init_agent_with_orchestrator.start()

    time.sleep(1)  # Allow some time for the run method to process

    assert len(init_agent_with_orchestrator.processes) == len(
        init_agent_with_orchestrator.pipeline.operators
    )
    init_agent_with_orchestrator.stop()
    init_agent_with_orchestrator.shutdown()
