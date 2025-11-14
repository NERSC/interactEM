import { Done, Error as ErrorIcon, PlayArrow } from "@mui/icons-material"
import {
  Box,
  Chip,
  ListItem,
  ListItemText,
  Tooltip,
  Typography,
} from "@mui/material"
import { formatDistanceToNow } from "date-fns"
import type React from "react"
import type {
  PipelineDeploymentPublic,
  PipelineDeploymentState,
} from "../../client"
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
  disableClick?: boolean
  hideActiveIndicator?: boolean
}

const STATE_ICONS: Partial<
  Record<PipelineDeploymentState, React.ReactElement>
> = {
  running: <PlayArrow fontSize="small" />,
  cancelled: <Done fontSize="small" />,
  failed_to_start: <ErrorIcon fontSize="small" />,
} as const

export const DeploymentItem: React.FC<DeploymentItemProps> = ({
  deployment,
  showPipelineInfo = false,
  onDeploymentClick,
  disableClick = false,
  hideActiveIndicator = false,
}) => {
  const pipelineName = usePipelineName(deployment.pipeline_id)

  // Don't render if we don't have the basic deployment data
  if (!deployment) {
    return null
  }

  // Don't render if we don't have the basic deployment data
  if (!deployment) {
    return null
  }

  const handleDeploymentClick = () => {
    if (disableClick) return
    onDeploymentClick?.(deployment)
  }

  const timeAgo = formatDistanceToNow(new Date(deployment.created_at), {
    addSuffix: true,
  })
  const isActive = isActiveDeploymentState(deployment.state)

  const getChipColor = () => {
    return getDeploymentStateColor(deployment.state)
  }

  const getChipTooltip = () => {
    return `Deployment is ${formatDeploymentState(deployment.state)}`
  }

  const getListItemSx = () => {
    const isClickable = !disableClick && onDeploymentClick

    return {
      cursor: isClickable ? "pointer" : "default",
      borderLeft: "3px solid",
      borderLeftColor:
        !hideActiveIndicator && isActive ? "primary.main" : "transparent",
      "&:hover": isClickable ? { bgcolor: "action.hover" } : {},
    }
  }

  return (
    <ListItem onClick={handleDeploymentClick} sx={getListItemSx()}>
      <ListItemText
        primary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Tooltip title={getChipTooltip()}>
              <Chip
                icon={STATE_ICONS[deployment.state] ?? undefined}
                label={formatDeploymentState(deployment.state)}
                color={getChipColor()}
                size="small"
                variant={isActive ? "filled" : "outlined"}
              />
            </Tooltip>
            {showPipelineInfo && (
              <Typography variant="body2" color="text.secondary">
                {pipelineName}
              </Typography>
            )}
          </Box>
        }
        secondary={
          <Typography
            variant="caption"
            component="span"
            sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}
          >
            Revision {deployment.revision_id} • {timeAgo}
          </Typography>
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
