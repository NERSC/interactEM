import { Stop } from "@mui/icons-material"
import { CircularProgress, IconButton, Tooltip } from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type React from "react"
import { toast } from "react-toastify"
import {
  deploymentsListPipelineDeploymentsQueryKey,
  deploymentsUpdatePipelineDeploymentMutation,
  pipelinesListPipelineDeploymentsQueryKey,
} from "../../client/generated/@tanstack/react-query.gen"

interface StopPipelineButtonProps {
  deploymentId: string
  disabled?: boolean
}

export const StopPipelineButton: React.FC<StopPipelineButtonProps> = ({
  disabled = false,
  deploymentId,
}) => {
  const queryClient = useQueryClient()

  const cancelDeployment = useMutation({
    ...deploymentsUpdatePipelineDeploymentMutation(),
    onSuccess: (data) => {
      // Invalidate all deployment queries
      queryClient.invalidateQueries({
        queryKey: deploymentsListPipelineDeploymentsQueryKey({}),
      })

      // Use the pipeline_id from the response to invalidate pipeline-specific queries
      queryClient.invalidateQueries({
        queryKey: pipelinesListPipelineDeploymentsQueryKey({
          path: { id: data.pipeline_id },
        }),
      })

      toast.success("Pipeline deployment cancelled")
    },
    onError: () => {
      toast.error("Failed to cancel pipeline deployment")
    },
  })

  const handleStopClick = () => {
    cancelDeployment.mutate({
      path: { id: deploymentId },
      body: { state: "cancelled" },
    })
  }

  return (
    <Tooltip title="Stop Pipeline">
      <span>
        <IconButton
          size="small"
          onClick={handleStopClick}
          disabled={disabled || cancelDeployment.isPending}
          color="error"
          sx={{ mr: 0.5 }}
        >
          {cancelDeployment.isPending ? (
            <CircularProgress size={20} color="error" />
          ) : (
            <Stop fontSize="small" />
          )}
        </IconButton>
      </span>
    </Tooltip>
  )
}
