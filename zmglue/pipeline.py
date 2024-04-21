from uuid import UUID

import networkx as nx
from pydantic import ValidationError

from zmglue.types import EdgeJSON, NodeJSON, NodePairJSON, PipelineJSON, URIBase


class Pipeline(nx.DiGraph):

    @classmethod
    def from_pipeline(cls, pipeline: PipelineJSON) -> "Pipeline":
        graph = cls(id=pipeline.id)
        for node in pipeline.nodes:
            graph.add_node(node.id, **node.model_dump())

        for edge in pipeline.edges:
            nodes: NodePairJSON = edge.nodes
            if nodes.input and nodes.output:
                graph.add_edge(nodes.input.id, nodes.output.id, **edge.model_dump())

        return graph

    @classmethod
    def from_node_neighborhood(cls, graph: "Pipeline", node_id) -> "Pipeline":
        subgraph = cls(id=node_id)

        neighbors = list(graph.predecessors(node_id)) + list(graph.successors(node_id))
        neighbors_and_me = set(neighbors + [node_id])

        for node in neighbors_and_me:
            subgraph.add_node(node, **graph.nodes[node])

        for u, v in graph.edges:
            if u in neighbors_and_me and v in neighbors_and_me:
                subgraph.add_edge(u, v, **graph.edges[u, v])

        return subgraph

    def to_json(self) -> PipelineJSON:
        nodes = []
        edges = []
        for node_id, data in self.nodes.data():
            node = NodeJSON(**data)
            nodes.append(node)

        for input_node_id, output_node_id, data in self.edges.data():
            edge = EdgeJSON(**data)
            edges.append(edge)
        try:
            return PipelineJSON(id=self.graph["id"], nodes=nodes, edges=edges)
        except ValidationError as e:
            raise e

    def get_predecessors(self, node_id) -> list[UUID]:
        return list(self.predecessors(node_id))
    
    def get_successors(self, node_id) -> list[UUID]:
        return list(self.successors(node_id))
