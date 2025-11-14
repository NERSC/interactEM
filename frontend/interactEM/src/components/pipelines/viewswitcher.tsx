import { Edit, PlayArrow } from "@mui/icons-material"
import { Button, useTheme } from "@mui/material"
import type React from "react"
import {
  ACTIVE_DEPLOYMENT_STATES,
  RUNNING_STATE,
  useInfinitePipelineDeployments,
} from "../../hooks/api/useDeploymentsQuery"
import { ViewMode, usePipelineStore, useViewModeStore } from "../../stores"

export const ViewSwitcher: React.FC = () => {
  const theme = useTheme()
  const { viewMode, setViewMode } = useViewModeStore()
  const { currentPipelineId, setSelectedRuntimePipelineId } = usePipelineStore()
  const { data } = useInfinitePipelineDeployments(
    currentPipelineId,
    ACTIVE_DEPLOYMENT_STATES,
  )

  const isComposer = viewMode === ViewMode.Composer

  const handleToggle = () => {
    if (isComposer) {
      // Switching to Runtime view - select the most recent running deployment
      const allDeployments = data?.pages?.flatMap((page) => page.data) ?? []
      const runningDeployments = allDeployments.filter(
        (d) => d.state === RUNNING_STATE,
      )

      if (runningDeployments.length > 0) {
        // Sort by created_at descending to get the most recent
        const mostRecent = runningDeployments.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )[0]!
        setSelectedRuntimePipelineId(mostRecent.id)
      }
    }

    const newMode = isComposer ? ViewMode.Runtime : ViewMode.Composer
    setViewMode(newMode)
  }

  // Check if there's any running deployment
  const hasRunningDeployment = data?.pages?.some((page) =>
    page.data.some((deployment) => deployment.state === RUNNING_STATE),
  )

  // Use green if in composer view with a running deployment, always blue in runtime view
  const buttonColor =
    isComposer && hasRunningDeployment
      ? theme.palette.success.main
      : theme.palette.primary.main

  const hoverColor =
    isComposer && hasRunningDeployment
      ? theme.palette.success.dark
      : theme.palette.primary.dark

  return (
    <Button
      onClick={handleToggle}
      variant="contained"
      endIcon={isComposer ? <PlayArrow /> : <Edit />}
      sx={{
        borderRadius: "24px",
        px: 2.5,
        py: 1,
        fontWeight: 600,
        fontSize: "0.95rem",
        textTransform: "none",
        backgroundColor: buttonColor,
        color: "white",
        boxShadow: `0 4px 20px ${buttonColor}66`,
        transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        "&:hover": {
          backgroundColor: hoverColor,
          boxShadow: `0 6px 24px ${buttonColor}99`,
          transform: "translateY(-2px)",
        },
        "&:active": {
          transform: "translateY(0)",
        },
      }}
    >
      {isComposer ? "View Deployments" : "Edit Pipelines"}
    </Button>
  )
}
