import { useMemo } from "react"
import { BUCKET_STATUS, OPERATORS } from "../../constants/nats"
import type { OperatorVal } from "../../types/gen"
import { OperatorValSchema } from "../../types/operator"
import { useBucketWatch } from "./useBucketWatch"
import { useRunningPipelines } from "./useRunningPipelines"

export const useOperatorStatus = (operatorID: string) => {
  const { items: operatorVals, isLoading } = useBucketWatch<OperatorVal>({
    bucketName: `${BUCKET_STATUS}`,
    schema: OperatorValSchema,
    // TODO: come back when we revisit runtime pipelines in frontend
    keyFilter: `${OPERATORS}.>`,
    stripPrefix: OPERATORS,
  })

  const { pipelines } = useRunningPipelines()

  // Find the operator status that matches the canonical ID
  // TODO: come back when we revisit runtime pipelines in frontend
  const operatorStatus = useMemo(() => {
    return (
      operatorVals.find((status) => status.canonical_id === operatorID) || null
    )
  }, [operatorVals, operatorID])

  const pipelineId = operatorStatus?.runtime_pipeline_id || null
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
