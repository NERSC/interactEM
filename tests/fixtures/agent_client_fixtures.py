from uuid import UUID

import pytest

from zmglue.agentclient import AgentClient
from zmglue.models import OperatorID


@pytest.fixture
def agent_client(operator_0_id: OperatorID) -> AgentClient:
    return AgentClient(operator_0_id)
