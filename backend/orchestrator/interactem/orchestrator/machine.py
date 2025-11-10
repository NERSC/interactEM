from typing import TYPE_CHECKING

from faststream.nats.annotations import NatsBroker as BrokerAnnotation
from nats.js import JetStreamContext
from transitions.extensions.asyncio import AsyncMachine

from interactem.core.events.pipelines import (
    PipelineUpdateEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import (
    TERMINAL_DEPLOYMENT_STATES,
    PipelineDeploymentState,
)
from interactem.core.models.kvs import AgentStatus, AgentVal
from interactem.core.nats.publish import (
    publish_deployment_update,
)

from .config import cfg
from .types import DeploymentID

if TYPE_CHECKING:
    from .state import OrchestratorState

logger = get_logger()


class DeploymentStateMachine(AsyncMachine):
    # State enum shortcuts for cleaner transition definitions
    PENDING = PipelineDeploymentState.PENDING
    AGENTS_ASSIGNED = PipelineDeploymentState.AGENTS_ASSIGNED
    FAILED_TO_START = PipelineDeploymentState.FAILED_TO_START
    FAILURE_ON_AGENT = PipelineDeploymentState.FAILURE_ON_AGENT
    RUNNING = PipelineDeploymentState.RUNNING
    CANCELLED = PipelineDeploymentState.CANCELLED

    # transition definitions: (trigger, [source_states], dest_state)
    TRANSITIONS = [
        ("assign", [PENDING], AGENTS_ASSIGNED),

        ("start_failure", [PENDING, AGENTS_ASSIGNED], FAILED_TO_START),
        ("start_failure", [FAILURE_ON_AGENT], "="),  # idempotent
        ("agent_failure", [AGENTS_ASSIGNED, RUNNING], FAILURE_ON_AGENT),
        ("agent_failure", [FAILURE_ON_AGENT], "="),  # idempotent
        ("start", [AGENTS_ASSIGNED], RUNNING),
        ("start", [RUNNING], "="),  # running -> running transition
        # anything can be cancelled
        ("cancel", [PENDING, AGENTS_ASSIGNED, RUNNING, FAILURE_ON_AGENT], CANCELLED),
        ("cancel", [CANCELLED], "="),  # idempotent
    ]

    def __init__(self, id: DeploymentID, broker: BrokerAnnotation, **kwargs):
        self.broker = broker
        self.id = id

        states = [
            self.PENDING,
            self.AGENTS_ASSIGNED,
            {"name": self.FAILED_TO_START, "final": True},
            self.FAILURE_ON_AGENT,
            self.RUNNING,
            {"name": self.CANCELLED, "final": True},
        ]

        transitions = [
            {
                "trigger": trigger,
                "source": source,
                "dest": dest,
                "after": "publish_state_update" if dest != "=" else None,
            }
            for trigger, sources, dest in self.TRANSITIONS
            for source in sources
        ]

        super().__init__(
            model=self,
            states=states,
            transitions=transitions,
            initial=self.PENDING,
            **kwargs,
        )

    @property
    def js(self) -> JetStreamContext:
        return self.broker.config.connection_state.stream

    @property
    def current_state(self) -> PipelineDeploymentState:
        return self.state

    async def publish_state_update(self):
        """Publish the current deployment state as an update event."""
        update = PipelineUpdateEvent(
            deployment_id=self.id,
            state=self.current_state,
        )
        await publish_deployment_update(
            self.js, update, api_key=cfg.ORCHESTRATOR_API_KEY
        )


class AgentTracker:
    def __init__(
        self,
        val: AgentVal,
        broker: BrokerAnnotation,
        deployment: DeploymentStateMachine | None = None,
    ):
        self.id = val.uri.id
        self.val = val
        self.broker = broker
        self.deployment = deployment
        self.state = val.status

    async def update(
        self,
        orchestrator_state: "OrchestratorState",
        new_val: AgentVal,
        old_val: AgentVal | None = None,
    ) -> None:
        """Update tracker based on AgentVal changes."""
        self.val = new_val
        self.state = new_val.status

        # Handle deployment changes
        if old_val and new_val.current_deployment_id != old_val.current_deployment_id:
            await self._handle_deployment_change(
                orchestrator_state,
                new_val.current_deployment_id,
                old_val.current_deployment_id,
            )

        # Handle status changes
        if old_val and old_val.status != new_val.status and self.deployment:
            await self._handle_status_change(new_val.status, old_val.status)

    async def _handle_deployment_change(
        self,
        orchestrator_state: "OrchestratorState",
        new_id: DeploymentID | None,
        old_id: DeploymentID | None,
    ):
        logger.info(f"Agent {self.id} deployment: {old_id} -> {new_id}")

        # Cancel old deployment if it exists and isn't in terminal state
        if old_id and new_id != old_id:
            old_deployment = await orchestrator_state.get_deployment_sm(old_id)
            if (
                old_deployment
                and old_deployment.state not in TERMINAL_DEPLOYMENT_STATES
            ):
                await old_deployment.cancel()

        # Update deployment reference
        if new_id is None:
            self.deployment = None
        elif new_id and orchestrator_state:
            self.deployment = await orchestrator_state.get_deployment_sm(new_id)
            logger.info(f"Linked agent {self.id} to deployment {new_id}")

    async def _handle_status_change(
        self, new_status: AgentStatus, old_status: AgentStatus
    ):
        if not self.deployment:
            return

        status_transitions = {
            AgentStatus.DEPLOYMENT_RUNNING: self.deployment.start,
            AgentStatus.DEPLOYMENT_ERROR: self.deployment.agent_failure,
            AgentStatus.SHUTTING_DOWN: self.deployment.cancel,
        }

        if new_status in status_transitions:
            await status_transitions[new_status]()

    async def cleanup(self):
        if self.deployment and self.deployment.state not in TERMINAL_DEPLOYMENT_STATES:
            logger.info(
                f"Cancelling deployment {self.deployment.id} for agent {self.id}"
            )
            await self.deployment.cancel()
