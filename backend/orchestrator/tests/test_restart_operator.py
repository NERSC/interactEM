import uuid
from unittest.mock import MagicMock, patch

import anyio
import pytest

from interactem.core.events.deployments import OperatorRestartEvent
from interactem.core.models.base import CommBackend, URILocation
from interactem.core.models.kvs import (
    AgentStatus,
    AgentVal,
    OperatorStatus,
    OperatorVal,
)
from interactem.core.models.uri import URI
from interactem.orchestrator.exceptions import (
    NoAgentAssignmentsError,
    OperatorNotFoundError,
)
from interactem.orchestrator.orchestrator import handle_restart_operator_event
from interactem.orchestrator.state import OrchestratorState


def test_restart_operator_not_found():
    """Test that OperatorNotFoundError is raised when no operators match."""
    deployment_id = uuid.uuid4()
    canonical_operator_id = uuid.uuid4()

    state = OrchestratorState(MagicMock())
    state.operators = {}
    state.agents = {}

    event = OperatorRestartEvent(
        deployment_id=deployment_id,
        canonical_operator_id=canonical_operator_id,
    )

    with pytest.raises(OperatorNotFoundError):
        anyio.run(handle_restart_operator_event, event, MagicMock(), state)


def test_restart_operator_no_agent_assignments():
    """Test that NoAgentAssignmentsError is raised when no agents are assigned."""
    deployment_id = uuid.uuid4()
    canonical_operator_id = uuid.uuid4()
    canonical_pipeline_id = uuid.uuid4()

    state = OrchestratorState(MagicMock())

    # Create operator
    operator_id = uuid.uuid4()
    operator = OperatorVal(
        id=operator_id,
        canonical_id=canonical_operator_id,
        status=OperatorStatus.RUNNING,
        canonical_pipeline_id=canonical_pipeline_id,
        runtime_pipeline_id=deployment_id,
    )

    # Create agent with no assignments
    agent_id = uuid.uuid4()
    agent = AgentVal(
        uri=URI(
            id=agent_id,
            location=URILocation.agent,
            hostname="test-host",
            comm_backend=CommBackend.NATS,
        ),
        status=AgentStatus.IDLE,
        tags=[],
        networks={"net1"},
        operator_assignments=None,
    )

    state.operators = {operator_id: operator}
    state.agents = {agent_id: agent}

    event = OperatorRestartEvent(
        deployment_id=deployment_id,
        canonical_operator_id=canonical_operator_id,
    )

    with pytest.raises(NoAgentAssignmentsError):
        anyio.run(handle_restart_operator_event, event, MagicMock(), state)


def test_restart_operator_wrong_deployment():
    """Test that OperatorNotFoundError when operator is on different deployment."""
    deployment_id = uuid.uuid4()
    canonical_operator_id = uuid.uuid4()
    canonical_pipeline_id = uuid.uuid4()

    state = OrchestratorState(MagicMock())

    operator_id = uuid.uuid4()
    operator = OperatorVal(
        id=operator_id,
        canonical_id=canonical_operator_id,
        status=OperatorStatus.RUNNING,
        canonical_pipeline_id=canonical_pipeline_id,
        runtime_pipeline_id=uuid.uuid4(),  # Different deployment
    )

    agent_id = uuid.uuid4()
    agent = AgentVal(
        uri=URI(
            id=agent_id,
            location=URILocation.agent,
            hostname="test-host",
            comm_backend=CommBackend.NATS,
        ),
        status=AgentStatus.IDLE,
        tags=[],
        networks={"net1"},
    )

    state.operators = {operator_id: operator}
    state.agents = {agent_id: agent}

    event = OperatorRestartEvent(
        deployment_id=deployment_id,
        canonical_operator_id=canonical_operator_id,
    )

    with pytest.raises(OperatorNotFoundError):
        anyio.run(handle_restart_operator_event, event, MagicMock(), state)


def test_restart_operator_success():
    """Test successful operator restart event publishing."""
    deployment_id = uuid.uuid4()
    canonical_operator_id = uuid.uuid4()
    canonical_pipeline_id = uuid.uuid4()

    operator_id = uuid.uuid4()
    operator = OperatorVal(
        id=operator_id,
        canonical_id=canonical_operator_id,
        status=OperatorStatus.RUNNING,
        canonical_pipeline_id=canonical_pipeline_id,
        runtime_pipeline_id=deployment_id,
    )

    agent_id = uuid.uuid4()
    agent = AgentVal(
        uri=URI(
            id=agent_id,
            location=URILocation.agent,
            hostname="test-host",
            comm_backend=CommBackend.NATS,
        ),
        status=AgentStatus.IDLE,
        tags=[],
        networks={"net1"},
        operator_assignments=[operator_id],
        current_deployment_id=deployment_id,
    )

    state = OrchestratorState(MagicMock())
    state.operators = {operator_id: operator}
    state.agents = {agent_id: agent}

    event = OperatorRestartEvent(
        deployment_id=deployment_id,
        canonical_operator_id=canonical_operator_id,
    )

    with patch(
        "interactem.orchestrator.orchestrator.publish_agent_deployment_event"
    ) as mock_publish:
        anyio.run(handle_restart_operator_event, event, MagicMock(), state)
        mock_publish.assert_called_once()


def test_restart_operator_filters_by_deployment():
    """Test that only agents on the specified deployment are notified."""
    deployment_id = uuid.uuid4()
    canonical_operator_id = uuid.uuid4()
    canonical_pipeline_id = uuid.uuid4()

    operator_id = uuid.uuid4()
    operator = OperatorVal(
        id=operator_id,
        canonical_id=canonical_operator_id,
        status=OperatorStatus.RUNNING,
        canonical_pipeline_id=canonical_pipeline_id,
        runtime_pipeline_id=deployment_id,
    )

    target_agent_id = uuid.uuid4()
    target_agent = AgentVal(
        uri=URI(
            id=target_agent_id,
            location=URILocation.agent,
            hostname="target-host",
            comm_backend=CommBackend.NATS,
        ),
        status=AgentStatus.IDLE,
        tags=[],
        networks={"net1"},
        operator_assignments=[operator_id],
        current_deployment_id=deployment_id,
    )

    other_agent_id = uuid.uuid4()
    other_agent = AgentVal(
        uri=URI(
            id=other_agent_id,
            location=URILocation.agent,
            hostname="other-host",
            comm_backend=CommBackend.NATS,
        ),
        status=AgentStatus.IDLE,
        tags=[],
        networks={"net1"},
        operator_assignments=[operator_id],
        current_deployment_id=uuid.uuid4(),  # Different deployment
    )

    state = OrchestratorState(MagicMock())
    state.operators = {operator_id: operator}
    state.agents = {target_agent_id: target_agent, other_agent_id: other_agent}

    event = OperatorRestartEvent(
        deployment_id=deployment_id,
        canonical_operator_id=canonical_operator_id,
    )

    with patch(
        "interactem.orchestrator.orchestrator.publish_agent_deployment_event"
    ) as mock_publish:
        anyio.run(handle_restart_operator_event, event, MagicMock(), state)
        assert mock_publish.call_count == 1
