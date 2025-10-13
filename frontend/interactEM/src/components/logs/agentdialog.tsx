import CloseIcon from "@mui/icons-material/Close"
import { Box, Dialog, DialogContent, DialogTitle } from "@mui/material"
import React from "react"
import { useAgentLogs } from "../../hooks/nats/useAgentLogs"
import LogsList from "./list"
import { CloseDialogButton, LogsPanel } from "./styles"

interface AgentLogsDialogProps {
  open: boolean
  onClose: () => void
  agentId: string
  agentLabel: string
}

const AgentLogsDialog: React.FC<AgentLogsDialogProps> = ({
  open,
  onClose,
  agentId,
  agentLabel,
}) => {
  const { logs } = useAgentLogs({
    id: agentId,
  })

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
      <DialogTitle>
        Agent Logs: {agentLabel}
        <CloseDialogButton aria-label="close" onClick={onClose}>
          <CloseIcon />
        </CloseDialogButton>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ width: "100%", height: "100%" }}>
          <LogsPanel>
            <LogsList logs={logs} showModule={true} />
          </LogsPanel>
        </Box>
      </DialogContent>
    </Dialog>
  )
}

export default React.memo(AgentLogsDialog)
