import { Badge, type BadgeProps, Tooltip } from "@mui/material"
import type { AgentStatus } from "../types/gen"
import { getAgentStatusColor } from "../utils/statusColor"

type StatusDotProps = {
  status: AgentStatus
  tooltipContent?: React.ReactNode
}

export const StatusDot = ({ status, tooltipContent }: StatusDotProps) => {
  const color = getAgentStatusColor(status)
  const badgeColor: BadgeProps["color"] = color

  const badgeElement = <Badge variant="dot" color={badgeColor} />

  if (tooltipContent) {
    return (
      <Tooltip title={tooltipContent} arrow placement="top">
        <div style={{ cursor: "pointer" }}>{badgeElement}</div>
      </Tooltip>
    )
  }

  return badgeElement
}
