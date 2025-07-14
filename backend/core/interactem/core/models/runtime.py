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
from interactem.core.models.uri import OperatorURI, PipelineURI, PortURI

RuntimeOperatorID = IdType
RuntimePipelineID = IdType
RuntimePortID = IdType


class RuntimeOperator(CanonicalOperator):
    id: RuntimeOperatorID
    canonical_id: CanonicalOperatorID
    uri: OperatorURI | None = None
    parallel_index: int = 0
    env: dict[str, str] = {}  # Environment variables to pass to the container
    command: str | list[str] = []  # Command to pass to the container
    network_mode: NetworkMode | None = None  # Network mode for the container

    @classmethod
    def from_canonical(
        cls,
        canonical_operator: CanonicalOperator,
        runtime_id: RuntimeOperatorID,
        parallel_index: int = 0,
        uri: OperatorURI | None = None,
    ) -> "RuntimeOperator":
        return cls(
            id=runtime_id,
            canonical_id=canonical_operator.id,
            uri=uri,
            parallel_index=parallel_index,
            # Canonical fields
            image=canonical_operator.image,
            parameters=canonical_operator.parameters,
            inputs=canonical_operator.inputs,
            outputs=canonical_operator.outputs,
            tags=canonical_operator.tags,
            parallel_config=canonical_operator.parallel_config,
        )

    def to_canonical(self) -> CanonicalOperator:
        return CanonicalOperator(
            id=self.canonical_id,
            image=self.image,
            parameters=self.parameters,
            inputs=self.inputs,
            outputs=self.outputs,
            tags=self.tags,
            parallel_config=self.parallel_config,
        )


class AgentRuntimeOperator(RuntimeOperator, MountMixin):
    # We need to check resolve mounts on the agent side
    pass


class RuntimePort(CanonicalPort):
    id: RuntimePortID
    canonical_id: CanonicalPortID
    operator_id: RuntimeOperatorID  # The operator this port belongs to
    canonical_operator_id: CanonicalOperatorID
    uri: PortURI | None = None

    @classmethod
    def from_canonical(
        cls,
        canonical_port: CanonicalPort,
        runtime_id: RuntimePortID,
        runtime_operator_id: RuntimeOperatorID,
        uri: PortURI | None = None,
    ) -> "RuntimePort":
        return cls(
            id=runtime_id,
            canonical_id=canonical_port.id,
            operator_id=runtime_operator_id,
            canonical_operator_id=canonical_port.operator_id,
            uri=uri,
            port_type=canonical_port.port_type,
            portkey=canonical_port.portkey,
        )

    def to_canonical(self) -> CanonicalPort:
        return CanonicalPort(
            id=self.canonical_id,
            operator_id=self.canonical_operator_id,
            port_type=self.port_type,
            portkey=self.portkey,
        )


class RuntimeInput(RuntimePort):
    port_type: PortType = PortType.input


class RuntimeOutput(RuntimePort):
    port_type: PortType = PortType.output


class RuntimeEdge(CanonicalEdge):
    pass


class RuntimePipeline(CanonicalPipeline):
    id: RuntimePipelineID  # ID of the pipeline run
    canonical_id: CanonicalPipelineID
    uri: PipelineURI | None = None
    operators: Sequence[RuntimeOperator] = []
    ports: Sequence[RuntimePort] = []
    edges: Sequence[RuntimeEdge] = []


class AgentRuntimePipeline(RuntimePipeline):
    operators: Sequence[AgentRuntimeOperator] = []


class PipelineAssignment(BaseModel):
    agent_id: IdType
    operators_assigned: list[RuntimeOperatorID] = []
    pipeline: RuntimePipeline
