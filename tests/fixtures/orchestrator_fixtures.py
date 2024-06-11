import pytest

from zmglue.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    orchestrator = Orchestrator()
    orchestrator.start()
    yield orchestrator

    orchestrator.stop()
