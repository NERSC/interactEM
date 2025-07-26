import { z } from "zod"
import { OperatorStatus } from "./gen"
import type { OperatorVal } from "./gen"

export const OperatorStatusSchema = z.nativeEnum(OperatorStatus)

export const OperatorValSchema = z.object({
  id: z.string().uuid(),
  canonical_id: z.string().uuid(),
  canonical_pipeline_id: z.string().uuid(),
  runtime_pipeline_id: z.string().uuid(),
  status: OperatorStatusSchema,
}) satisfies z.ZodType<OperatorVal>
