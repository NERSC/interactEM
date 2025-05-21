import { Stop } from "@mui/icons-material"
import { CircularProgress, IconButton, Tooltip } from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import type React from "react"
import { toast } from "react-toastify"
import { pipelinesStopPipelineMutation } from "../../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../../stores"

interface StopPipelineButtonProps {
  disabled?: boolean
}

export const StopPipelineButton: React.FC<StopPipelineButtonProps> = ({
  disabled = false,
}) => {
  const { currentPipelineId, currentRevisionId } = usePipelineStore()

  const stopPipeline = useMutation({
    ...pipelinesStopPipelineMutation(),
    onSuccess: (data) => {
      toast.success(data.message)
    },
    onError: (data) => {
      toast.error(data.message)
    },
  })

  const handleStopClick = () => {
    if (!currentPipelineId || !currentRevisionId) {
      toast.error("No pipeline or revision selected")
      return
    }

    stopPipeline.mutate({
      path: { id: currentPipelineId, revision_id: currentRevisionId },
    })
  }

  return (
    <Tooltip title="Stop Pipeline">
      <span>
        <IconButton
          size="small"
          onClick={handleStopClick}
          disabled={
            disabled ||
            stopPipeline.isPending ||
            !currentPipelineId ||
            !currentRevisionId
          }
          color="error"
          sx={{ mr: 0.5 }}
        >
          {stopPipeline.isPending ? (
            <CircularProgress size={20} color="error" />
          ) : (
            <Stop fontSize="small" />
          )}
        </IconButton>
      </span>
    </Tooltip>
  )
}
