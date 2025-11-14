import {
  Chip,
  CircularProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material"
import type React from "react"
import type { PipelineDeploymentPublic } from "../../client"
import { usePipelineName } from "../../hooks/api/usePipelineQuery"
import {
  formatDeploymentState,
  getDeploymentStateColor,
} from "../../utils/deployments"
import { RevisionButton } from "./revisionbutton"

interface HudRuntimeInfoProps {
  deployment: PipelineDeploymentPublic | undefined
  isLoading: boolean
  error: Error | null
}

export const HudRuntimeInfo: React.FC<HudRuntimeInfoProps> = ({
  deployment,
  isLoading,
  error,
}) => {
  const pipelineName = usePipelineName(deployment?.pipeline_id || "")

  if (isLoading) {
    return <CircularProgress size={24} />
  }

  if (error) {
    return (
      <Typography variant="body2" color="error">
        Failed to load deployment
      </Typography>
    )
  }

  if (!deployment) {
    return (
      <Typography variant="body2" color="text.secondary">
        No deployment selected
      </Typography>
    )
  }

  return (
    <Stack direction="row" alignItems="center" sx={{ gap: 0.5, flex: 1 }}>
      <Typography
        variant="subtitle1"
        fontWeight="medium"
        noWrap
        sx={{ display: "flex", alignItems: "center" }}
      >
        {pipelineName}
      </Typography>
      <RevisionButton revisionId={deployment.revision_id} />
      <Tooltip
        title={`Deployment is ${formatDeploymentState(deployment.state)}`}
      >
        <Chip
          label={formatDeploymentState(deployment.state)}
          color={getDeploymentStateColor(deployment.state)}
          size="small"
          variant="filled"
        />
      </Tooltip>
    </Stack>
  )
}
