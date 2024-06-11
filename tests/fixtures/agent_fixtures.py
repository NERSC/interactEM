import threading
import time

import pytest

from zmglue.agent import Agent
from zmglue.orchestrator import Orchestrator
from zmglue.pipeline import Pipeline
from zmglue.models import PipelineJSON


@pytest.fixture
def agent(pipeline: PipelineJSON, orchestrator: Orchestrator):
    agent = Agent()
    agent.pipeline = Pipeline.from_pipeline(pipeline)
    yield agent

    agent.terminate_processes()


@pytest.fixture
def initialized_agent(pipeline: PipelineJSON) -> Agent:
    agent = Agent()
    agent.pipeline = Pipeline.from_pipeline(pipeline)
    yield agent


def run_server_loop(agent):
    try:
        agent.server_loop()
    except KeyboardInterrupt:
        pass


@pytest.fixture
def initialized_agent_running_server_loop(initialized_agent: Agent):
    server_thread = threading.Thread(target=run_server_loop, args=(initialized_agent,))
    server_thread.start()

    time.sleep(1)  # Let the server loop run for a bit

    assert initialized_agent.pipeline is not None

    yield initialized_agent

    initialized_agent.stop()
    server_thread.join()
