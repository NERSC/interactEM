import { z } from "zod"
import type { OperatorSpecParameter } from "../client"
import type {
  ParameterSpecType,
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

const mountPathRegex = /^(\/|~\/)(?!.*(?:^|\/)\.\.(?:\/|$)).*$/

export const parameterTypeSchemas: Record<ParameterSpecType, z.ZodTypeAny> = {
  int: z
    .string()
    .regex(/^-?\d+$/, "Must be an integer")
    .transform((val) => Number.parseInt(val, 10)),
  float: z
    .string()
    .regex(/^-?\d+(\.\d+)?$/, "Must be a float")
    .transform((val) => Number.parseFloat(val)),
  bool: z.enum(["true", "false"]),
  str: z.string(),
  "str-enum": z.string(),
  mount: z.string().regex(mountPathRegex, "Invalid file path"),
}

export const getParameterSchema = (parameter: OperatorSpecParameter) => {
  let schema = parameterTypeSchemas[parameter.type]

  if (parameter.type === "str-enum" && parameter.options) {
    schema = z.enum(parameter.options as [string, ...string[]])
  }

  return schema
}
