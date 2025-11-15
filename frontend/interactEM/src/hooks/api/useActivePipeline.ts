import { useQuery } from "@tanstack/react-query"
import {
  pipelinesReadPipelineOptions,
  pipelinesReadPipelineRevisionOptions,
} from "../../client/generated/@tanstack/react-query.gen"
import { ViewMode, usePipelineStore, useViewModeStore } from "../../stores"
import { useDeployment } from "./useDeploymentsQuery"

function useComposerPipeline() {
  const { currentPipelineId, currentRevisionId } = usePipelineStore()

  const pipelineQuery = useQuery({
    ...pipelinesReadPipelineOptions({ path: { id: currentPipelineId! } }),
    enabled: !!currentPipelineId,
  })

  const revisionId =
    currentRevisionId != null
      ? currentRevisionId
      : (pipelineQuery.data?.current_revision_id ?? null)

  const revisionQuery = useQuery({
    ...pipelinesReadPipelineRevisionOptions({
      path: { id: currentPipelineId!, revision_id: revisionId! },
    }),
    enabled: !!currentPipelineId && revisionId != null,
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

  // Get deployment data to extract pipeline_id and revision_id
  const { data: deployment, isLoading: deploymentLoading } = useDeployment(
    selectedRuntimePipelineId,
  )

  const canonicalId = deployment?.pipeline_id
  const revisionId = deployment?.revision_id

  // Fetch canonical pipeline data based on deployment
  const pipelineQuery = useQuery({
    ...pipelinesReadPipelineOptions({ path: { id: canonicalId! } }),
    enabled: !!canonicalId && !deploymentLoading,
  })

  const revisionQuery = useQuery({
    ...pipelinesReadPipelineRevisionOptions({
      path: { id: canonicalId!, revision_id: revisionId! },
    }),
    enabled: !!canonicalId && revisionId != null && !deploymentLoading,
  })

  return {
    pipeline: pipelineQuery.data,
    revision: revisionQuery.data,
    runtimePipelineId: selectedRuntimePipelineId,
    isLoading:
      deploymentLoading || pipelineQuery.isLoading || revisionQuery.isLoading,
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
