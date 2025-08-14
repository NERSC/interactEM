import { useMemo } from "react"
import { usePipelineStatusContext } from "../../contexts/nats/pipelinestatus"

export const usePipelineStatus = (runtimeId: string | null) => {
  const { pipelines, pipelinesLoading, pipelinesError } =
    usePipelineStatusContext()

  const pipeline = useMemo(
    () =>
      runtimeId ? pipelines.find((p) => p.id === runtimeId) || null : null,
    [pipelines, runtimeId],
  )

  return {
    pipeline,
    isLoading: pipelinesLoading,
    error: pipelinesError,
  }
}
export const useAllPipelineStatuses = () => {
  const { pipelines, pipelinesLoading, pipelinesError } =
    usePipelineStatusContext()

  return {
    pipelines,
    isLoading: pipelinesLoading,
    error: pipelinesError,
  }
}
