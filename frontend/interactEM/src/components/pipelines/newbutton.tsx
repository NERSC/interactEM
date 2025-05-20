import { Add as AddIcon } from "@mui/icons-material"
import { IconButton, Tooltip } from "@mui/material"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "react-toastify"
import type { PipelineCreate } from "../../client"
import {
  pipelinesCreatePipelineMutation,
  pipelinesReadPipelinesQueryKey,
} from "../../client"
import { usePipelineStore } from "../../stores"

interface NewPipelineButtonProps {
  size?: "small" | "medium" | "large"
}

export const NewPipelineButton: React.FC<NewPipelineButtonProps> = ({
  size = "small",
}) => {
  const queryClient = useQueryClient()
  const { setPipeline } = usePipelineStore()

  const createPipeline = useMutation({
    ...pipelinesCreatePipelineMutation(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      setPipeline(data)
    },
    onError: (error) => {
      console.error("Failed to create pipeline:", error)
      toast.error("Failed to create pipeline. Please try again.")
    },
  })

  const handleCreateNewPipeline = () => {
    const p: PipelineCreate = {
      data: {
        operators: [],
        ports: [],
        edges: [],
      },
    }
    createPipeline.mutate({
      body: p,
    })
  }

  return (
    <Tooltip title="New Pipeline">
      <IconButton
        size={size}
        onClick={handleCreateNewPipeline}
        disabled={createPipeline.isPending}
        aria-label="Create new pipeline"
      >
        <AddIcon />
      </IconButton>
    </Tooltip>
  )
}
