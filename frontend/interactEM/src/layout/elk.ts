import { type Edge, type Node, Position } from "@xyflow/react"
import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js"

const elk = new ELK()

// Minimum Y offset for child nodes to avoid overlapping with agent header
const AGENT_HEADER_HEIGHT = 50

export const layoutNodesWithELK = async <T extends Node>(
  nodes: T[],
  edges: Edge[] = [],
  options: {
    direction?: "RIGHT" | "DOWN"
    nodeSpacing?: number
    rankSpacing?: number
    padding?: number
  } = {},
): Promise<{ nodes: T[]; edges: Edge[] }> => {
  if (nodes.length === 0) return { nodes: [], edges: [] }

  const {
    direction = "RIGHT",
    nodeSpacing = 50,
    rankSpacing = 75,
    padding = 20,
  } = options

  const isHorizontal = direction === "RIGHT"

  // Create node maps for quick lookup
  const nodeMap = new Map<string, T>(
    nodes.map((node) => [node.id, { ...node }]),
  )
  const childToParentMap = new Map<string, string>()

  // Identify operators and their parent agents
  const operatorNodes: T[] = []
  const agentNodeIds = new Set<string>()

  // Map children to parents and separate agents from operators
  for (const node of nodes) {
    if (node.parentId) {
      childToParentMap.set(node.id, node.parentId)
      operatorNodes.push(node)
    } else if (node.type === "agent") {
      agentNodeIds.add(node.id)
    }
  }

  // Create ELK graph with only operator nodes (no hierarchy)
  const elkGraph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": direction,
      "elk.spacing.nodeNode": String(nodeSpacing),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(rankSpacing),
      "elk.padding": `[top=${padding}, left=${padding}, bottom=${padding}, right=${padding}]`,
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    },
    children: [],
    edges: [],
  }

  // Add all operator nodes to the flat graph
  for (const node of operatorNodes) {
    elkGraph.children!.push({
      id: node.id,
      width: node.width || 172,
      height: node.height || 36,
    })
  }

  // Add edges between operators
  for (const edge of edges) {
    // Only consider edges between operator nodes
    if (
      nodeMap.has(edge.source) &&
      nodeMap.has(edge.target) &&
      !agentNodeIds.has(edge.source) &&
      !agentNodeIds.has(edge.target)
    ) {
      elkGraph.edges!.push({
        id: edge.id || `${edge.source}-${edge.target}`,
        sources: [edge.source],
        targets: [edge.target],
      })
    }
  }

  // Run ELK layout on the operator graph
  const elkLayouted = await elk.layout(elkGraph)

  // Update operator node positions from ELK layout results
  if (elkLayouted.children) {
    for (const elkNode of elkLayouted.children) {
      const node = nodeMap.get(elkNode.id)
      if (node) {
        // Store absolute positions
        const x = elkNode.x || 0
        let y = elkNode.y || 0

        // If this is a child node, ensure it's below the agent header
        if (node.parentId) {
          // Add padding for the agent header area
          y = Math.max(y, AGENT_HEADER_HEIGHT)
          node.position = { x, y }
        } else {
          node.position = { x, y }
        }
      }
    }
  }

  // Set connection points based on layout direction
  for (const node of nodes) {
    const updatedNode = nodeMap.get(node.id)
    if (updatedNode) {
      updatedNode.targetPosition = isHorizontal ? Position.Left : Position.Top
      updatedNode.sourcePosition = isHorizontal
        ? Position.Right
        : Position.Bottom
    }
  }

  // Place agent nodes at a sensible initial position if they're new
  // Let the parent auto-resize based on children with expandParent
  for (const agentId of agentNodeIds) {
    const agentNode = nodeMap.get(agentId)
    if (agentNode && !agentNode.position.x && !agentNode.position.y) {
      // Only set position for new agent nodes
      agentNode.position = { x: 0, y: 0 }
    }
  }

  return {
    nodes: Array.from(nodeMap.values()),
    edges,
  }
}
