import { useQuery } from "@tanstack/react-query"
import {
  pipelinesReadPipelineOptions,
  pipelinesReadPipelineRevisionOptions,
} from "../client/generated/@tanstack/react-query.gen"
import { usePipelineStore } from "../stores"

export function useActivePipeline() {
  const { currentPipelineId, currentRevisionId } = usePipelineStore()

  const pipelineQuery = useQuery({
    ...pipelinesReadPipelineOptions({ path: { id: currentPipelineId! } }),
    enabled: !!currentPipelineId,
  })

  const revisionId =
    currentRevisionId || pipelineQuery.data?.current_revision_id || null

  const revisionQuery = useQuery({
    ...pipelinesReadPipelineRevisionOptions({
      path: { id: currentPipelineId!, revision_id: revisionId! },
    }),
    enabled: !!currentPipelineId && !!revisionId,
  })

  return {
    pipeline: pipelineQuery.data,
    revision: revisionQuery.data,
    isLoading: pipelineQuery.isLoading || revisionQuery.isLoading,
    error: pipelineQuery.error || revisionQuery.error,
  }
}
