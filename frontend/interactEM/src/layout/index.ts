import dagre from "@dagrejs/dagre"
import { type Edge, type Node, Position } from "@xyflow/react"

const dagreGraph = new dagre.graphlib.Graph()
dagreGraph.setDefaultEdgeLabel(() => ({}))

const nodeWidth = 172
const nodeHeight = 36
const isHorizontal = true

// Generic layout function that can handle any node type
export const layoutNodes = <T extends Node>(
  nodes: T[],
  edges: Edge[] = [],
  options: {
    width?: number
    height?: number
    direction?: "LR" | "TB"
    nodesep?: number
    ranksep?: number
  } = {},
): { nodes: T[]; edges: Edge[] } => {
  if (nodes.length === 0) return { nodes: [], edges: [] }

  const {
    width = nodeWidth,
    height = nodeHeight,
    direction = "LR",
    nodesep = 100,
    ranksep = 100,
  } = options

  // Create a new graph instance to avoid conflicts with concurrent calls
  const graph = new dagre.graphlib.Graph()
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({ rankdir: direction, nodesep, ranksep })

  // Add nodes to graph
  for (const node of nodes) {
    const nodeWidth = node.width || width
    const nodeHeight = node.height || height
    graph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  }

  // Add edges to graph
  for (const edge of edges) {
    if (
      nodes.some((n) => n.id === edge.source) &&
      nodes.some((n) => n.id === edge.target)
    ) {
      graph.setEdge(edge.source, edge.target)
    }
  }

  dagre.layout(graph)

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = graph.node(node.id)
    const nodeWidth = node.width || width
    const nodeHeight = node.height || height

    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      // We are shifting the dagre node position (anchor=center center) to the top left
      // so it matches the React Flow node anchor point (top left).
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
      draggable: true,
    } as T
  })

  return { nodes: newNodes, edges }
}
