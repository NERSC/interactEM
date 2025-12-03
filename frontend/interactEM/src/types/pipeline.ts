import type { CanonicalOperator, CanonicalPipelineData } from "../client"

export type OperatorNodeData = Omit<CanonicalOperator, "id">
export interface PipelineJSON {
  data: CanonicalPipelineData
}
