from collections.abc import AsyncGenerator
from enum import Enum
from uuid import uuid4

import networkx as nx

from .logger import get_logger
from .models.base import IdType, NodeType, PortType
from .models.canonical import (
    CanonicalEdge,
    CanonicalOperator,
    CanonicalOperatorID,
    CanonicalPipeline,
    CanonicalPipelineID,
    CanonicalPort,
    CanonicalPortID,
)
from .models.runtime import (
    RuntimeEdge,
    RuntimeInput,
    RuntimeOperator,
    RuntimeOutput,
    RuntimePipeline,
    RuntimePipelineID,
    RuntimePort,
)
from .models.spec import ParallelType

logger = get_logger()

DEFAULT_PARALLEL_FACTOR = 2

"""
This module has the Pipeline graph implementation.
TODO: a better way to do this is to create a more generic pipeline class that could handle
either canonical or runtime pipelines and associated models. We could then use graph methods
to handle introspection and expansion/replication.
"""


def get_port_fanout_map(
    canonical_pipeline: CanonicalPipeline,
) -> dict[CanonicalPortID, set[CanonicalOperatorID]]:
    port_lookup = {p.id: p for p in canonical_pipeline.ports}
    fanout_map = {}

    for port in canonical_pipeline.ports:
        if port.port_type != PortType.output:
            continue

        # Find all edges that start from this output port
        downstream_operators = set()
        for edge in canonical_pipeline.edges:
            if edge.input_id == port.id and edge.output_id in port_lookup:
                target_port = port_lookup[edge.output_id]
                downstream_operators.add(target_port.canonical_operator_id)

        fanout_map[port.id] = downstream_operators

    return fanout_map


class IdName(str, Enum):
    RUNTIME = "id"
    CANONICAL = "canonical_id"
    REVISION = "revision_id"

class Pipeline(nx.DiGraph):
    def __init__(self, **attr):
        super().__init__(**attr)
        self._operator_graph = nx.DiGraph()
        self._needs_rebuild = True

    def _try_get_id(self, id: IdName):
        """Helper to safely get the ID from the graph attributes."""
        try:
            return self.graph[id.value]
        except KeyError:
            raise AttributeError(f"Graph object has no '{id}' attribute.")

    @property
    def id(self) -> RuntimePipelineID:
        """Returns the ID of the pipeline graph stored in graph attributes."""
        return self._try_get_id(IdName.RUNTIME)

    @property
    def canonical_id(self) -> CanonicalPipelineID:
        """Returns the canonical ID of the pipeline graph."""
        return self._try_get_id(IdName.CANONICAL)

    @property
    def revision_id(self) -> int:
        """Returns the revision ID of the pipeline graph."""
        return self._try_get_id(IdName.REVISION)

    @classmethod
    def from_pipeline(
        cls,
        pipeline: CanonicalPipeline | RuntimePipeline,
        runtime_pipeline_id: IdType | None = None,
        parallel_factor: int = DEFAULT_PARALLEL_FACTOR,
    ) -> "Pipeline":
        """
        Create Pipeline from either CanonicalPipeline or RuntimePipeline.
        Always produces a runtime pipeline representation internally.

        Args:
            pipeline: Either CanonicalPipeline or RuntimePipeline to convert
            runtime_pipeline_id: Override runtime pipeline ID
            parallel_factor: Factor for parallel expansion (only applies to CanonicalPipeline)

        Returns:
            Pipeline graph with runtime models
        """
        if isinstance(pipeline, RuntimePipeline):
            # Convert canonical to runtime with parallel expansion
            return cls.from_runtime_pipeline(pipeline)
        elif isinstance(pipeline, CanonicalPipeline):
            # Create from existing runtime pipeline
            if runtime_pipeline_id is None:
                raise ValueError(
                    "runtime_pipeline_id must be provided for CanonicalPipeline conversion."
                )
            return cls.expand_canonical_to_runtime(
                pipeline, runtime_pipeline_id, parallel_factor
            )
        else:
            raise ValueError(f"Unsupported pipeline type: {type(pipeline)}")

    @classmethod
    def from_runtime_pipeline(cls, pipeline: RuntimePipeline) -> "Pipeline":
        graph = cls(
            id=pipeline.id,
            canonical_id=pipeline.canonical_id,
            revision_id=pipeline.revision_id,
        )

        for operator in pipeline.operators:
            graph.add_node_model(operator)

        for port in pipeline.ports:
            graph.add_node_model(port)

        for edge in pipeline.edges:
            graph.add_edge_model(edge)

        return graph

    @classmethod
    def expand_canonical_to_runtime(
        cls,
        canonical_pipeline: CanonicalPipeline,
        runtime_pipeline_id: IdType,
        parallel_factor: int = DEFAULT_PARALLEL_FACTOR,
    ) -> "Pipeline":
        """
        Expand a canonical pipeline to runtime pipeline with parallel operator expansion.

        Args:
            canonical_pipeline: The canonical pipeline to expand
            runtime_pipeline_id: The runtime pipeline ID from the database
            parallel_factor: Factor to expand parallel operators (default: 2)

        Returns:
            Pipeline with runtime models and expanded parallel operators
        """
        # Create runtime pipeline graph
        graph = cls(
            id=runtime_pipeline_id,
            canonical_id=canonical_pipeline.id,
            revision_id=canonical_pipeline.revision_id,
        )

        # Track mapping of canonical operator ID to list of runtime operators
        operator_mapping: dict[IdType, list[RuntimeOperator]] = {}
        all_runtime_operators: list[RuntimeOperator] = []

        # Expand operators (with parallel expansion)
        for canonical_op in canonical_pipeline.operators:
            runtime_ops = graph._expand_operator(canonical_op, parallel_factor)
            operator_mapping[canonical_op.id] = runtime_ops
            all_runtime_operators.extend(runtime_ops)

        # Batch add all runtime operators
        operator_node_data = [(op.id, op.model_dump()) for op in all_runtime_operators]
        graph.add_nodes_from(operator_node_data)

        # Expand ports
        port_fanout = get_port_fanout_map(canonical_pipeline)
        runtime_ports = graph._expand_ports(
            list(canonical_pipeline.ports), operator_mapping, port_fanout
        )

        # Batch add all runtime ports
        port_node_data = [(port.id, port.model_dump()) for port in runtime_ports]
        graph.add_nodes_from(port_node_data)

        # Build port lookup
        port_by_canonical_id = {port.canonical_id: [] for port in runtime_ports}
        for port in runtime_ports:
            port_by_canonical_id[port.canonical_id].append(port)

        # Expand edges with lookup
        runtime_edges = graph._expand_edges(
            list(canonical_pipeline.edges), port_by_canonical_id, operator_mapping
        )

        # Batch add all runtime edges
        edge_data = [
            (edge.input_id, edge.output_id, edge.model_dump()) for edge in runtime_edges
        ]
        graph.add_edges_from(edge_data)

        return graph

    def _expand_operator(
        self, operator: CanonicalOperator, factor: int
    ) -> list[RuntimeOperator]:
        """Expand operator based on parallel configuration."""
        should_expand = (
            operator.parallel_config is not None
            and operator.parallel_config.type != ParallelType.NONE
        )

        expansion_factor = factor if should_expand else 1
        return RuntimeOperator.replicate_from_canonical(operator, expansion_factor)

    def _expand_ports(
        self,
        ports: list[CanonicalPort],
        operator_mapping: dict[IdType, list[RuntimeOperator]],
        port_fanout: dict[CanonicalPortID, set[CanonicalOperatorID]],
    ) -> list[RuntimePort]:
        runtime_ports = []

        for canonical_port in ports:
            # Get the runtime operators for this port's canonical operator
            runtime_ops = operator_mapping.get(canonical_port.canonical_operator_id, [])

            if not runtime_ops:
                logger.warning(
                    f"No runtime operators found for canonical operator {canonical_port.canonical_operator_id}"
                )
                continue

            port_base_data = canonical_port.model_dump(
                exclude={"id", "targets_canonical_operator_id"}
            )

            if canonical_port.port_type == PortType.output:
                runtime_ports.extend(
                    self._create_output_ports(
                        canonical_port, runtime_ops, port_base_data, port_fanout
                    )
                )
            else:  # Input port
                runtime_ports.extend(
                    self._create_input_ports(
                        canonical_port, runtime_ops, port_base_data
                    )
                )

        return runtime_ports

    def _create_output_ports(
        self,
        canonical_port: CanonicalPort,
        runtime_ops: list[RuntimeOperator],
        port_base_data: dict,
        port_fanout: dict[CanonicalPortID, set[CanonicalOperatorID]],
    ) -> list[RuntimePort]:
        """Create runtime output ports with replication if needed."""
        runtime_ports = []
        downstream_ops = port_fanout.get(canonical_port.id, set())

        # If no downstream or single downstream, treat as single target
        # If multiple downstream, create one port per target for replication
        targets = (
            downstream_ops
            if len(downstream_ops) > 1
            else {list(downstream_ops)[0] if downstream_ops else None}
        )

        for runtime_op in runtime_ops:
            for target_op_id in targets:
                runtime_port = RuntimeOutput(
                    id=uuid4(),
                    canonical_id=canonical_port.id,
                    operator_id=runtime_op.id,
                    targets_canonical_operator_id=target_op_id,
                    **port_base_data,
                )
                runtime_ports.append(runtime_port)

        return runtime_ports

    def _create_input_ports(
        self,
        canonical_port: CanonicalPort,
        runtime_ops: list[RuntimeOperator],
        port_base_data: dict,
    ) -> list[RuntimePort]:
        runtime_ports = []

        for runtime_op in runtime_ops:
            runtime_port = RuntimeInput(
                id=uuid4(),
                canonical_id=canonical_port.id,
                operator_id=runtime_op.id,
                targets_canonical_operator_id=runtime_op.canonical_id,
                **port_base_data,
            )
            runtime_ports.append(runtime_port)

        return runtime_ports

    def _expand_edges(
        self,
        edges: list[CanonicalEdge],
        port_by_canonical_id: dict[IdType, list[RuntimePort]],
        operator_mapping: dict[IdType, list[RuntimeOperator]],
    ) -> list[RuntimeEdge]:
        runtime_edges = []

        # Build operator lookup by runtime ID for faster access
        operator_by_runtime_id = {}
        for runtime_ops in operator_mapping.values():
            for op in runtime_ops:
                operator_by_runtime_id[op.id] = op

        for canonical_edge in edges:
            src_runtime_ports = port_by_canonical_id.get(canonical_edge.input_id, [])
            dst_runtime_ports = port_by_canonical_id.get(canonical_edge.output_id, [])

            # Connect corresponding parallel instances
            for src_port in src_runtime_ports:
                for dst_port in dst_runtime_ports:
                    if self._should_connect_ports(
                        src_port, dst_port, operator_by_runtime_id
                    ):
                        runtime_edge = RuntimeEdge(
                            input_id=src_port.id, output_id=dst_port.id
                        )
                        runtime_edges.append(runtime_edge)

        return runtime_edges

    def _should_connect_ports(
        self,
        src_port: RuntimePort,
        dst_port: RuntimePort,
        operator_by_id: dict[IdType, RuntimeOperator],
    ) -> bool:
        # Validate both operators exist
        src_op = operator_by_id.get(src_port.operator_id)
        dst_op = operator_by_id.get(dst_port.operator_id)

        if not src_op or not dst_op:
            return False

        # Check replicated output targeting constraint
        if (
            src_port.port_type == PortType.output
            and src_port.targets_canonical_operator_id is not None
        ):
            # This output port is replicated for a specific target
            # Only connect if the destination matches the intended target
            return src_port.targets_canonical_operator_id == dst_op.canonical_id

        # Standard connection - no targeting constraints
        return True

    @classmethod
    def from_upstream_subgraph(cls, graph: "Pipeline", id: IdType) -> "Pipeline":
        subgraph = cls(id=id)

        # Use a stack to perform DFS and collect all upstream nodes
        stack = [id]
        visited = set()

        while stack:
            current_node = stack.pop()
            if current_node not in visited:
                visited.add(current_node)
                predecessors = list(graph.predecessors(current_node))
                stack.extend(predecessors)

        # Add nodes and edges to the subgraph
        for node in visited:
            subgraph.add_node(node, **graph.nodes[node])

        for u, v in graph.edges:
            if u in visited and v in visited:
                subgraph.add_edge(u, v, **graph.edges[u, v])

        subgraph._build_operator_graph()

        return subgraph

    def _build_operator_graph(self) -> None:
        """
        Build operator-to-operator dependency graph from the port connections
        and cache the result.
        """
        # Clear and rebuild the operator graph
        self._operator_graph.clear()

        # Add all operators as nodes
        for op_id in self.operators:
            self._operator_graph.add_node(op_id)

        # For each port connection, determine the operators it connects
        for u, v in self.edges:
            # Get the ports at both ends of the connection
            if u in self.ports and v in self.ports:
                # Get the operators that own these ports
                src_op_id = self.ports[u].operator_id
                dst_op_id = self.ports[v].operator_id

                # If they're different operators, add the edge
                if src_op_id != dst_op_id:
                    self._operator_graph.add_edge(src_op_id, dst_op_id)

        self._needs_rebuild = False

    def __eq__(self, other):
        if not isinstance(other, Pipeline):
            return False

        if self.graph != other.graph:
            logger.info("Graph metadata differs.")
            logger.info(f"Self graph metadata: {self.graph}")
            logger.info(f"Other graph metadata: {other.graph}")
            return False

        self_nodes = set(self.nodes)
        other_nodes = set(other.nodes)

        if self_nodes != other_nodes:
            logger.info("Node sets differ.")
            logger.info(f"Nodes in self but not in other: {self_nodes - other_nodes}")
            logger.info(f"Nodes in other but not in self: {other_nodes - self_nodes}")
            return False

        for node_id in self_nodes:
            if self.nodes[node_id] != other.nodes[node_id]:
                logger.info(f"Node attributes differ for node {node_id}.")
                logger.info(f"Self node attributes: {self.nodes[node_id]}")
                logger.info(f"Other node attributes: {other.nodes[node_id]}")
                return False

        self_edges = set(self.edges)
        other_edges = set(other.edges)

        if self_edges != other_edges:
            logger.info("Edge sets differ.")
            logger.info(f"Edges in self but not in other: {self_edges - other_edges}")
            logger.info(f"Edges in other but not in self: {other_edges - self_edges}")
            return False

        for edge in self_edges:
            if self.edges[edge] != other.edges[edge]:
                logger.info(f"Edge attributes differ for edge {edge}.")
                logger.info(f"Self edge attributes: {self.edges[edge]}")
                logger.info(f"Other edge attributes: {other.edges[edge]}")
                return False

        return True

    def to_runtime(self) -> RuntimePipeline:
        operators: list[RuntimeOperator] = []
        ports: list[RuntimePort] = []
        edges: list[RuntimeEdge] = []

        for model in self.operators.values():
            operators.append(model)

        for model in self.ports.values():
            ports.append(model)

        for u, v, _ in self.edges(data=True):
            edges.append(RuntimeEdge(input_id=u, output_id=v))

        return RuntimePipeline(
            id=self.graph["id"],
            canonical_id=self.graph.get("canonical_id", self.graph["id"]),
            revision_id=self.graph.get("revision_id", 1),
            operators=operators,
            ports=ports,
            edges=edges,
        )

    def to_canonical(self) -> CanonicalPipeline:
        operators: list[CanonicalOperator] = []
        ports: list[CanonicalPort] = []
        edges: list[CanonicalEdge] = []

        # Extract canonical operators (deduplicate parallel instances)
        canonical_ops_seen = set()
        for runtime_op in self.operators.values():
            if runtime_op.canonical_id not in canonical_ops_seen:
                canonical_ops_seen.add(runtime_op.canonical_id)
                # Convert runtime operator back to canonical using conversion method
                canonical_op = runtime_op.to_canonical()
                operators.append(canonical_op)

        # Extract canonical ports (deduplicate parallel instances)
        canonical_ports_seen = set()
        for runtime_port in self.ports.values():
            if runtime_port.canonical_id not in canonical_ports_seen:
                canonical_ports_seen.add(runtime_port.canonical_id)
                # Convert runtime port back to canonical using conversion method
                canonical_port = runtime_port.to_canonical()
                ports.append(canonical_port)

        # Extract canonical edges (deduplicate parallel instances)
        canonical_edges_seen = set()
        for u, v, _ in self.edges(data=True):
            runtime_input_port = self.ports.get(u)
            runtime_output_port = self.ports.get(v)

            if runtime_input_port and runtime_output_port:
                edge_key = (
                    runtime_input_port.canonical_id,
                    runtime_output_port.canonical_id,
                )
                if edge_key not in canonical_edges_seen:
                    canonical_edges_seen.add(edge_key)
                    edges.append(
                        CanonicalEdge(
                            input_id=runtime_input_port.canonical_id,
                            output_id=runtime_output_port.canonical_id,
                        )
                    )

        return CanonicalPipeline(
            id=self.graph.get("canonical_id", self.graph["id"]),
            revision_id=self.graph.get("revision_id", 1),
            operators=operators,
            ports=ports,
            edges=edges,
        )

    def get_parallel_group(
        self, canonical_operator_id: IdType
    ) -> list[RuntimeOperator]:
        """Get all parallel instances of an operator by canonical ID."""
        return [
            op
            for op in self.operators.values()
            if op.canonical_id == canonical_operator_id
        ]

    @property
    def operators(self) -> dict[IdType, RuntimeOperator]:
        return {
            n: RuntimeOperator(**data)
            for n, data in self.nodes(data=True)
            if data["node_type"] == NodeType.operator
        }

    @property
    def ports(self) -> dict[IdType, RuntimePort]:
        return {
            n: RuntimePort(**data)
            for n, data in self.nodes(data=True)
            if data["node_type"] == NodeType.port
        }

    def get_operator_ports(self, operator_id: IdType) -> dict[IdType, RuntimePort]:
        if isinstance(operator_id, str):
            operator_id = IdType(operator_id)
        return {k: v for k, v in self.ports.items() if v.operator_id == operator_id}

    def get_operator(self, operator_id: IdType) -> RuntimeOperator | None:
        if isinstance(operator_id, str):
            operator_id = IdType(operator_id)

        return self.operators.get(operator_id, None)

    def get_operator_outputs(self, operator_id: IdType) -> dict[IdType, RuntimeOutput]:
        ports = self.get_operator_ports(operator_id)
        return {
            k: RuntimeOutput(**v.model_dump())
            for k, v in ports.items()
            if v.port_type == PortType.output
        }

    def get_operator_inputs(self, operator_id: IdType) -> dict[IdType, RuntimeInput]:
        ports = self.get_operator_ports(operator_id)
        return {
            k: RuntimeInput(**v.model_dump())
            for k, v in ports.items()
            if v.port_type == PortType.input
        }

    def add_node_model(self, node: RuntimePort | RuntimeOperator):
        if self.has_node(node.id):
            raise ValueError(
                f"Node {node.id} already exists in the graph, occured when adding {node.model_dump()}."
            )
        self.add_node(node.id, **node.model_dump())

    def add_edge_model(self, edge: RuntimeEdge):
        if self.has_edge(edge.input_id, edge.output_id):
            raise ValueError(
                f"Edge {edge.input_id} -> {edge.output_id} already exists in the graph."
            )
        self.add_edge(edge.input_id, edge.output_id, **edge.model_dump())

    def add_node(self, node_for_adding, **attr):
        super().add_node(node_for_adding, **attr)
        self._needs_rebuild = True

    def add_edge(self, u_of_edge, v_of_edge, **attr):
        super().add_edge(u_of_edge, v_of_edge, **attr)
        self._needs_rebuild = True

    def remove_node(self, n):
        super().remove_node(n)
        self._needs_rebuild = True

    def remove_edge(self, u, v):
        super().remove_edge(u, v)
        self._needs_rebuild = True

    def get_operator_graph(self) -> nx.DiGraph:
        if self._needs_rebuild or self._operator_graph is None:
            self._build_operator_graph()
        return self._operator_graph

    def get_predecessors(self, node_id: IdType) -> list[IdType]:
        return list(self.predecessors(node_id))

    async def get_predecessors_async(
        self, node_id: IdType
    ) -> AsyncGenerator[IdType, None]:
        for predecessor in self.predecessors(node_id):
            yield predecessor

    def get_successors(self, node_id: IdType) -> list[IdType]:
        return list(self.successors(node_id))

    def get_edge_model(self, input_id: IdType, output_id: IdType) -> RuntimeEdge:
        edge = self.get_edge_data(input_id, output_id)
        if not edge:
            raise ValueError(f"Edge not found between {input_id} and {output_id}")
        return RuntimeEdge(**edge)
