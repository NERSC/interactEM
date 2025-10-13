import Chip from "@mui/material/Chip"
import Tooltip from "@mui/material/Tooltip"
import { useState } from "react"
import type { AgentVal } from "../../types/gen"
import { getAgentStatusColor } from "../../utils/statusColor"
import AgentLogsDialog from "../logs/agentdialog"
import { StatusDot } from "../statusdot"
import AgentTooltip from "./tooltip"

interface AgentChipProps {
  agent: AgentVal
}

export default function AgentChip({ agent }: AgentChipProps) {
  const [open, setOpen] = useState(false)
  const shortId = agent.uri.id.substring(0, 6)
  const displayName = agent.name?.trim() ? agent.name : shortId

  return (
    <>
      <Tooltip title={<AgentTooltip data={agent} />} arrow>
        <Chip
          icon={<StatusDot status={agent.status} />}
          label={displayName}
          color={getAgentStatusColor(agent.status)}
          variant="outlined"
          onClick={() => setOpen(true)}
          clickable
          sx={{ fontWeight: 500, fontSize: "1rem" }}
        />
      </Tooltip>

      <AgentLogsDialog
        open={open}
        onClose={() => setOpen(false)}
        agentId={agent.uri.id}
        agentLabel={displayName}
      />
    </>
  )
}
