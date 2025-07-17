import { Done, Error as ErrorIcon, PlayArrow } from "@mui/icons-material"
import { Box, Chip, ListItem, ListItemText, Typography } from "@mui/material"
import { formatDistanceToNow } from "date-fns"
import type React from "react"
import type { PipelineDeploymentPublic, PipelineDeploymentState } from "../../client"
import { usePipelineName } from "../../hooks/api/usePipelineQuery"
import {
  formatDeploymentState,
  getDeploymentStateColor,
  isActiveDeploymentState,
} from "../../utils/deployments"
import { StopPipelineButton } from "./stopbutton"

interface DeploymentItemProps {
  deployment: PipelineDeploymentPublic
  showPipelineInfo?: boolean
  onDeploymentClick?: (deployment: PipelineDeploymentPublic) => void
}

const STATE_ICONS: Partial<Record<PipelineDeploymentState, React.ReactElement>> = {
  running: <PlayArrow fontSize="small" />,
  cancelled: <Done fontSize="small" />,
  failed_to_start: <ErrorIcon fontSize="small" />,
} as const

export const DeploymentItem: React.FC<DeploymentItemProps> = ({
  deployment,
  showPipelineInfo = false,
  onDeploymentClick,
}) => {
  const pipelineName = usePipelineName(deployment.pipeline_id)

  const handleDeploymentClick = () => {
    onDeploymentClick?.(deployment)
  }

  const timeAgo = formatDistanceToNow(new Date(deployment.created_at), {
    addSuffix: true,
  })
  const isActive = isActiveDeploymentState(deployment.state)

  return (
    <ListItem
      onClick={handleDeploymentClick}
      sx={{
        cursor: onDeploymentClick ? "pointer" : "default",
        "&:hover": onDeploymentClick
          ? {
              bgcolor: "action.hover",
            }
          : {},
        borderLeft: isActive ? "3px solid" : "3px solid transparent",
        borderLeftColor: isActive ? "primary.main" : "transparent",
      }}
    >
      <ListItemText
        primary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Chip
              icon={STATE_ICONS[deployment.state] ?? undefined}
              label={formatDeploymentState(deployment.state)}
              color={getDeploymentStateColor(deployment.state)}
              size="small"
              variant={isActive ? "filled" : "outlined"}
            />
            {showPipelineInfo && (
              <Typography variant="body2" color="text.secondary">
                {pipelineName}
              </Typography>
            )}
          </Box>
        }
        secondary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
            <Typography variant="caption">
              Revision {deployment.revision_id} • {timeAgo}
            </Typography>
          </Box>
        }
      />
      {isActive && (
        <Box sx={{ ml: 1 }} onClick={(e) => e.stopPropagation()}>
          <StopPipelineButton deploymentId={deployment.id} />
        </Box>
      )}
    </ListItem>
  )
}
