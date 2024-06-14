import pytest

from zmglue.agent import Agent
from zmglue.models.pipeline import PipelineJSON
from zmglue.pipeline import Pipeline


@pytest.fixture
def init_agent_without_orchestrator(pipeline: PipelineJSON):
    agent = Agent()
    agent.pipeline = Pipeline.from_pipeline(pipeline)
    yield agent
    agent.stop()
    agent.shutdown()


def test_start_operators(init_agent_without_orchestrator: Agent):
    agent = init_agent_without_orchestrator
    processes = agent.start_operators()
    assert len(processes) == len(agent.pipeline.operators)
    for process in processes.values():
        assert process.poll() is None  # Check that the process is still running

    agent.stop()
    agent.shutdown()
