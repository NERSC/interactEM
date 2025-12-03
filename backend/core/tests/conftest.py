from typing import Optional, Dict
from uuid import UUID, uuid4

from interactem.core.models.base import PortType
from interactem.core.models.canonical import (
    CanonicalEdge,
    CanonicalOperator,
    CanonicalPipeline,
    CanonicalPort,
)
from interactem.core.models.spec import ParallelConfig, ParallelType


class PipelineBuilder:
    """Builder for creating test pipelines using canonical models."""

    def __init__(self) -> None:
        self.operators: list[CanonicalOperator] = []
        self.ports: list[CanonicalPort] = []
        self.edges: list[CanonicalEdge] = []
        self._port_lookup: Dict[str, CanonicalPort] = {}  # label -> port mapping

    def add_operator(
        self,
        label: str,
        parallel: bool = False,
        num_inputs: int = 1,
        num_outputs: int = 1,
        spec_id: Optional[UUID] = None,
        **kwargs,
    ) -> CanonicalOperator:
        """Add an operator with its ports to the pipeline."""
        op_id = uuid4()
        operator = CanonicalOperator(
            id=op_id,
            spec_id=spec_id or uuid4(),
            label=label,
            description=kwargs.get("description", f"{label} operator"),
            image=kwargs.get("image", f"test/{label.lower().replace(' ', '_')}:latest"),
            parameters=kwargs.get("parameters"),
            inputs=[],
            outputs=[],
            tags=kwargs.get("tags", []),
            parallel_config=ParallelConfig(type=ParallelType.EMBARRASSING)
            if parallel
            else None,
        )

        # Create input ports
        for i in range(num_inputs):
            port_key = f"input{i}" if num_inputs > 1 else "input"
            port = CanonicalPort(
                id=uuid4(),
                canonical_operator_id=op_id,
                port_type=PortType.input,
                portkey=port_key,
            )
            self.ports.append(port)
            operator.inputs.append(port.id)
            self._port_lookup[f"{label}:in:{i}"] = port

        # Create output ports
        for i in range(num_outputs):
            port_key = f"output{i}" if num_outputs > 1 else "output"
            port = CanonicalPort(
                id=uuid4(),
                canonical_operator_id=op_id,
                port_type=PortType.output,
                portkey=port_key,
            )
            self.ports.append(port)
            operator.outputs.append(port.id)
            self._port_lookup[f"{label}:out:{i}"] = port

        self.operators.append(operator)
        return operator

    def connect(
        self,
        from_op: CanonicalOperator,
        to_op: CanonicalOperator,
        from_port_idx: int = 0,
        to_port_idx: int = 0,
    ) -> "PipelineBuilder":
        """Connect two operators via their ports."""
        from_port = self._port_lookup[f"{from_op.label}:out:{from_port_idx}"]
        to_port = self._port_lookup[f"{to_op.label}:in:{to_port_idx}"]

        self.edges.append(CanonicalEdge(input_id=from_port.id, output_id=to_port.id))
        return self

    def build(self) -> CanonicalPipeline:
        """Build the canonical pipeline."""
        return CanonicalPipeline(
            id=uuid4(),
            revision_id=1,
            operators=self.operators,
            ports=self.ports,
            edges=self.edges,
        )
