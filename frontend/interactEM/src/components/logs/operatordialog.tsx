import CloseIcon from "@mui/icons-material/Close"
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Tab,
  Tabs,
  Typography,
} from "@mui/material"
import React, { useState, useMemo } from "react"
import { useOperatorLogs } from "../../hooks/nats/useOperatorLogs"
import type { OperatorLog } from "../../types/gen"
import LogsList from "./list"
import { CloseDialogButton, LogsPanel } from "./styles"

interface OperatorLogsDialogProps {
  open: boolean
  onClose: () => void
  canonicalOperatorId: string
  operatorLabel: string
}

const OperatorLogsDialog: React.FC<OperatorLogsDialogProps> = ({
  open,
  onClose,
  canonicalOperatorId,
  operatorLabel,
}) => {
  const { logs, operators } = useOperatorLogs({
    canonicalOperatorId,
  })

  const [selectedTab, setSelectedTab] = useState(0)

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue)
  }

  // Group logs by runtime operator ID and get displayed logs based on tab
  const displayedLogs = useMemo(() => {
    if (selectedTab === 0) {
      return logs
    }

    // Show logs for specific instance
    const operatorId = operators[selectedTab - 1]?.id
    return operatorId
      ? logs.filter((log) => log.operator_id === operatorId)
      : []
  }, [logs, operators, selectedTab])

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            Logs: {operatorLabel}
            {operators.length > 1 && ` (${operators.length} instances)`}
          </Typography>
          <CloseDialogButton onClick={onClose} size="small">
            <CloseIcon />
          </CloseDialogButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {operators.length === 0 ? (
          <Typography color="text.secondary">
            No runtime operators found for this canonical operator.
          </Typography>
        ) : (
          <>
            {operators.length > 1 && (
              <Tabs
                value={selectedTab}
                onChange={handleTabChange}
                sx={{ mb: 2 }}
              >
                <Tab label="All Instances" />
                {operators.map((op, idx) => (
                  <Tab key={op.id} label={`Instance ${idx}`} />
                ))}
              </Tabs>
            )}

            <LogsPanel>
              <LogsList
                logs={displayedLogs}
                showModule={false}
                showInstance={operators.length > 1 && selectedTab === 0}
                getInstanceLabel={(log) => {
                  const opLog = log as OperatorLog
                  const opIndex = operators.findIndex(
                    (o) => o.id === opLog.operator_id,
                  )
                  return `[${opIndex >= 0 ? opIndex : "?"}]`
                }}
                emptyMessage={
                  selectedTab === 0
                    ? "No logs yet..."
                    : "No logs yet for this instance..."
                }
              />
            </LogsPanel>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default React.memo(OperatorLogsDialog)
