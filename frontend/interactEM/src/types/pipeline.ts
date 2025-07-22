import { z } from "zod"
import type { CanonicalOperator, CanonicalPipelineData } from "../client"

export type OperatorNodeData = Omit<CanonicalOperator, "id">

export interface PipelineJSON {
  data: CanonicalPipelineData
}

export const PipelineRunSchema = z.object({
  id: z.string().uuid(),
  revision_id: z.number().int(),
})

export type PipelineRun = z.infer<typeof PipelineRunSchema>
