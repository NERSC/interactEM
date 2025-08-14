import { PlayCircleOutline } from "@mui/icons-material"
import { Box, Divider, Typography } from "@mui/material"
import { useState } from "react"
import type { PipelineDeploymentPublic } from "../../client"
import { useActivePipeline } from "../../hooks/api/useActivePipeline"
import { useDeployment } from "../../hooks/api/useDeploymentsQuery"
import { usePipelineStore } from "../../stores"
import { DeploymentItem } from "./deploymentitem"
import { DeploymentManagementPanel } from "./deploymentmanagementpanel"
import { HudListButton } from "./hudlistbutton"
import { ViewModeToggle } from "./viewmodetoggle"

export const HudRunning: React.FC = () => {
  const { setSelectedRuntimePipelineId } = usePipelineStore()
  const [isDeploymentManagementOpen, setIsDeploymentManagementOpen] =
    useState(false)

  const { runtimePipelineId, isLoading: pipelineLoading } = useActivePipeline()

  const {
    data: deployment,
    isLoading: deploymentLoading,
    error,
  } = useDeployment(runtimePipelineId)

  const handleOpenDeploymentManagement = () => {
    setIsDeploymentManagementOpen(true)
  }

  const handleCloseDeploymentManagement = () => {
    setIsDeploymentManagementOpen(false)
  }

  const handleDeploymentClick = (deployment: PipelineDeploymentPublic) => {
    setSelectedRuntimePipelineId(deployment.id)
  }

  const loading = pipelineLoading || deploymentLoading

  return (
    <>
      <Box
        sx={{
          p: 1,
          bgcolor: "background.paper",
          borderRadius: 1,
          boxShadow: 1,
          minWidth: 300,
          display: "flex",
          alignItems: "center",
        }}
      >
        {/* View Mode Toggle */}
        <ViewModeToggle />

        {/* Deployment Management Button */}
        <HudListButton
          tooltip="Deployment Management"
          icon={<PlayCircleOutline fontSize="small" />}
          onClick={handleOpenDeploymentManagement}
          active={false}
        />

        <Divider orientation="vertical" flexItem sx={{ mr: 1 }} />

        {/* Deployment Display */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          {loading ? (
            <Typography
              variant="body2"
              color="text.secondary"
              noWrap
              sx={{ fontStyle: "italic" }}
            >
              Loading deployment...
            </Typography>
          ) : deployment ? (
            <DeploymentItem
              deployment={deployment}
              showPipelineInfo
              disableClick
              hideActiveIndicator
            />
          ) : error ? (
            <Typography variant="body2" color="error" noWrap>
              Failed to load deployment
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary" noWrap>
              No deployment selected
            </Typography>
          )}
        </Box>
      </Box>

      {/* Deployment Management Panel */}
      <DeploymentManagementPanel
        open={isDeploymentManagementOpen}
        onClose={handleCloseDeploymentManagement}
        onDeploymentClick={handleDeploymentClick}
      />
    </>
  )
}
