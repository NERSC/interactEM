import { z } from "zod"
import type { CanonicalOperator, CanonicalPipelineData } from "../client"
import type { PipelineRunVal } from "./gen"
export type OperatorNodeData = Omit<CanonicalOperator, "id">

export interface PipelineJSON {
  data: CanonicalPipelineData
}

export const PipelineRunValSchema = z.object({
  id: z.string().uuid(),
  canonical_id: z.string().uuid(),
  canonical_revision_id: z.number().int(),
}) satisfies z.ZodType<PipelineRunVal>
