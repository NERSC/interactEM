import uuid
from collections.abc import Sequence

from pydantic import BaseModel

from interactem.core.models.base import IdType, PortType
from interactem.core.models.canonical import (
    CanonicalEdge,
    CanonicalOperator,
    CanonicalOperatorID,
    CanonicalPipeline,
    CanonicalPipelineID,
    CanonicalPort,
    CanonicalPortID,
)
from interactem.core.models.containers import MountMixin, NetworkMode
from interactem.core.models.spec import OperatorSpecParameter

"""
These models represent the runtime form of a pipeline. They are converted from canonical form.
Their primary keys are runtime IDs. Our system will chat at runtime about these IDs, rather
than the canonical IDs, since we don't want to clobber.
"""


RuntimeOperatorID = IdType
RuntimePipelineID = IdType
RuntimePortID = IdType

class RuntimeOperatorParameter(OperatorSpecParameter):
    value: str | None = None  # Value of the parameter at runtime


class RuntimeOperator(CanonicalOperator):
    id: RuntimeOperatorID
    canonical_id: CanonicalOperatorID
    parallel_index: int = 0
    parameters: list[RuntimeOperatorParameter] | None = None  # Runtime parameters
    env: dict[str, str] = {}  # Environment variables to pass to the container
    command: str | list[str] = []  # Command to pass to the container
    network_mode: NetworkMode | None = None  # Network mode for the container

    def update_parameter_value(self, name: str, value: str | None) -> None:
        for parameter in self.parameters or []:
            if parameter.name == name:
                parameter.value = value
                return
        raise ValueError(f"Parameter '{name}' not found in operator.")

    @classmethod
    def from_canonical(
        cls,
        canonical_operator: CanonicalOperator,
        runtime_id: RuntimeOperatorID,
        parallel_index: int = 0,
    ) -> "RuntimeOperator":
        return cls(
            id=runtime_id,
            canonical_id=canonical_operator.id,
            parallel_index=parallel_index,
            **canonical_operator.model_dump(exclude={"id"}),
        )

    def to_canonical(self) -> CanonicalOperator:
        return CanonicalOperator(
            id=self.canonical_id, **self.model_dump(exclude={"id"})
        )

    @classmethod
    def replicate_from_canonical(
        cls, operator: CanonicalOperator, num_replicas: int
    ) -> list["RuntimeOperator"]:
        return [
            cls.from_canonical(
                canonical_operator=operator,
                runtime_id=uuid.uuid4(),
                parallel_index=parallel_index,
            )
            for parallel_index in range(num_replicas)
        ]


class AgentRuntimeOperator(RuntimeOperator, MountMixin):
    # We need to check resolve mounts on the agent side
    pass


class RuntimePort(CanonicalPort):
    id: RuntimePortID
    canonical_id: CanonicalPortID
    operator_id: RuntimeOperatorID  # The operator this port belongs to
    canonical_operator_id: CanonicalOperatorID

    # We want to store which canonical operator this port targets at runtime
    # This is useful for when we are expanding the pipeline
    # and we need to know which operator this port is connected to
    targets_canonical_operator_id: CanonicalOperatorID | None = None

    @classmethod
    def from_canonical(
        cls,
        canonical_port: CanonicalPort,
        runtime_id: RuntimePortID,
        runtime_operator_id: RuntimeOperatorID,
    ) -> "RuntimePort":
        return cls(
            id=runtime_id,
            canonical_id=canonical_port.id,
            operator_id=runtime_operator_id,
            **canonical_port.model_dump(exclude={"id"}),
        )

    def to_canonical(self) -> CanonicalPort:
        return CanonicalPort(id=self.canonical_id, **self.model_dump(exclude={"id"}))


class RuntimeInput(RuntimePort):
    port_type: PortType = PortType.input


class RuntimeOutput(RuntimePort):
    port_type: PortType = PortType.output


class RuntimeEdge(CanonicalEdge):
    pass


class RuntimePipeline(CanonicalPipeline):
    id: RuntimePipelineID  # ID of the pipeline run
    canonical_id: CanonicalPipelineID
    operators: Sequence[RuntimeOperator] = []
    ports: Sequence[RuntimePort] = []
    edges: Sequence[RuntimeEdge] = []


class AgentRuntimePipeline(RuntimePipeline):
    operators: Sequence[AgentRuntimeOperator] = []


class PipelineAssignment(BaseModel):
    agent_id: IdType
    operators_assigned: list[RuntimeOperatorID] = []
    pipeline: RuntimePipeline
