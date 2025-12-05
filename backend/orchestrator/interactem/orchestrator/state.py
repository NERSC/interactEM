from enum import Enum
from typing import TypeVar

import anyio
from faststream.nats.annotations import NatsBroker as BrokerAnnotation
from nats.js import JetStreamContext
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DeliverPolicy,
)
from nats.js.kv import KV_DEL, KV_OP, KV_PURGE, KeyValue
from pydantic import BaseModel

from interactem.core.constants import (
    STREAM_DEPLOYMENTS,
    SUBJECT_PIPELINES_DEPLOYMENTS,
)
from interactem.core.events.pipelines import (
    PipelineAssignmentsEvent,
    PipelineEvent,
    PipelineEventType,
    PipelineRunEvent,
    PipelineStopEvent,
    PipelineUpdateEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import (
    RUNNING_DEPLOYMENT_STATES,
    TERMINAL_DEPLOYMENT_STATES,
    IdType,
)
from interactem.core.models.kvs import AgentVal, OperatorVal
from interactem.core.models.runtime import RuntimeOperatorID

from .machine import AgentTracker, DeploymentStateMachine
from .types import AgentID, DeploymentID

logger = get_logger()


ModelT = TypeVar("ModelT", bound=BaseModel)


async def exhaust_stream(
    psub: JetStreamContext.PullSubscription, batch_size: int = 100, timeout: float = 2.0
):
    while True:
        try:
            events = await psub.fetch(batch_size, timeout=timeout)
            if not events:
                return
            for msg in events:
                yield msg
        # hits this when no more messages to fetch
        except TimeoutError:
            return


class NoValueError(Exception):
    pass


class KvOperationType(str, Enum):
    PUT = KV_OP
    DEL = KV_DEL
    PURGE = KV_PURGE


class OrchestratorState:
    def __init__(self, broker: BrokerAnnotation):
        self.broker = broker
        self.agents: dict[AgentID, AgentVal] = {}
        self.operators: dict[RuntimeOperatorID, OperatorVal] = {}

        self.deployment_state_machines: dict[DeploymentID, DeploymentStateMachine] = {}
        self.agent_trackers: dict[AgentID, AgentTracker] = {}

        # need this to process events before we start receiving updates from agents/operators
        self._ready = anyio.Event()

    @property
    def js(self) -> JetStreamContext:
        return self.broker.config.connection_state.stream

    async def initialize(self):
        await self._replay_and_cleanup_deployments()

        self._ready.set()
        logger.info("Orchestrator state fully initialized, ready to process KV updates")

    async def _replay_and_cleanup_deployments(self):
        logger.info("Replaying deployment stream...")

        # Read last messages on DEPLOYMENTS stream for all deployments
        # ephemeral consumer, will read messages in order
        psub = await self.js.pull_subscribe(
            stream=STREAM_DEPLOYMENTS,
            subject=f"{SUBJECT_PIPELINES_DEPLOYMENTS}.>",
            config=ConsumerConfig(
                deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
                ack_policy=AckPolicy.NONE,
            ),
        )
        updates: dict[DeploymentID, PipelineUpdateEvent] = {}
        runs: dict[DeploymentID, PipelineRunEvent] = {}
        stops: dict[DeploymentID, PipelineStopEvent] = {}
        assignments: dict[DeploymentID, PipelineAssignmentsEvent] = {}
        dict_to_update: dict[PipelineEventType, dict] = {
            PipelineEventType.PIPELINE_UPDATE: updates,
            PipelineEventType.PIPELINE_ASSIGNMENTS: assignments,
            PipelineEventType.PIPELINE_RUN: runs,
            PipelineEventType.PIPELINE_STOP: stops,
        }

        # Grab messages into respective dicts
        messages_processed = 0
        async for msg in exhaust_stream(psub):
            ev = PipelineEvent.model_validate_json(msg.data)

            depl_id = ev.root.deployment_id
            event_type = ev.root.type

            if event_type in dict_to_update:
                dict_to_update[event_type][depl_id] = ev.root
            messages_processed += 1

        # Get all unique deployment IDs from all event types
        all_deployment_ids = set()
        all_deployment_ids.update(assignments.keys())
        all_deployment_ids.update(updates.keys())
        all_deployment_ids.update(runs.keys())
        all_deployment_ids.update(stops.keys())

        logger.info(
            f"Assignments: {len(assignments)}, Updates: {len(updates)}, Runs: {len(runs)}"
        )
        async with anyio.create_task_group() as tg:
            for deployment_id in all_deployment_ids:
                # Create the state machine
                sm = DeploymentStateMachine(deployment_id, self.broker)

                if deployment_id not in updates:
                    logger.warning(
                        f"No updates found for deployment {deployment_id} during replay, updating to failed state"
                    )
                    # this will trigger cleanup in db - means that we didn't get to the
                    # point of sending updates for this deployment
                    tg.start_soon(sm.start_failure)
                    continue

                # Initialize to the correct state based on last update event
                last_update = updates[deployment_id]
                deployment_state = last_update.state
                sm.set_state(deployment_state)

                # skip terminal states (TODO: for now, may want to revisit later if we do cleanup)
                if sm.current_state in TERMINAL_DEPLOYMENT_STATES:
                    continue

                # If it is not running, then cancel it (TODO: revisit later if we want to double check agents)
                if sm.current_state not in RUNNING_DEPLOYMENT_STATES:
                    logger.info(
                        f"Deployment {deployment_id} in state {sm.current_state}, triggering cleanup"
                    )
                    tg.start_soon(sm.cancel)
                    continue
                self.deployment_state_machines[deployment_id] = sm

        logger.info(
            f"Initialized {len(self.deployment_state_machines)} deployment state machines"
        )

    async def get_deployment_sm(self, deployment_id: DeploymentID):
        if deployment_id in self.deployment_state_machines:
            return self.deployment_state_machines[deployment_id]
        sm = DeploymentStateMachine(deployment_id, self.broker)
        self.deployment_state_machines[deployment_id] = sm
        return sm

    def get_agent_tracker(self, agent_val: AgentVal) -> AgentTracker:
        agent_id = agent_val.uri.id
        if agent_id not in self.agent_trackers:
            logger.info(
                f"Created agent tracker for {agent_id} in state {agent_val.status}"
            )
            tracker = AgentTracker(agent_val, self.broker)
            self.agent_trackers[agent_id] = tracker
        return self.agent_trackers[agent_id]

    async def op_entry(self, id: RuntimeOperatorID, entry: KeyValue.Entry):
        # wait for orchestrator to initialize...
        await self._ready.wait()

        # TODO: for now we don't do anything with operators
        self._entry(
            id=id,
            entry=entry,
            store=self.operators,
            model=OperatorVal,
        )

    async def agent_entry(self, id: AgentID, entry: KeyValue.Entry):
        await self._ready.wait()

        new_agent_val, old_agent_val, oper = self._entry(
            id=id,
            entry=entry,
            store=self.agents,
            model=AgentVal,
        )

        # if we deleted from the store (agent shut down),
        if oper == KvOperationType.DEL:
            if id in self.agent_trackers:
                tracker = self.agent_trackers[id]
                await tracker.cleanup()
                del self.agent_trackers[id]
            return

        if new_agent_val is None:
            return

        tracker = self.get_agent_tracker(new_agent_val)

        # Let update handle all state and deployment changes
        await tracker.update(self, new_agent_val, old_agent_val)

    def _entry(
        self,
        id: IdType,
        entry: KeyValue.Entry,
        store: dict[IdType, ModelT],
        model: type[ModelT],
    ):
        # Deletions come in as DEL/PURGE, but when TTL expires we get operation=None,
        # so entry.value == b"" is our way to catch that case (purge notification)
        if (
            entry.operation == KV_DEL
            or entry.operation == KV_PURGE
            or entry.value == b""
        ):
            if id in store:
                # we only return DEL because we only care about 2 cases: add/update and delete
                return None, store.pop(id), KvOperationType.DEL
            else:
                # Entry was already removed from store, just return early on purge notification
                return None, None, KvOperationType.DEL

        if not entry.value:
            raise NoValueError(
                f"No value found in KV entry for id: {id}, model: {model}, entry: {entry}"
            )

        # TODO: have to do this, until this q is answered:
        # https://github.com/ag2ai/faststream/issues/2627
        new_val = model.model_validate_json(entry.value)
        if id not in store:
            old_val = None
        else:
            old_val = store[id].model_copy()
        store[id] = new_val
        return new_val, old_val, KvOperationType.PUT
