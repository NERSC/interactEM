import pytest
from interactem.core.agent import Agent
from interactem.core.models.pipeline import PipelineJSON
from interactem.core.pipeline import Pipeline


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
