from uuid import uuid4

import pytest

from interactem.core.config import cfg
from interactem.core.models.base import PortType
from interactem.core.models.canonical import (
    CanonicalEdge,
    CanonicalOperator,
    CanonicalPipeline,
    CanonicalPort,
)
from interactem.core.models.runtime import RuntimePipeline
from interactem.core.models.spec import ParallelConfig, ParallelType
from interactem.core.pipeline import Pipeline


@pytest.fixture
def canonical() -> CanonicalPipeline:

    # Create operators
    op1 = CanonicalOperator(
        id=uuid4(),
        spec_id=uuid4(),
        label="Test Operator 1",
        description="First test operator",
        image="test/op1:latest",
        parameters=None,
        inputs=[],
        outputs=[],
        tags=[],
        parallel_config=None,  # Not parallel
    )

    # Parallel operator
    parallel_op = CanonicalOperator(
        id=uuid4(),
        spec_id=uuid4(),
        label="Parallel Test Operator",
        description="Parallel test operator",
        image="test/parallel:latest",
        parameters=None,
        inputs=[],
        outputs=[],
        tags=[],
        parallel_config=ParallelConfig(type=ParallelType.EMBARRASSING),  # Parallel
    )

    op3 = CanonicalOperator(
        id=uuid4(),
        spec_id=uuid4(),
        label="Test Operator 3",
        description="Third test operator",
        image="test/op3:latest",
        parameters=None,
        inputs=[],
        outputs=[],
        tags=[],
        parallel_config=None,  # Not parallel
    )

    # Create ports
    ports = [
        # Op1 ports
        CanonicalPort(
            id=uuid4(), canonical_operator_id=op1.id, port_type=PortType.input, portkey="input"
        ),
        CanonicalPort(
            id=uuid4(), canonical_operator_id=op1.id, port_type=PortType.output, portkey="output"
        ),
        # Parallel op ports
        CanonicalPort(
            id=uuid4(),
            canonical_operator_id=parallel_op.id,
            port_type=PortType.input,
            portkey="input",
        ),
        CanonicalPort(
            id=uuid4(),
            canonical_operator_id=parallel_op.id,
            port_type=PortType.output,
            portkey="output",
        ),
        # Op3 ports
        CanonicalPort(
            id=uuid4(), canonical_operator_id=op3.id, port_type=PortType.input, portkey="input"
        ),
        CanonicalPort(
            id=uuid4(), canonical_operator_id=op3.id, port_type=PortType.output, portkey="output"
        ),
    ]

    # Update operator port lists
    op1.inputs = [ports[0].id]
    op1.outputs = [ports[1].id]
    parallel_op.inputs = [ports[2].id]
    parallel_op.outputs = [ports[3].id]
    op3.inputs = [ports[4].id]
    op3.outputs = [ports[5].id]

    # Create edges: op1 -> parallel_op -> op3
    edges = [
        CanonicalEdge(
            input_id=ports[1].id,  # op1 output
            output_id=ports[2].id,  # parallel_op input
        ),
        CanonicalEdge(
            input_id=ports[3].id,  # parallel_op output
            output_id=ports[4].id,  # op3 input
        ),
    ]

    canonical_pipeline = CanonicalPipeline(
        id=uuid4(),
        revision_id=1,
        operators=[op1, parallel_op, op3],
        ports=ports,
        edges=edges,
    )

    return canonical_pipeline


@pytest.fixture
def pipeline_graph(canonical: CanonicalPipeline) -> Pipeline:
    return Pipeline.from_pipeline(canonical, uuid4())


def get_parallel_operator(canonical: CanonicalPipeline) -> CanonicalOperator:
    for op in canonical.operators:
        if op.parallel_config and op.parallel_config.type != ParallelType.NONE:
            return op
    raise ValueError("No parallel operator found")


def get_non_parallel_operator(canonical: CanonicalPipeline) -> CanonicalOperator:
    for op in canonical.operators:
        if not op.parallel_config or op.parallel_config.type == ParallelType.NONE:
            return op
    raise ValueError("No non-parallel operator found")


def get_parallel_factor(parallel_op: CanonicalOperator) -> int:
    return parallel_op.parallelism or cfg.PARALLEL_EXPANSION_FACTOR


class TestPipelineExpansion:
    """Test pipeline expansion from canonical to runtime models."""

    def test_roundtrip_conversion(self, canonical: CanonicalPipeline, pipeline_graph: Pipeline):
        """Test canonical -> runtime -> canonical roundtrip."""
        # Convert back to canonical
        roundtrip = pipeline_graph.to_canonical()
        assert isinstance(roundtrip, CanonicalPipeline)

        # Verify structure preserved
        assert canonical == roundtrip  # Should be equal after roundtrip

    @pytest.mark.parametrize("parallel_factor", [1, 2, 3, 5])
    def test_different_parallel_factors(self, canonical: CanonicalPipeline, parallel_factor: int):
        """Test expansion with different parallel factors."""
        parallel_op = get_parallel_operator(canonical)

        runtime_pipeline = Pipeline.from_pipeline(
            canonical, uuid4(), parallel_factor=parallel_factor
        )

        assert len(runtime_pipeline.operators) == 2 + parallel_factor, (
            "Mismatch in operator count for parallel expansion"
        )  # 2 original + parallel copies

        parallel_instances = runtime_pipeline.get_parallel_group(parallel_op.id)
        assert len(parallel_instances) == parallel_factor
        assert sorted(inst.parallel_index for inst in parallel_instances) == list(range(parallel_factor))

    def test_operator_parallelism_override(self, canonical: CanonicalPipeline):
        parallel_op = get_parallel_operator(canonical)
        override_factor = get_parallel_factor(parallel_op) + 2
        parallel_op.parallelism = override_factor

        runtime_pipeline = Pipeline.from_pipeline(canonical, uuid4(), parallel_factor=1)

        parallel_instances = runtime_pipeline.get_parallel_group(parallel_op.id)
        assert len(parallel_instances) == override_factor


class TestPipelineSerialization:
    """Test pipeline serialization and conversion."""

    def test_to_runtime_serialization(self, pipeline_graph: Pipeline):
        """Test serialization to RuntimePipeline."""
        runtime_json = pipeline_graph.to_runtime()

        assert isinstance(runtime_json, RuntimePipeline)
        assert len(runtime_json.operators) == len(pipeline_graph.operators)
        assert len(runtime_json.ports) == len(pipeline_graph.ports)

    def test_to_canonical_deduplication(self, canonical: CanonicalPipeline, pipeline_graph: Pipeline):
        """Test conversion back to canonical deduplicates parallel instances."""
        # Runtime should have expanded operators/ports
        parallel_ops = canonical.get_parallel_operators()
        expected_parallel_ops = sum(get_parallel_factor(op) for op in parallel_ops)
        expected_runtime_ops = len(canonical.operators) - len(parallel_ops) + expected_parallel_ops
        assert len(pipeline_graph.operators) == expected_runtime_ops

        # Canonical should be deduplicated back to original
        canonical_json = pipeline_graph.to_canonical()
        assert len(canonical_json.operators) == 3
        assert len(canonical_json.ports) == 6


class TestGraphOperations:
    """Test graph building and operations."""

    def test_operator_graph_and_port_queries(self, canonical: CanonicalPipeline, pipeline_graph: Pipeline):
        """Test graph construction and port queries."""
        # Test graph building
        op_graph = pipeline_graph.get_operator_graph()
        assert len(op_graph.nodes()) == len(pipeline_graph.operators)

        # Test port queries on all operators
        for runtime_op in pipeline_graph.operators.values():
            inputs = pipeline_graph.get_operator_inputs(runtime_op.id)
            outputs = pipeline_graph.get_operator_outputs(runtime_op.id)

            assert isinstance(inputs, dict)
            assert isinstance(outputs, dict)

    def test_parallel_group_retrieval(self, canonical: CanonicalPipeline, pipeline_graph: Pipeline):
        """Test getting parallel groups for both parallel and non-parallel operators."""
        parallel_op = get_parallel_operator(canonical)
        non_parallel_op = get_non_parallel_operator(canonical)
        expected_parallel = get_parallel_factor(parallel_op)

        # Test parallel operator group
        parallel_group = pipeline_graph.get_parallel_group(parallel_op.id)
        assert len(parallel_group) == expected_parallel

        # Test non-parallel operator group
        non_parallel_group = pipeline_graph.get_parallel_group(non_parallel_op.id)
        assert len(non_parallel_group) == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_pipeline_expansion(self):
        """Test expansion of empty pipeline."""
        empty_canonical = CanonicalPipeline(
            id=uuid4(), revision_id=1, operators=[], ports=[], edges=[]
        )

        empty_runtime = Pipeline.from_pipeline(empty_canonical, uuid4())

        assert len(empty_runtime.operators) == 0
        assert len(empty_runtime.ports) == 0

    def test_single_non_parallel_operator(self):
        """Test expansion of single non-parallel operator."""
        single_op = CanonicalOperator(
            id=uuid4(),
            spec_id=uuid4(),
            label="Single Test Operator",
            description="Single operator test",
            image="test:latest",
            parameters=None,
            inputs=[],
            outputs=[],
            tags=[],
            parallel_config=None,
        )

        single_pipeline = CanonicalPipeline(
            id=uuid4(), revision_id=1, operators=[single_op], ports=[], edges=[]
        )

        single_runtime = Pipeline.from_pipeline(single_pipeline, uuid4())

        # Should have exactly one operator (no expansion)
        assert len(single_runtime.operators) == 1

        # Check that the operator is properly converted
        runtime_op = list(single_runtime.operators.values())[0]
        assert runtime_op.canonical_id == single_op.id
        assert runtime_op.parallel_index == 0
