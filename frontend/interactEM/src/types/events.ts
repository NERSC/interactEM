import { type ZodType, z } from "zod"
import {
  type OperatorErrorEvent,
  OperatorErrorType,
  OperatorEventType,
} from "./gen"

export const zOperatorEventType = z.nativeEnum(OperatorEventType)

export const zOperatorErrorType = z.nativeEnum(OperatorErrorType)

export const OperatorErrorEventSchema = z.object({
  type: zOperatorEventType.default(OperatorEventType.error).optional(),
  operator_id: z.string().uuid(),
  error_type: zOperatorErrorType,
  message: z.string().optional().nullable(),
}) satisfies ZodType<OperatorErrorEvent>
