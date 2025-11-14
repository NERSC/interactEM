import ListIcon from "@mui/icons-material/List"
import { Box } from "@mui/material"
import { useState } from "react"
import type { PipelineDeploymentPublic } from "../../client"
import { useActivePipeline } from "../../hooks/api/useActivePipeline"
import { useDeployment } from "../../hooks/api/useDeploymentsQuery"
import { usePipelineStore } from "../../stores"
import { DeploymentManagementPanel } from "./deploymentmanagementpanel"
import { HudListButton } from "./hudlistbutton"
import { HudRuntimeInfo } from "./hudruntimeinfo"

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
          display: "flex",
          alignItems: "center",
          gap: 0.5,
        }}
      >
        {/* Deployment Management Button */}
        <HudListButton
          tooltip="Deployment List"
          icon={<ListIcon fontSize="small" />}
          onClick={handleOpenDeploymentManagement}
          active={false}
        />

        {/* Deployment Info */}
        <HudRuntimeInfo
          deployment={deployment}
          isLoading={loading}
          error={error}
        />
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
