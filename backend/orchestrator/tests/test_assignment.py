import uuid

import pytest

from interactem.core.models.agent import AgentStatus, AgentVal
from interactem.core.models.base import CommBackend, IdType, PortType, URILocation
from interactem.core.models.operators import OperatorTag
from interactem.core.models.pipeline import (
    EdgeJSON,
    InputJSON,
    OperatorJSON,
    OutputJSON,
    PipelineAssignment,
    PipelineJSON,
)
from interactem.core.models.uri import URI
from interactem.core.pipeline import Pipeline
from interactem.orchestrator.orchestrator import (
    CyclicDependenciesError,
    NoAgentsError,
    PipelineAssigner,
    UnassignableOperatorsError,
)


# Helper function to get assigned operator IDs for an agent
def get_assigned_ops(
    assignments: list[PipelineAssignment], agent_id: IdType
) -> set[IdType]:
    for assignment in assignments:
        if assignment.agent_id == agent_id:
            # Ensure operators_assigned is not None before creating a set
            return (
                set(assignment.operators_assigned)
                if assignment.operators_assigned
                else set()
            )
    return set()


def test_simple_tag_match():
    """Test basic tag matching."""
    # 1. Define Operators with tags
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        tags=[OperatorTag(value="gpu")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b-img",
        tags=[OperatorTag(value="cpu")],
        inputs=[port_b_in_id],
        outputs=[port_b_out_id],
    )
    op_c = OperatorJSON(id=op_c_id, image="op-c-img", inputs=[port_c_in_id])  # No tags

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in],
        edges=[edge_ab, edge_bc],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_gpu_id = uuid.uuid4()
    agent_cpu_id = uuid.uuid4()
    agent_generic_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_gpu_id,
                location=URILocation.agent,
                hostname="host1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_cpu_id,
                location=URILocation.agent,
                hostname="host2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["cpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_generic_id,
                location=URILocation.agent,
                hostname="host3",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assert op_a.id in get_assigned_ops(assignments, agent_gpu_id)
    assert op_b.id in get_assigned_ops(assignments, agent_cpu_id)
    assigned_c = False
    for agent_id in [agent_gpu_id, agent_cpu_id, agent_generic_id]:
        if op_c.id in get_assigned_ops(assignments, agent_id):
            assigned_c = True
            break
    assert assigned_c, "Operator C was not assigned"
    assert op_b.id not in get_assigned_ops(assignments, agent_gpu_id)
    assert op_a.id not in get_assigned_ops(assignments, agent_cpu_id)


def test_network_preference_no_crossing():
    """Test that assigner prefers staying on the same network."""
    # 1. Define Operators (no tags needed)
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        outputs=[port_a_out_id],
        tags=[OperatorTag(value="net1_feature")],
    )
    op_b = OperatorJSON(
        id=op_b_id, image="op-b-img", inputs=[port_b_in_id], outputs=[port_b_out_id]
    )
    op_c = OperatorJSON(id=op_c_id, image="op-c-img", inputs=[port_c_in_id])

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in],
        edges=[edge_ab, edge_bc],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_net1_a_id = uuid.uuid4()
    agent_net1_b_id = uuid.uuid4()
    agent_net2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_net1_a_id,
                location=URILocation.agent,
                hostname="host1a",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["net1_feature"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net1_b_id,
                location=URILocation.agent,
                hostname="host1b",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net2_id,
                location=URILocation.agent,
                hostname="host2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net2"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_net1_a = get_assigned_ops(assignments, agent_net1_a_id)
    assigned_ops_net1_b = get_assigned_ops(assignments, agent_net1_b_id)
    assigned_ops_net2 = get_assigned_ops(assignments, agent_net2_id)

    assert len(assigned_ops_net2) == 0, (
        "Operators assigned across network boundary unnecessarily"
    )
    assert len(assigned_ops_net1_a) + len(assigned_ops_net1_b) == 3


def test_network_forced_crossing():
    """Test that assigner crosses network boundary when necessary (e.g., due to tags)."""
    # 1. Define Operators with tags
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        tags=[OperatorTag(value="net1_feature")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b-img",
        tags=[OperatorTag(value="net2_feature")],
        inputs=[port_b_in_id],
        outputs=[port_b_out_id],
    )
    op_c = OperatorJSON(id=op_c_id, image="op-c-img", inputs=[port_c_in_id])  # No tags

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in],
        edges=[edge_ab, edge_bc],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_net1_id = uuid.uuid4()
    agent_net2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_net1_id,
                location=URILocation.agent,
                hostname="host1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["net1_feature"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net2_id,
                location=URILocation.agent,
                hostname="host2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["net2_feature"],
            networks={"net2"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_net1 = get_assigned_ops(assignments, agent_net1_id)
    assigned_ops_net2 = get_assigned_ops(assignments, agent_net2_id)

    assert op_a.id in assigned_ops_net1
    assert op_b.id in assigned_ops_net2
    # OpC (no tags) should ideally follow OpB onto net2 to avoid crossing back
    assert op_c.id in assigned_ops_net2


def test_tag_and_network_preference():
    """Test interaction of tags and network preference."""
    # 1. Define Operators with tags
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        tags=[OperatorTag(value="gpu")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b-img",
        tags=[OperatorTag(value="cpu")],
        inputs=[port_b_in_id],
        outputs=[port_b_out_id],
    )
    op_c = OperatorJSON(id=op_c_id, image="op-c-img", inputs=[port_c_in_id])  # No tags

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in],
        edges=[edge_ab, edge_bc],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_gpu_net1_id = uuid.uuid4()
    agent_cpu_net1_id = uuid.uuid4()
    agent_gpu_net2_id = uuid.uuid4()
    agent_cpu_net2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_gpu_net1_id,
                location=URILocation.agent,
                hostname="host1g",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_cpu_net1_id,
                location=URILocation.agent,
                hostname="host1c",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["cpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_gpu_net2_id,
                location=URILocation.agent,
                hostname="host2g",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu"],
            networks={"net2"},
        ),
        AgentVal(
            uri=URI(
                id=agent_cpu_net2_id,
                location=URILocation.agent,
                hostname="host2c",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["cpu"],
            networks={"net2"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    # Find which networks op_a was assigned to
    assigned_networks = None
    for agent in agents:
        if op_a.id in get_assigned_ops(assignments, agent.uri.id):
            assigned_networks = agent.networks
            break
    assert assigned_networks is not None, "op_a was not assigned"

    # op_b must be assigned to a cpu agent on the same networks
    cpu_agents_on_net = [
        agent
        for agent in agents
        if "cpu" in agent.tags and assigned_networks == agent.networks
    ]
    assert any(
        op_b.id in get_assigned_ops(assignments, agent.uri.id)
       for agent in cpu_agents_on_net
    )

    # op_c must be assigned to an agent on the same network
    agents_on_net = [agent for agent in agents if assigned_networks == agent.networks]
    assert any(
        op_c.id in get_assigned_ops(assignments, agent.uri.id)
        for agent in agents_on_net
    )


def test_load_balancing_same_network():
    """Test that assigner distributes load among agents on the same network."""
    # 1. Define Operators (no tags needed)
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()
    op_d_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()
    port_c_out_id = uuid.uuid4()
    port_d_in_id = uuid.uuid4()

    op_a = OperatorJSON(id=op_a_id, image="op-a-img", outputs=[port_a_out_id])
    op_b = OperatorJSON(
        id=op_b_id, image="op-b-img", inputs=[port_b_in_id], outputs=[port_b_out_id]
    )
    op_c = OperatorJSON(
        id=op_c_id, image="op-c-img", inputs=[port_c_in_id], outputs=[port_c_out_id]
    )
    op_d = OperatorJSON(id=op_d_id, image="op-d-img", inputs=[port_d_in_id])

    # 2. Define Ports (simple linear chain A->B->C->D)
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )
    port_c_out = OutputJSON(
        id=port_c_out_id, operator_id=op_c_id, portkey="out", port_type=PortType.output
    )
    port_d_in = InputJSON(
        id=port_d_in_id, operator_id=op_d_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)
    edge_cd = EdgeJSON(input_id=port_c_out_id, output_id=port_d_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c, op_d],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in, port_c_out, port_d_in],
        edges=[edge_ab, edge_bc, edge_cd],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (two identical agents on the same network)
    agent_net1_a_id = uuid.uuid4()
    agent_net1_b_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_net1_a_id,
                location=URILocation.agent,
                hostname="host1a",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net1_b_id,
                location=URILocation.agent,
                hostname="host1b",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_net1_a = get_assigned_ops(assignments, agent_net1_a_id)
    assigned_ops_net1_b = get_assigned_ops(assignments, agent_net1_b_id)

    # Expect operators to be distributed roughly evenly
    assert len(assigned_ops_net1_a) + len(assigned_ops_net1_b) == 4
    assert (
        abs(len(assigned_ops_net1_a) - len(assigned_ops_net1_b)) <= 1
    )  # Allow for uneven split like 3-1 or 2-2
    # Check that all operators are assigned to one of the two agents
    all_assigned_ops = assigned_ops_net1_a.union(assigned_ops_net1_b)
    assert all_assigned_ops == {op_a.id, op_b.id, op_c.id, op_d.id}


def test_unassignable_operator_missing_tags():
    """Test that an operator is unassignable if no agent has its required tags."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        tags=[OperatorTag(value="required_feature")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id, image="op-b-img", inputs=[port_b_in_id]
    )  # Assignable

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edge
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (None have the required tag)
    agent_1_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_1_id,
                location=URILocation.agent,
                hostname="host1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["other_feature"],
            networks={"net1"},
        )
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    with pytest.raises(UnassignableOperatorsError):
        assigner.assign()


def test_no_agents_available():
    """Test assignment behavior when no agents are provided."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()

    op_a = OperatorJSON(id=op_a_id, image="op-a-img", outputs=[port_a_out_id])
    op_b = OperatorJSON(id=op_b_id, image="op-b-img", inputs=[port_b_in_id])

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edge
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (Empty list)
    agents = []

    # 6. Run Assigner
    with pytest.raises(NoAgentsError, match="No agents available for assignment."):
        PipelineAssigner(agents, pipeline)


def test_multiple_tags_required():
    """Test assignment when an operator requires multiple tags."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        tags=[OperatorTag(value="gpu"), OperatorTag(value="fast_io")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b-img",
        tags=[OperatorTag(value="gpu")],
        inputs=[port_b_in_id],
    )  # Only needs gpu

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edge
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_gpu_fast_id = uuid.uuid4()
    agent_gpu_only_id = uuid.uuid4()
    agent_fast_only_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_gpu_fast_id,
                location=URILocation.agent,
                hostname="host_gf",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu", "fast_io"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_gpu_only_id,
                location=URILocation.agent,
                hostname="host_g",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_fast_only_id,
                location=URILocation.agent,
                hostname="host_f",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["fast_io"],
            networks={"net1"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assert op_a.id in get_assigned_ops(assignments, agent_gpu_fast_id)
    assert op_a.id not in get_assigned_ops(assignments, agent_gpu_only_id)
    assert op_a.id not in get_assigned_ops(assignments, agent_fast_only_id)

    # OpB should prefer the agent OpA is on due to network locality (implicitly same network here)
    # OR it could go to agent_gpu_only if load balancing dictates.
    # Let's assert it lands on one of the GPU agents.
    assigned_b = op_b.id in get_assigned_ops(
        assignments, agent_gpu_fast_id
    ) or op_b.id in get_assigned_ops(assignments, agent_gpu_only_id)
    assert assigned_b, "Operator B should be assigned to a GPU agent"
    assert op_b.id not in get_assigned_ops(assignments, agent_fast_only_id)


def test_pipeline_with_cycle():
    """Test that PipelineAssigner initialization raises error for cyclic pipeline."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_a_in_id = uuid.uuid4()  # Input for cycle

    op_a = OperatorJSON(
        id=op_a_id, image="op-a-img", inputs=[port_a_in_id], outputs=[port_a_out_id]
    )
    op_b = OperatorJSON(
        id=op_b_id, image="op-b-img", inputs=[port_b_in_id], outputs=[port_b_out_id]
    )

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_a_in = InputJSON(
        id=port_a_in_id, operator_id=op_a_id, portkey="in", port_type=PortType.input
    )  # Input for cycle

    # 3. Define Edges (A -> B and B -> A)
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_ba = EdgeJSON(input_id=port_b_out_id, output_id=port_a_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in, port_b_out, port_a_in],
        edges=[edge_ab, edge_ba],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (content doesn't matter as error should occur before assignment)
    agent_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_id,
                location=URILocation.agent,
                hostname="host_cycle",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        )
    ]

    # 6. Assert that creating the Assigner raises PipelineGraphError
    with pytest.raises(CyclicDependenciesError, match="contains cycles"):
        PipelineAssigner(agents, pipeline)


def test_disconnected_operators():
    """Test assignment of operators not connected to the main graph."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()  # Disconnected

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()

    op_a = OperatorJSON(id=op_a_id, image="op-a-img", outputs=[port_a_out_id])
    op_b = OperatorJSON(id=op_b_id, image="op-b-img", inputs=[port_b_in_id])
    op_c = OperatorJSON(id=op_c_id, image="op-c-img")  # Disconnected

    # 2. Define Ports (only for A -> B)
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    # Op C has no ports defined in this simple case

    # 3. Define Edge (only A -> B)
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c],
        ports=[port_a_out, port_b_in],  # Only ports for connected part
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (two generic agents)
    agent_1_id = uuid.uuid4()
    agent_2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_1_id,
                location=URILocation.agent,
                hostname="host_disc_1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_2_id,
                location=URILocation.agent,
                hostname="host_disc_2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_1 = get_assigned_ops(assignments, agent_1_id)
    assigned_ops_2 = get_assigned_ops(assignments, agent_2_id)
    all_assigned = assigned_ops_1.union(assigned_ops_2)

    # Check all operators were assigned
    assert {op_a.id, op_b.id, op_c.id}.issubset(all_assigned), (
        "Not all operators were assigned"
    )
    assert len(all_assigned) == 3


def test_network_preference_over_load():
    """Test that network preference is prioritized over assigning to an agent on another network."""
    # 1. Define Operators
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()

    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a-img",
        outputs=[port_a_out_id],
        tags=[OperatorTag(value="net1_feature")],
    )
    op_b = OperatorJSON(id=op_b_id, image="op-b-img", inputs=[port_b_in_id])

    # 2. Define Ports
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edge
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents
    agent_net1_a_id = uuid.uuid4()
    agent_net1_b_id = uuid.uuid4()  # Another agent on Net1
    agent_net2_id = uuid.uuid4()  # agent on Net2
    agents = [
        AgentVal(
            uri=URI(
                id=agent_net1_a_id,
                location=URILocation.agent,
                hostname="host1a",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["net1_feature"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net1_b_id,
                location=URILocation.agent,
                hostname="host1b",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["net1_feature"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net2_id,
                location=URILocation.agent,
                hostname="host2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net2"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_net1_a = get_assigned_ops(assignments, agent_net1_a_id)
    assigned_ops_net1_b = get_assigned_ops(assignments, agent_net1_b_id)
    assigned_ops_net2 = get_assigned_ops(assignments, agent_net2_id)

    # OpA will land on net1_a or net1_b.
    # OpB MUST follow onto net1_a or net1_b, NOT net2_idle, due to network preference.
    assert len(assigned_ops_net2) == 0, (
        "Operator assigned to Net2 despite Net1 preference"
    )
    assert len(assigned_ops_net1_a) + len(assigned_ops_net1_b) == 2, (
        "Operators not assigned correctly to Net1 agents"
    )


def test_tie_breaking_load():
    """Test load balancing as the final tie-breaker when network and tags match."""
    # 1. Define Operators (all require 'common_tag')
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    op_c_id = uuid.uuid4()
    op_d_id = uuid.uuid4()

    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    port_b_out_id = uuid.uuid4()
    port_c_in_id = uuid.uuid4()
    port_c_out_id = uuid.uuid4()
    port_d_in_id = uuid.uuid4()

    common_tag = OperatorTag(value="common_tag")
    op_a = OperatorJSON(
        id=op_a_id, image="op-a-img", tags=[common_tag], outputs=[port_a_out_id]
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b-img",
        tags=[common_tag],
        inputs=[port_b_in_id],
        outputs=[port_b_out_id],
    )
    op_c = OperatorJSON(
        id=op_c_id,
        image="op-c-img",
        tags=[common_tag],
        inputs=[port_c_in_id],
        outputs=[port_c_out_id],
    )
    op_d = OperatorJSON(
        id=op_d_id, image="op-d-img", tags=[common_tag], inputs=[port_d_in_id]
    )

    # 2. Define Ports (simple linear chain A->B->C->D)
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    port_b_out = OutputJSON(
        id=port_b_out_id, operator_id=op_b_id, portkey="out", port_type=PortType.output
    )
    port_c_in = InputJSON(
        id=port_c_in_id, operator_id=op_c_id, portkey="in", port_type=PortType.input
    )
    port_c_out = OutputJSON(
        id=port_c_out_id, operator_id=op_c_id, portkey="out", port_type=PortType.output
    )
    port_d_in = InputJSON(
        id=port_d_in_id, operator_id=op_d_id, portkey="in", port_type=PortType.input
    )

    # 3. Define Edges
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    edge_bc = EdgeJSON(input_id=port_b_out_id, output_id=port_c_in_id)
    edge_cd = EdgeJSON(input_id=port_c_out_id, output_id=port_d_in_id)

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b, op_c, op_d],
        ports=[port_a_out, port_b_in, port_b_out, port_c_in, port_c_out, port_d_in],
        edges=[edge_ab, edge_bc, edge_cd],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (two identical agents matching network and tags)
    agent_1_id = uuid.uuid4()
    agent_2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_1_id,
                location=URILocation.agent,
                hostname="host_tie_1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["common_tag"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_2_id,
                location=URILocation.agent,
                hostname="host_tie_2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["common_tag"],
            networks={"net1"},
        ),
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assigned_ops_1 = get_assigned_ops(assignments, agent_1_id)
    assigned_ops_2 = get_assigned_ops(assignments, agent_2_id)

    # Expect operators to be distributed roughly evenly due to load balancing
    assert len(assigned_ops_1) + len(assigned_ops_2) == 4
    assert abs(len(assigned_ops_1) - len(assigned_ops_2)) <= 1  # Allow 2-2 or 3-1 split
    all_assigned_ops = assigned_ops_1.union(assigned_ops_2)
    assert all_assigned_ops == {op_a.id, op_b.id, op_c.id, op_d.id}


def test_empty_pipeline():
    """Test assignment with an empty pipeline definition."""
    # 1. Define Operators, Ports, Edges (all empty)
    operators = []
    ports = []
    edges = []

    # 4. Create Pipeline
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(), operators=operators, ports=ports, edges=edges
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)

    # 5. Define Agents (at least one agent)
    agent_1_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_1_id,
                location=URILocation.agent,
                hostname="host_empty",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        )
    ]

    # 6. Run Assigner
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()

    # 7. Assertions
    assert len(assignments) == 1, (
        "We should still be assigning 'work' to agents (even if empty)"
    )
    assert assignments[0].operators_assigned == [], (
        "Empty pipeline should assign empty operators_assigned"
    )

def test_agent_with_multiple_networks():
    """Agent with multiple networks can be chosen for a chain crossing networks."""
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    op_a = OperatorJSON(id=op_a_id, image="op-a", outputs=[port_a_out_id])
    op_b = OperatorJSON(id=op_b_id, image="op-b", inputs=[port_b_in_id])
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)
    agent_multi_id = uuid.uuid4()
    agent_net1_id = uuid.uuid4()
    agent_net2_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_multi_id,
                location=URILocation.agent,
                hostname="multi",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1", "net2"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net1_id,
                location=URILocation.agent,
                hostname="n1",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_net2_id,
                location=URILocation.agent,
                hostname="n2",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net2"},
        ),
    ]
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()
    # All operators should be assigned to a single network, and the agent with both networks is eligible
    all_assigned = [op for a in assignments for op in a.operators_assigned]
    assert set(all_assigned) == {op_a_id, op_b_id}


def test_operators_with_overlapping_tags():
    """Operators with overlapping but not identical tag requirements are assigned correctly."""
    op_a_id = uuid.uuid4()
    op_b_id = uuid.uuid4()
    port_a_out_id = uuid.uuid4()
    port_b_in_id = uuid.uuid4()
    op_a = OperatorJSON(
        id=op_a_id,
        image="op-a",
        tags=[OperatorTag(value="gpu")],
        outputs=[port_a_out_id],
    )
    op_b = OperatorJSON(
        id=op_b_id,
        image="op-b",
        tags=[OperatorTag(value="gpu"), OperatorTag(value="ssd")],
        inputs=[port_b_in_id],
    )
    port_a_out = OutputJSON(
        id=port_a_out_id, operator_id=op_a_id, portkey="out", port_type=PortType.output
    )
    port_b_in = InputJSON(
        id=port_b_in_id, operator_id=op_b_id, portkey="in", port_type=PortType.input
    )
    edge_ab = EdgeJSON(input_id=port_a_out_id, output_id=port_b_in_id)
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op_a, op_b],
        ports=[port_a_out, port_b_in],
        edges=[edge_ab],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)
    agent_gpu_id = uuid.uuid4()
    agent_gpu_ssd_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_gpu_id,
                location=URILocation.agent,
                hostname="gpu",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_gpu_ssd_id,
                location=URILocation.agent,
                hostname="gpu-ssd",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["gpu", "ssd"],
            networks={"net1"},
        ),
    ]
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()
    # op_a can go to either agent, op_b must go to gpu-ssd agent
    assert op_b_id in get_assigned_ops(assignments, agent_gpu_ssd_id)


def test_agent_with_superset_tags():
    """Agent with superset of required tags is eligible for assignment."""
    op_id = uuid.uuid4()
    port_out_id = uuid.uuid4()
    op = OperatorJSON(
        id=op_id, image="op", tags=[OperatorTag(value="cpu")], outputs=[port_out_id]
    )
    port_out = OutputJSON(
        id=port_out_id, operator_id=op_id, portkey="out", port_type=PortType.output
    )
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op],
        ports=[port_out],
        edges=[],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)
    agent_exact_id = uuid.uuid4()
    agent_superset_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_exact_id,
                location=URILocation.agent,
                hostname="cpu",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["cpu"],
            networks={"net1"},
        ),
        AgentVal(
            uri=URI(
                id=agent_superset_id,
                location=URILocation.agent,
                hostname="cpu-gpu",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=["cpu", "gpu"],
            networks={"net1"},
        ),
    ]
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()
    # Both agents are eligible
    assigned = get_assigned_ops(assignments, agent_exact_id) | get_assigned_ops(
        assignments, agent_superset_id
    )
    assert op_id in assigned


def test_isolated_operator_assignment():
    """Operators with no inputs or outputs (isolated) are assigned."""
    op_id = uuid.uuid4()
    op = OperatorJSON(id=op_id, image="op")
    pipeline_json = PipelineJSON(
        id=uuid.uuid4(),
        operators=[op],
        ports=[],
        edges=[],
    )
    pipeline = Pipeline.from_pipeline(pipeline_json)
    agent_id = uuid.uuid4()
    agents = [
        AgentVal(
            uri=URI(
                id=agent_id,
                location=URILocation.agent,
                hostname="host",
                comm_backend=CommBackend.NATS,
            ),
            status=AgentStatus.IDLE,
            tags=[],
            networks={"net1"},
        ),
    ]
    assigner = PipelineAssigner(agents, pipeline)
    assignments = assigner.assign()
    assert op_id in get_assigned_ops(assignments, agent_id)
