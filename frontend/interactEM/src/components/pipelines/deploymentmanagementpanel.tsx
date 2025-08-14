import { PlayCircleOutline } from "@mui/icons-material"
import { Box, Drawer, Tab, Tabs, Typography } from "@mui/material"
import type React from "react"
import { useState } from "react"
import type { PipelineDeploymentPublic } from "../../client"
import { DeploymentsList } from "./deploymentslist"

interface DeploymentManagementPanelProps {
  open: boolean
  onClose: () => void
  onDeploymentClick?: (deployment: PipelineDeploymentPublic) => void
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
> = ({ open, onClose, onDeploymentClick }) => {
  const [currentTab, setCurrentTab] = useState(0)

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue)
  }

  const handleDeploymentClick = (deployment: PipelineDeploymentPublic) => {
    onDeploymentClick?.(deployment)
    onClose()
  }

  return (
    <Drawer anchor="left" open={open} onClose={onClose}>
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
            <Tab label="All" />
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
