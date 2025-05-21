import { Navigation } from "@mui/icons-material"
import { CircularProgress, IconButton, Tooltip } from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import type React from "react"
import { useState } from "react"
import { toast } from "react-toastify"
import { pipelinesRunPipelineMutation } from "../../client"
import { usePipelineStore } from "../../stores"

interface LaunchPipelineButtonProps {
  disabled?: boolean
}

export const LaunchPipelineButton: React.FC<LaunchPipelineButtonProps> = ({
  disabled = false,
}) => {
  const { currentPipelineId, currentRevisionId } = usePipelineStore()
  const [isLaunching, setIsLaunching] = useState(false)

  const launchPipeline = useMutation({
    ...pipelinesRunPipelineMutation(),
    onMutate: () => {
      setIsLaunching(true)
    },
    onSuccess: () => {
      toast.success("Pipeline sent to agents")
      setIsLaunching(false)
    },
    onError: () => {
      toast.error("Failed to launch pipeline")
      setIsLaunching(false)
    },
  })

  const handleLaunchClick = () => {
    if (!currentPipelineId || !currentRevisionId) {
      toast.error("No pipeline or revision selected")
      return
    }

    launchPipeline.mutate({
      path: { id: currentPipelineId, revision_id: currentRevisionId },
    })
  }

  return (
    <Tooltip title="Launch Pipeline">
      <span>
        <IconButton
          size="small"
          onClick={handleLaunchClick}
          disabled={
            disabled || isLaunching || !currentPipelineId || !currentRevisionId
          }
          color="primary"
          sx={{ mr: 0.5 }}
        >
          {isLaunching ? (
            <CircularProgress size={20} color="primary" />
          ) : (
            <Navigation fontSize="small" />
          )}
        </IconButton>
      </span>
    </Tooltip>
  )
}
