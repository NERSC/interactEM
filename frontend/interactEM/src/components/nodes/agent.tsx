import { Typography } from "@mui/material"
import type { NodeProps } from "@xyflow/react"
import { NodeResizer, useReactFlow } from "@xyflow/react"
import { useCallback } from "react"
import { AgentStatus } from "../../types/gen"
import { type AgentNodeType, DisplayNodeType } from "../../types/nodes"
import AgentTooltip from "../agents/tooltip"
import { StatusDot } from "../statusdot"

const AgentNode = ({ data, id, selected }: NodeProps<AgentNodeType>) => {
  const shortId = data.uri.id.substring(0, 6)
  const displayName = data.name?.trim() ? data.name : `Agent ${shortId}`
  const { getNodes, setNodes } = useReactFlow()

  const childNodes = getNodes().filter(
    (node) =>
      node.parentId === id &&
      (node.type === DisplayNodeType.image ||
        node.type === DisplayNodeType.operator),
  )

  const operatorCount =
    childNodes.length || data.operator_assignments?.length || 0
  const hasOperators = operatorCount > 0

  const hasErrors = data.error_messages && data.error_messages.length > 0
  const effectiveStatus =
    data.status === "idle" && hasErrors
      ? AgentStatus.deployment_error
      : data.status

  // Function to layout child nodes when agent node is double-clicked
  const handleDoubleClick = useCallback(() => {
    if (!hasOperators) return

    const agent = getNodes().find((node) => node.id === id)
    if (!agent) return

    const agentWidth = agent.width || 300
    const agentHeight = agent.height || 200

    // Get all child nodes
    const childNodes = getNodes().filter((node) => node.parentId === id)
    if (childNodes.length === 0) return

    const headerHeight = 40

    // Available space for layout
    const availableWidth = agentWidth - 20 // 10px padding on each side
    const availableHeight = agentHeight - headerHeight - 20 // minus header and padding

    // Calculate grid dimensions based on number of children
    const cols = Math.ceil(Math.sqrt(childNodes.length))
    const rows = Math.ceil(childNodes.length / cols)

    // Calculate cell size
    const cellWidth = availableWidth / cols
    const cellHeight = availableHeight / rows

    // Update positions of child nodes
    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.parentId === id) {
          // Find index of this child
          const index = childNodes.findIndex((child) => child.id === node.id)
          const col = index % cols
          const row = Math.floor(index / cols)

          // Calculate position relative to parent
          // Adding 10px padding and header height
          return {
            ...node,
            position: {
              x: 10 + col * cellWidth + cellWidth / 2 - (node.width || 150) / 2,
              y:
                headerHeight +
                10 +
                row * cellHeight +
                cellHeight / 2 -
                (node.height || 60) / 2,
            },
          }
        }
        return node
      }),
    )
  }, [id, getNodes, setNodes, hasOperators])

  return (
    <div
      className={`agent-node ${selected ? "agent-node-selected" : ""} ${hasOperators ? "has-operators" : ""}`}
      onDoubleClick={handleDoubleClick}
    >
      <NodeResizer isVisible={selected} minWidth={100} minHeight={30} />
      <div className="agent-header-compact">
        <div className="agent-title">
          <StatusDot
            status={effectiveStatus}
            tooltipContent={<AgentTooltip data={data} />}
          />
          <Typography variant="subtitle1">{displayName}</Typography>
        </div>
        {hasOperators && (
          <Typography variant="caption" className="operator-count">
            {operatorCount} operator{operatorCount !== 1 ? "s" : ""}
          </Typography>
        )}
      </div>
    </div>
  )
}

export default AgentNode
