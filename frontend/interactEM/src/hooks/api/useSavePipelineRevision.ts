import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { Edge } from "@xyflow/react"
import {
  pipelinesAddPipelineRevisionMutation,
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
} from "../../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../../stores"
import type { OperatorNodeTypes } from "../../types/nodes"
import { toJSON } from "../../utils/pipeline"

export const useSavePipelineRevision = () => {
  const queryClient = useQueryClient()
  const { currentPipelineId, setPipelineRevision } = usePipelineStore()

  const mutation = useMutation({
    ...pipelinesAddPipelineRevisionMutation(),
    onSuccess: (data) => {
      setPipelineRevision(data)
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      if (currentPipelineId) {
        queryClient.invalidateQueries({
          queryKey: pipelinesReadPipelineQueryKey({
            path: { id: currentPipelineId },
          }),
        })
        queryClient.invalidateQueries({
          queryKey: pipelinesListPipelineRevisionsQueryKey({
            path: { id: currentPipelineId },
          }),
        })
      }
    },
  })

  const saveRevision = (nodes: OperatorNodeTypes[], edges: Edge[]) => {
    if (!currentPipelineId) return
    const pipelineJson = toJSON(nodes, edges)
    mutation.mutate({
      path: { id: currentPipelineId },
      body: { data: pipelineJson },
    })
  }

  return { saveRevision, ...mutation }
}
