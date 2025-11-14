import { FileCopy } from "@mui/icons-material"
import { CircularProgress, IconButton, Tooltip } from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type React from "react"
import {
  pipelinesDuplicatePipelineMutation,
  pipelinesReadPipelinesQueryKey,
} from "../../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../../stores"

interface DuplicatePipelineButtonProps {
  pipelineId: string
}

export const DuplicatePipelineButton: React.FC<
  DuplicatePipelineButtonProps
> = ({ pipelineId }) => {
  const queryClient = useQueryClient()
  const { setPipeline } = usePipelineStore()

  const duplicatePipelineMutation = useMutation({
    ...pipelinesDuplicatePipelineMutation(),
    onMutate: () => {},
    onSuccess: (newPipeline) => {
      // Invalidate the pipelines list to refresh
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      // Switch to the newly created duplicate pipeline
      setPipeline(newPipeline)
    },
    onError: () => {},
  })

  const handleDuplicateClick = () => {
    duplicatePipelineMutation.mutate({ path: { id: pipelineId } })
  }

  const isDuplicating = duplicatePipelineMutation.isPending

  return (
    <Tooltip title="Duplicate Pipeline">
      <span>
        <IconButton
          size="small"
          onClick={handleDuplicateClick}
          disabled={isDuplicating}
          color="inherit"
          sx={{ mr: 0.5 }}
        >
          {isDuplicating ? (
            <CircularProgress size={20} />
          ) : (
            <FileCopy fontSize="small" />
          )}
        </IconButton>
      </span>
    </Tooltip>
  )
}
