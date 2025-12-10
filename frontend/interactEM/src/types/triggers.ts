import { z } from "zod"
import type { OperatorSpecTrigger } from "../client"

export type { OperatorSpecTrigger }

export const TriggerInvocationResponseSchema = z.object({
  status: z.enum(["ok", "error"]),
  message: z.string().nullable().optional(),
})
export type TriggerInvocationResponse = z.infer<
  typeof TriggerInvocationResponseSchema
>

export const TriggerInvocationRequestSchema = z.object({
  trigger: z.string(),
})
export type TriggerInvocationRequest = z.infer<
  typeof TriggerInvocationRequestSchema
>
