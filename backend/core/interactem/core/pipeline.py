from collections.abc import AsyncGenerator

import networkx as nx

from .logger import get_logger
from .models import (
    EdgeJSON,
    IdType,
    InputJSON,
    NodeType,
    OperatorJSON,
    OutputJSON,
    PipelineJSON,
    PortJSON,
    PortType,
)

logger = get_logger()


class Pipeline(nx.DiGraph):
    def __init__(self, **attr):
        super().__init__(**attr)
        self._operator_graph = nx.DiGraph()
        self._needs_rebuild = True

    @property
    def id(self) -> IdType:
        """Returns the ID of the pipeline graph stored in graph attributes."""
        try:
            return self.graph["id"]
        except KeyError:
            # This case should ideally not happen if constructed via from_pipeline
            # or if id is always provided.
            logger.error("Pipeline graph object missing 'id' attribute in self.graph.")
            raise AttributeError("Pipeline graph object has no 'id' attribute.")

    @classmethod
    def from_pipeline(cls, pipeline: PipelineJSON) -> "Pipeline":
        graph = cls(id=pipeline.id)

        for operator in pipeline.operators:
            graph.add_node_model(operator)

        for port in pipeline.ports:
            graph.add_node_model(port)

        for edge in pipeline.edges:
            graph.add_edge_model(edge)

        return graph

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

    def to_json(self) -> PipelineJSON:
        operators: list[OperatorJSON] = []
        ports: list[PortJSON] = []
        edges: list[EdgeJSON] = []

        for model in self.operators.values():
            operators.append(model)

        for model in self.ports.values():
            ports.append(model)

        for u, v, data in self.edges(data=True):
            edges.append(
                EdgeJSON(
                    input_id=u, output_id=v, num_connections=data["num_connections"]
                )
            )

        return PipelineJSON(
            id=self.graph["id"], operators=operators, ports=ports, edges=edges
        )

    @property
    def operators(self) -> dict[IdType, OperatorJSON]:
        return {
            n: OperatorJSON(**data)
            for n, data in self.nodes(data=True)
            if data["node_type"] == NodeType.operator
        }

    @property
    def ports(self) -> dict[IdType, PortJSON]:
        return {
            n: PortJSON(**data)
            for n, data in self.nodes(data=True)
            if data["node_type"] == NodeType.port
        }

    def get_operator_ports(self, operator_id: IdType) -> dict[IdType, PortJSON]:
        if isinstance(operator_id, str):
            operator_id = IdType(operator_id)
        return {k: v for k, v in self.ports.items() if v.operator_id == operator_id}

    def get_operator(self, operator_id: IdType) -> OperatorJSON:
        if isinstance(operator_id, str):
            operator_id = IdType(operator_id)

        return self.operators[operator_id]

    def get_operator_outputs(self, operator_id: IdType) -> dict[IdType, OutputJSON]:
        ports = self.get_operator_ports(operator_id)
        return {
            k: OutputJSON(**v.model_dump())
            for k, v in ports.items()
            if v.port_type == PortType.output
        }

    def get_operator_inputs(self, operator_id: IdType) -> dict[IdType, InputJSON]:
        ports = self.get_operator_ports(operator_id)
        return {
            k: InputJSON(**v.model_dump())
            for k, v in ports.items()
            if v.port_type == PortType.input
        }

    def add_node_model(self, node: PortJSON | OperatorJSON):
        if self.has_node(node.id):
            raise ValueError(
                f"Node {node.id} already exists in the graph, occured when adding {node.model_dump()}."
            )
        self.add_node(node.id, **node.model_dump())

    def add_edge_model(self, edge: EdgeJSON):
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

    def get_edge_model(self, input_id: IdType, output_id: IdType) -> EdgeJSON:
        edge = self.get_edge_data(input_id, output_id)
        if not edge:
            raise ValueError(f"Edge not found between {input_id} and {output_id}")
        return EdgeJSON(**edge)
