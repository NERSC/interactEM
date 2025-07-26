import { PlayCircleOutline } from "@mui/icons-material"
import {
  Box,
  Drawer,
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from "@mui/material"
import type React from "react"
import { useState } from "react"
import { usePipelineStore } from "../../stores"
import { DeploymentsList } from "./deploymentslist"

interface DeploymentManagementPanelProps {
  open: boolean
  onClose: () => void
  onRevisionClick?: (pipelineId: string, revisionId: number) => void
}

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

const DeploymentManagementIcon = PlayCircleOutline

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index} style={{ height: "100%" }}>
      {value === index && (
        <Box sx={{ height: "100%", overflow: "auto" }}>{children}</Box>
      )}
    </div>
  )
}

export const DeploymentManagementPanel: React.FC<
  DeploymentManagementPanelProps
> = ({ open, onClose, onRevisionClick }) => {
  const { currentPipelineId } = usePipelineStore()
  const [currentTab, setCurrentTab] = useState(0)

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue)
  }

  const handleDeploymentClick = (deployment: any) => {
    // When a deployment is clicked, switch to that pipeline and revision
    onRevisionClick?.(deployment.pipeline_id, deployment.revision_id)
  }

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box
        sx={{
          width: 400,
          height: "100%",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: "divider" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <DeploymentManagementIcon />
            <Typography variant="h6">Pipeline Deployments</Typography>
          </Box>
        </Box>

        {/* Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
          <Tabs value={currentTab} onChange={handleTabChange}>
            <Tab label="Active" />
            <Tab label="Current Pipeline" />
            <Tab label="All Deployments" />
          </Tabs>
        </Box>

        {/* Tab Content */}
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          <TabPanel value={currentTab} index={0}>
            <DeploymentsList
              variant="active"
              showPipelineInfo={true}
              onDeploymentClick={handleDeploymentClick}
              emptyMessage="No active deployments across all pipelines"
            />
          </TabPanel>

          <TabPanel value={currentTab} index={1}>
            <DeploymentsList
              variant="pipeline"
              pipelineId={currentPipelineId}
              showPipelineInfo={false}
              onDeploymentClick={handleDeploymentClick}
              emptyMessage="No deployments for this pipeline"
            />
          </TabPanel>

          <TabPanel value={currentTab} index={2}>
            <DeploymentsList
              variant="all"
              showPipelineInfo={true}
              onDeploymentClick={handleDeploymentClick}
              emptyMessage="No deployments found"
            />
          </TabPanel>
        </Box>
      </Box>
    </Drawer>
  )
}

export const DeploymentManagementButton: React.FC<{
  onClick: () => void
  hasActiveDeployments?: boolean
}> = ({ onClick, hasActiveDeployments = false }) => {
  return (
    <Tooltip title="Deployment Management">
      <IconButton
        size="small"
        onClick={onClick}
        sx={{
          backgroundColor: hasActiveDeployments
            ? "success.main"
            : "transparent",
          color: hasActiveDeployments ? "success.contrastText" : "inherit",
          marginX: 0.5,
          "&:hover": {
            backgroundColor: hasActiveDeployments
              ? "success.dark"
              : "action.hover",
            color: hasActiveDeployments ? "success.contrastText" : "inherit",
          },
        }}
      >
        <DeploymentManagementIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  )
}
