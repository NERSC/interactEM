import pytest
from orchestrator.orchestrator import Orchestrator


@pytest.fixture(scope="module")
def orchestrator():
    orchestrator = Orchestrator()
    orchestrator.start()
    yield orchestrator
    orchestrator.stop()
    orchestrator.shutdown()
