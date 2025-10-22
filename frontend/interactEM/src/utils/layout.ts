import dagre from "@dagrejs/dagre"
import { type Edge, type Node, Position } from "@xyflow/react"
import type { OperatorPosition } from "../client"

const dagreGraph = new dagre.graphlib.Graph()
dagreGraph.setDefaultEdgeLabel(() => ({}))

const nodeWidth = 172
const nodeHeight = 36
const isHorizontal = true

const transformNodeWithPosition = <T extends Node>(
  node: T,
  position: { x: number; y: number },
): T => ({
  ...node,
  targetPosition: isHorizontal ? Position.Left : Position.Top,
  sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
  position,
  draggable: true,
})

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

    // We are shifting the dagre node position (anchor=center center) to the top left
    // so it matches the React Flow node anchor point (top left).
    const position = {
      x: nodeWithPosition.x - nodeWidth / 2,
      y: nodeWithPosition.y - nodeHeight / 2,
    }

    return transformNodeWithPosition(node, position) as T
  })

  return { nodes: newNodes, edges }
}

// Apply saved positions to nodes, falling back to dagre layout for unmapped nodes
export const applyPositionsToNodes = <T extends Node>(
  nodes: T[],
  savedPositions: OperatorPosition[],
  edges: Edge[] = [],
  options?: {
    width?: number
    height?: number
    direction?: "LR" | "TB"
    nodesep?: number
    ranksep?: number
  },
): { nodes: T[]; edges: Edge[] } => {
  // Create a map of saved positions by operator ID
  const positionMap = new Map(
    savedPositions.map((pos) => [pos.canonical_operator_id, pos]),
  )

  // Split nodes into those with saved positions and those without
  const nodesWithPositions: T[] = []
  const nodesWithoutPositions: T[] = []

  for (const node of nodes) {
    if (positionMap.has(node.id)) {
      nodesWithPositions.push(node)
    } else {
      nodesWithoutPositions.push(node)
    }
  }

  // Apply saved positions to existing nodes
  const positionedNodes = nodesWithPositions.map((node) => {
    const savedPos = positionMap.get(node.id)
    if (!savedPos) {
      throw new Error(
        `Invariant violation: position not found for node ${node.id}. This should never happen.`,
      )
    }
    return transformNodeWithPosition(node, {
      x: savedPos.x,
      y: savedPos.y,
    }) as T
  })

  // Apply dagre layout only to new nodes (those without saved positions)
  let newLayoutNodes: T[]
  if (nodesWithoutPositions.length > 0) {
    // Only layout the new nodes, not all nodes
    const dagreResult = layoutNodes(nodesWithoutPositions, edges, options)
    newLayoutNodes = dagreResult.nodes as T[]
  } else {
    newLayoutNodes = []
  }

  // Combine positioned nodes with newly laid out nodes
  const allNewNodes = [...positionedNodes, ...newLayoutNodes]

  return { nodes: allNewNodes, edges }
}
