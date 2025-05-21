import { z } from "zod"

const OperatorStatusEnum = z.enum(["initializing", "running", "shutting_down"])

export type OperatorStatus = z.infer<typeof OperatorStatusEnum>

export const OperatorValSchema = z.object({
  id: z.string().uuid(),
  status: OperatorStatusEnum,
  pipeline_id: z.string().uuid().nullable(),
})

export type OperatorVal = z.infer<typeof OperatorValSchema>
