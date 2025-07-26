import { z } from "zod"
import type {
  RuntimeOperatorParameterAck,
  RuntimeOperatorParameterUpdate,
} from "./gen"

export const RuntimeOperatorParameterUpdateSchema = z.object({
  canonical_operator_id: z.string(),
  name: z.string(),
  value: z.string(),
}) satisfies z.ZodType<RuntimeOperatorParameterUpdate>

export const RuntimeOperatorParameterAckSchema = z.object({
  canonical_operator_id: z.string(),
  name: z.string(),
  value: z.string().nullable().optional(),
}) satisfies z.ZodType<RuntimeOperatorParameterAck>
