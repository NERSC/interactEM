import networkx as nx

from zmglue.types import (
    EdgeJSON,
    IdType,
    InputJSON,
    NodeType,
    OperatorJSON,
    OutputJSON,
    PipelineJSON,
    PortJSON,
    PortType,
    URIBase,
    URIConnectMessage,
    URIUpdateMessage,
)


class Pipeline(nx.DiGraph):

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
    def from_node_neighborhood(cls, graph: "Pipeline", id: IdType) -> "Pipeline":
        subgraph = cls(id=id)

        neighbors = list(graph.predecessors(id)) + list(graph.successors(id))
        neighbors_and_me = set(neighbors + [id])

        for node in neighbors_and_me:
            subgraph.add_node(node, **graph.nodes[node])

        for u, v in graph.edges:
            if u in neighbors_and_me and v in neighbors_and_me:
                subgraph.add_edge(u, v, **graph.edges[u, v])

        return subgraph

    def to_json(self) -> PipelineJSON:
        operators: list[OperatorJSON] = []
        ports: list[PortJSON] = []
        edges: list[EdgeJSON] = []

        for model in self.operators.values():
            operators.append(model)

        for model in self.ports.values():
            ports.append(model)

        for u, v, _ in self.edges(data=True):
            edges.append(EdgeJSON(input_id=u, output_id=v))

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
        return {k: v for k, v in self.ports.items() if v.operator_id == operator_id}

    def get_operator(self, operator_id: IdType) -> OperatorJSON:
        return OperatorJSON(**self.nodes[operator_id])

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

    def get_predecessors(self, node_id: IdType) -> list[IdType]:
        return list(self.predecessors(node_id))

    def get_successors(self, node_id: IdType) -> list[IdType]:
        return list(self.successors(node_id))

    def get_edge_model(self, input_id: IdType, output_id: IdType) -> EdgeJSON:
        edge = self.get_edge_data(input_id, output_id)
        if not edge:
            raise ValueError(f"Edge not found between {input_id} and {output_id}")
        return EdgeJSON(**edge)

    def update_uri(self, message: URIUpdateMessage) -> URIUpdateMessage:
        node_id = message.id
        if node_id not in self.nodes:
            raise ValueError(f"Port {node_id} not found in the graph.")

        current_node = self.nodes[node_id]
        current_node_model = OutputJSON(**current_node)
        current_uri = current_node_model.uri

        # Ensure current_uri is a URIBase instance
        if not isinstance(current_uri, URIBase):
            current_uri = URIBase(**current_uri)

        # Apply updates from message
        update_data = {k: v for k, v in message.model_dump().items() if v is not None}
        updated_uri = current_uri.model_copy(update=update_data)
        URIBase.model_validate(updated_uri)

        current_node["uri"] = updated_uri

        return message

    def get_connections(self, message: URIConnectMessage) -> list[URIBase]:
        input_id = message.id

        output_ids = self.get_predecessors(input_id)

        output_ports = [
            OutputJSON(**p.model_dump())
            for p in self.ports.values()
            if p.id in output_ids
        ]

        return [p.uri for p in output_ports]
