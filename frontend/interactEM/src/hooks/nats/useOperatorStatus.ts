import { useMemo } from "react"
import { OPERATORS_BUCKET } from "../../constants/nats"
import { type OperatorVal, OperatorValSchema } from "../../types/operator"
import { useBucketWatch } from "./useBucketWatch"
import { useRunningPipelines } from "./useRunningPipelines"

export const useOperatorStatus = (operatorID: string) => {
  const { items: operatorStatuses, isLoading } = useBucketWatch<OperatorVal>({
    bucketName: OPERATORS_BUCKET,
    schema: OperatorValSchema,
    keyFilter: operatorID,
  })

  const { pipelines } = useRunningPipelines()

  const operatorStatus = useMemo(() => {
    return operatorStatuses.length > 0 ? operatorStatuses[0] : null
  }, [operatorStatuses])

  const pipelineId = operatorStatus?.pipeline_id || null
  const status = operatorStatus?.status || null

  // Check if the operator is part of a running pipeline
  const isActiveInRunningPipeline =
    pipelineId !== null &&
    pipelines.some((pipeline) => pipeline.id === pipelineId)

  // Get effective status - only return a status if the operator is part of a running pipeline
  const effectiveStatus = isActiveInRunningPipeline ? status : null

  return {
    status: effectiveStatus,
    isLoading,
    pipelineId,
    rawStatus: status,
  }
}
