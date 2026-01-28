import CloseIcon from "@mui/icons-material/Close"
import Button from "@mui/material/Button"
import Chip from "@mui/material/Chip"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import Tooltip from "@mui/material/Tooltip"
import Typography from "@mui/material/Typography"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { agentsShutdownAgentMutation } from "../../client"
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
  const [confirmOpen, setConfirmOpen] = useState(false)
  const shortId = agent.uri.id.substring(0, 6)
  const displayName = agent.name?.trim() ? agent.name : shortId
  const shutdownAgent = useMutation({
    ...agentsShutdownAgentMutation(),
    onSuccess: () => {
      setConfirmOpen(false)
    },
    onError: (error) => {
      console.error("Failed to shut down agent:", error)
    },
  })

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
          onDelete={(event) => {
            event.stopPropagation()
            setConfirmOpen(true)
          }}
          deleteIcon={<CloseIcon fontSize="small" />}
          sx={{
            fontWeight: 500,
            fontSize: "1rem",
            "& .MuiChip-deleteIcon": {
              opacity: 0,
              pointerEvents: "none",
              transition: "opacity 150ms ease-in-out",
            },
            "&:hover .MuiChip-deleteIcon, &:focus-visible .MuiChip-deleteIcon":
              {
                opacity: 1,
                pointerEvents: "auto",
              },
          }}
        />
      </Tooltip>

      <AgentLogsDialog
        open={open}
        onClose={() => setOpen(false)}
        agentId={agent.uri.id}
        agentLabel={displayName}
      />

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Are you sure?</DialogTitle>
        <DialogContent>
          <Typography>This will shut down agent {displayName}.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            color="error"
            onClick={() =>
              shutdownAgent.mutate({
                path: {
                  agent_id: agent.uri.id,
                },
              })
            }
            disabled={shutdownAgent.isPending}
          >
            {shutdownAgent.isPending ? "Shutting down..." : "Shutdown"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
