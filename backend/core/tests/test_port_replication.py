"""Test cases for message replication scenarios in pipeline expansion."""

import uuid
from uuid import UUID

import networkx as nx

from interactem.core.models.base import PortType
from interactem.core.models.canonical import (
    CanonicalOperator,
    CanonicalPort,
)
from interactem.core.models.runtime import RuntimeOperator
from interactem.core.pipeline import Pipeline, get_port_fanout_map
from tests.conftest import PipelineBuilder


class TestMessageReplicationScenarios:
    """Test message replication scenarios where outputs need to be duplicated."""

    def test_output_port_replication_analysis(self) -> None:
        """Test that output port replication analysis identifies correct replication needs."""
        # Build pipeline: A -> B (parallel), A -> C, A -> D (parallel)
        builder = PipelineBuilder()
        op_a = builder.add_operator("Operator A")
        op_b = builder.add_operator("Operator B", parallel=True)
        op_c = builder.add_operator("Operator C")
        op_d = builder.add_operator("Operator D", parallel=True)

        builder.connect(op_a, op_b)
        builder.connect(op_a, op_c)
        builder.connect(op_a, op_d)

        complex_replication_pipeline = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            complex_replication_pipeline,
            runtime_pipeline_id=uuid.uuid4(),
            parallel_factor=2,
        )

        # Find OpA using the new method
        op_a_canonical: CanonicalOperator | None = (
            complex_replication_pipeline.get_operator_by_label("Operator A")
        )
        assert op_a_canonical is not None

        op_a_instances: list[RuntimeOperator] = pipeline.get_parallel_group(
            op_a_canonical.id
        )
        assert len(op_a_instances) == 1  # Non-parallel operator
        op_a_runtime: RuntimeOperator = op_a_instances[0]

        # Check output port replication
        op_a_outputs = pipeline.get_operator_outputs(op_a_runtime.id)
        assert len(op_a_outputs) == 3  # Replicated for 3 targets

        # Verify semantic targeting using new method
        target_counts = pipeline.count_replicated_outputs(op_a_runtime.id)
        assert len(target_counts) == 3  # 3 different canonical operators targeted

    def test_input_port_targeting_consistency(self) -> None:
        """Test that input ports have consistent targeting with their connected output ports."""
        # Build complex pipeline
        builder = PipelineBuilder()
        op_a = builder.add_operator("Operator A")
        op_b = builder.add_operator("Operator B", parallel=True)
        op_c = builder.add_operator("Operator C")
        op_d = builder.add_operator("Operator D", parallel=True)

        builder.connect(op_a, op_b)
        builder.connect(op_a, op_c)
        builder.connect(op_a, op_d)

        complex_replication_pipeline = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            complex_replication_pipeline,
            runtime_pipeline_id=uuid.uuid4(),
            parallel_factor=3,
        )

        # Check all input ports have proper targeting
        for runtime_op in pipeline.operators.values():
            inputs = pipeline.get_operator_inputs(runtime_op.id)
            for input_port in inputs.values():
                assert (
                    input_port.targets_canonical_operator_id == runtime_op.canonical_id
                )

    def test_multi_output_replication(self) -> None:
        """Test replication behavior with multiple output ports."""
        # Build multi-output pipeline
        builder = PipelineBuilder()
        source = builder.add_operator("Multi-Output", num_outputs=2)
        target1 = builder.add_operator("Single Input Operator", parallel=False)
        target2 = builder.add_operator("Parallel Input Operator", parallel=True)

        builder.connect(source, target1, from_port_idx=0)
        builder.connect(source, target2, from_port_idx=1)

        multi_output_pipeline = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            multi_output_pipeline, runtime_pipeline_id=uuid.uuid4(), parallel_factor=2
        )

        # Find multi-output operator using new method
        op_a_canonical: CanonicalOperator | None = (
            multi_output_pipeline.get_operator_by_label("Multi-Output")
        )
        assert op_a_canonical is not None

        op_a_instances: list[RuntimeOperator] = pipeline.get_parallel_group(
            op_a_canonical.id
        )
        assert len(op_a_instances) == 1
        op_a_runtime: RuntimeOperator = op_a_instances[0]

        op_a_outputs = pipeline.get_operator_outputs(op_a_runtime.id)
        assert len(op_a_outputs) == 2  # 2 output ports as defined

    def test_edge_case_no_replication_needed(self) -> None:
        """Test pipeline where no replication is needed."""
        # Simple linear pipeline
        builder = PipelineBuilder()
        op1 = builder.add_operator("Operator 1")
        op2 = builder.add_operator("Operator 2")
        builder.connect(op1, op2)

        simple_pipeline = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            simple_pipeline, runtime_pipeline_id=uuid.uuid4(), parallel_factor=1
        )

        # Should have exactly 2 operators and 4 ports (2 per operator)
        assert len(pipeline.operators) == 2
        assert len(pipeline.ports) == 4

        # Verify operator graph is built correctly
        op_graph: nx.DiGraph = pipeline.get_operator_graph()
        assert len(op_graph.nodes()) == 2
        assert len(op_graph.edges()) == 1


    def test_non_parallel_to_parallel_expansion(self) -> None:
        """Test scenario 1: non-parallel → parallel expansion."""
        # Create pipeline: OpA (non-parallel) → OpB (parallel)
        builder = PipelineBuilder()
        op_a = builder.add_operator("OpA", parallel=False, num_inputs=1, num_outputs=1)
        op_b = builder.add_operator("OpB", parallel=True, num_inputs=1, num_outputs=0)
        builder.connect(op_a, op_b)

        pipeline_canonical = builder.build()
        parallel_factor = 2

        pipeline = Pipeline.from_pipeline(
            pipeline_canonical,
            runtime_pipeline_id=uuid.uuid4(),
            parallel_factor=parallel_factor,
        )

        # Verify operators
        assert len(pipeline.operators) == 3  # 1 OpA + 2 OpB instances

        # Get operator instances
        op_a_instances = pipeline.get_parallel_group(op_a.id)
        op_b_instances = pipeline.get_parallel_group(op_b.id)

        assert len(op_a_instances) == 1  # Non-parallel
        assert len(op_b_instances) == 2  # Parallel with factor 2

        # Verify ports
        # OpA: 1 input + 1 output = 2 ports
        # OpB1: 1 input = 1 port
        # OpB2: 1 input = 1 port
        # Total: 4 ports
        assert len(pipeline.ports) == 4

        # Verify edges
        # OpA output should connect to both OpB1 and OpB2 inputs
        edges = list(pipeline.edges)
        assert len(edges) == 2

        # Get OpA's output port
        op_a_runtime = op_a_instances[0]
        op_a_outputs = list(pipeline.get_operator_outputs(op_a_runtime.id).values())
        assert len(op_a_outputs) == 1
        op_a_output = op_a_outputs[0]

        # Verify OpA output connects to both OpB instances
        connected_operators = set()
        for src_id, dst_id in edges:
            if src_id == op_a_output.id:
                dst_port = pipeline.ports[dst_id]
                connected_operators.add(dst_port.operator_id)

        assert len(connected_operators) == 2
        assert all(
            pipeline.operators[op_id].canonical_id == op_b.id
            for op_id in connected_operators
        )

    def test_parallel_to_parallel_full_mesh(self) -> None:
        """Test scenario 2: OpA (non-parallel) → OpB (parallel) → OpC (parallel)."""
        # Create the pipeline
        builder = PipelineBuilder()
        op_a = builder.add_operator("OpA", parallel=False, num_inputs=1, num_outputs=1)
        op_b = builder.add_operator("OpB", parallel=True, num_inputs=1, num_outputs=1)
        op_c = builder.add_operator("OpC", parallel=True, num_inputs=1, num_outputs=0)

        builder.connect(op_a, op_b)
        builder.connect(op_b, op_c)

        pipeline_canonical = builder.build()
        parallel_factor = 2

        pipeline = Pipeline.from_pipeline(
            pipeline_canonical,
            runtime_pipeline_id=uuid.uuid4(),
            parallel_factor=parallel_factor,
        )

        # Verify operators
        # 1 OpA + 2 OpB + 2 OpC = 5 operators
        assert len(pipeline.operators) == 5

        op_a_instances = pipeline.get_parallel_group(op_a.id)
        op_b_instances = pipeline.get_parallel_group(op_b.id)
        op_c_instances = pipeline.get_parallel_group(op_c.id)

        assert len(op_a_instances) == 1
        assert len(op_b_instances) == 2
        assert len(op_c_instances) == 2

        # Count ports
        # OpA: 1 input + 1 output = 2
        # OpB1: 1 input + 1 output = 2
        # OpB2: 1 input + 1 output = 2
        # OpC1: 1 input = 1
        # OpC2: 1 input = 1
        # Total: 8 ports
        assert len(pipeline.ports) == 8

        # Verify edges
        # OpA → OpB1, OpA → OpB2 = 2 edges
        # OpB1 → OpC1, OpB1 → OpC2 = 2 edges
        # OpB2 → OpC1, OpB2 → OpC2 = 2 edges
        # Total: 6 edges
        edges = list(pipeline.edges)
        assert len(edges) == 6

        # Verify connection pattern
        # Track connections from OpB to OpC
        opb_to_opc_connections = []
        for src_id, dst_id in edges:
            src_port = pipeline.ports[src_id]
            dst_port = pipeline.ports[dst_id]

            src_op = pipeline.operators[src_port.operator_id]
            dst_op = pipeline.operators[dst_port.operator_id]

            if src_op.canonical_id == op_b.id and dst_op.canonical_id == op_c.id:
                opb_to_opc_connections.append(
                    (src_op.parallel_index, dst_op.parallel_index)
                )

        # Should have full mesh: each OpB connects to each OpC
        expected_connections = {(0, 0), (0, 1), (1, 0), (1, 1)}
        assert set(opb_to_opc_connections) == expected_connections

    def test_parallel_source_only(self) -> None:
        """Test when only the source is parallel."""
        builder = PipelineBuilder()
        op_a = builder.add_operator("OpA", parallel=True, num_inputs=0, num_outputs=1)
        op_b = builder.add_operator("OpB", parallel=False, num_inputs=1, num_outputs=0)
        builder.connect(op_a, op_b)

        pipeline_canonical = builder.build()
        parallel_factor = 3

        pipeline = Pipeline.from_pipeline(
            pipeline_canonical,
            runtime_pipeline_id=uuid.uuid4(),
            parallel_factor=parallel_factor,
        )

        # 3 OpA + 1 OpB = 4 operators
        assert len(pipeline.operators) == 4

        # Ports: 3 OpA outputs + 1 OpB input = 4
        assert len(pipeline.ports) == 4

        # Each OpA should connect to OpB
        edges = list(pipeline.edges)
        assert len(edges) == 3

        # Verify all OpA instances connect to the single OpB
        op_b_instances = pipeline.get_parallel_group(op_b.id)
        assert len(op_b_instances) == 1
        op_b_runtime = op_b_instances[0]
        op_b_inputs = list(pipeline.get_operator_inputs(op_b_runtime.id).values())
        assert len(op_b_inputs) == 1

        # Count incoming edges to OpB's input
        incoming_count = sum(1 for _, dst_id in edges if dst_id == op_b_inputs[0].id)
        assert incoming_count == 3  # All 3 OpA instances connect to it


class TestReplicationEdgeCases:
    """Test edge cases and error conditions for replication logic."""

    def test_disconnected_operators(self) -> None:
        """Test pipeline with disconnected operators (no replication needed)."""
        # Create disconnected operators
        builder = PipelineBuilder()
        builder.add_operator("Isolated 1", parallel=False, num_inputs=0, num_outputs=0)
        builder.add_operator("Isolated 2", parallel=True, num_inputs=0, num_outputs=0)

        pipeline_canonical = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            pipeline_canonical, runtime_pipeline_id=uuid.uuid4(), parallel_factor=3
        )
        # Should have 4 operators: 1 non-parallel + 3 parallel instances
        assert len(pipeline.operators) == 4
        assert len(pipeline.ports) == 0  # No ports since disconnected

        # Verify operator graph has no edges
        op_graph: nx.DiGraph = pipeline.get_operator_graph()
        assert len(op_graph.edges()) == 0

    def test_self_loop_operator(self) -> None:
        """Test operator that connects to itself (edge case)."""
        builder = PipelineBuilder()
        op = builder.add_operator("Self Loop")
        builder.connect(op, op)

        pipeline_canonical = builder.build()

        pipeline: Pipeline = Pipeline.from_pipeline(
            pipeline_canonical, runtime_pipeline_id=uuid.uuid4()
        )

        assert len(pipeline.operators) == 1
        assert len(pipeline.ports) == 2

        # Verify self-loop in operator graph
        op_graph: nx.DiGraph = pipeline.get_operator_graph()
        assert len(op_graph.nodes()) == 1
        # Self-loops might not show in operator graph since it filters same-operator connections

    def test_port_fanout_analysis(self) -> None:
        """Test port fanout analysis utility."""
        # Build complex pipeline
        builder = PipelineBuilder()
        op_a = builder.add_operator("Operator A")
        op_b = builder.add_operator("Operator B", parallel=True)
        op_c = builder.add_operator("Operator C")
        op_d = builder.add_operator("Operator D", parallel=True)

        builder.connect(op_a, op_b)
        builder.connect(op_a, op_c)
        builder.connect(op_a, op_d)

        complex_replication_pipeline = builder.build()

        fanout_map: dict[UUID, set[UUID]] = get_port_fanout_map(
            complex_replication_pipeline
        )

        # Find OpA's output port using new method
        op_a: CanonicalOperator | None = (
            complex_replication_pipeline.get_operator_by_label("Operator A")
        )
        assert op_a is not None

        op_a_port: CanonicalPort = next(
            p
            for p in complex_replication_pipeline.ports
            if p.canonical_operator_id == op_a.id and p.port_type == PortType.output
        )

        # Should fan out to 3 operators
        assert len(fanout_map[op_a_port.id]) == 3
