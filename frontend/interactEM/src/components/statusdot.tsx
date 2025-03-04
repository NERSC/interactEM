import { Badge, Tooltip } from "@mui/material"
import type { AgentStatus } from "../types/agent"

type StatusDotProps = {
  status: AgentStatus
  tooltipContent?: React.ReactNode
}

export const StatusDot = ({ status, tooltipContent }: StatusDotProps) => {
  const color =
    {
      initializing: "info",
      idle: "success",
      busy: "warning",
      error: "error",
      shutting_down: "warning",
    }[status] || "error"

  const badgeElement = <Badge variant="dot" color={color as any} />

  if (tooltipContent) {
    return (
      <Tooltip title={tooltipContent} arrow placement="top">
        <div style={{ cursor: "pointer" }}>{badgeElement}</div>
      </Tooltip>
    )
  }

  return badgeElement
}
