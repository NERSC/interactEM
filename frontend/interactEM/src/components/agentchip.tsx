import Chip from "@mui/material/Chip"
import Tooltip from "@mui/material/Tooltip"
import type { Agent } from "../types/agent"
import { getAgentStatusColor } from "../utils/statusColor"
import AgentTooltip from "./agenttooltip"
import { StatusDot } from "./statusdot"

interface AgentChipProps {
  agent: Agent
}

export default function AgentChip({ agent }: AgentChipProps) {
  const shortId = agent.uri.id.substring(0, 6)
  const displayName = agent.name?.trim() ? agent.name : shortId
  return (
    <Tooltip title={<AgentTooltip data={agent} />} arrow>
      <Chip
        icon={<StatusDot status={agent.status} />}
        label={displayName}
        color={getAgentStatusColor(agent.status)}
        variant="outlined"
        sx={{ fontWeight: 500, fontSize: "1rem" }}
      />
    </Tooltip>
  )
}
