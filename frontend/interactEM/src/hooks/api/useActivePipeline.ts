import { useQuery } from "@tanstack/react-query"
import {
  pipelinesReadPipelineOptions,
  pipelinesReadPipelineRevisionOptions,
} from "../../client/generated/@tanstack/react-query.gen"
import { ViewMode, usePipelineStore, useViewModeStore } from "../../stores"
import { usePipelineStatus } from "../nats/useRunningPipelines"

function useComposerPipeline() {
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

function useRuntimePipeline() {
  const { selectedRuntimePipelineId } = usePipelineStore()

  // Get runtime pipeline data
  const { pipeline: runtimePipelineData } = usePipelineStatus(
    selectedRuntimePipelineId,
  )

  const canonicalId = runtimePipelineData?.pipeline.canonical_id
  const revisionId = runtimePipelineData?.pipeline.revision_id

  // Fetch canonical pipeline data based on runtime pipeline
  const pipelineQuery = useQuery({
    ...pipelinesReadPipelineOptions({ path: { id: canonicalId! } }),
    enabled: !!canonicalId,
  })

  const revisionQuery = useQuery({
    ...pipelinesReadPipelineRevisionOptions({
      path: { id: canonicalId!, revision_id: revisionId! },
    }),
    enabled: !!canonicalId && !!revisionId,
  })

  return {
    pipeline: pipelineQuery.data,
    revision: revisionQuery.data,
    runtimePipelineId: selectedRuntimePipelineId,
    isLoading: pipelineQuery.isLoading || revisionQuery.isLoading,
    error: pipelineQuery.error || revisionQuery.error,
  }
}

export function useActivePipeline() {
  const { viewMode } = useViewModeStore()

  const composerData = useComposerPipeline()
  const runtimeData = useRuntimePipeline()

  // Return the appropriate data based on view mode
  if (viewMode === ViewMode.Runtime) {
    return {
      ...runtimeData,
    }
  }

  return {
    ...composerData,
    runtimePipeline: null,
    runtimePipelineId: null,
  }
}
