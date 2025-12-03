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
  type: z.string() as z.ZodType<ParameterSpecType>,
  value: z.union([z.number(), z.boolean(), z.string()]),
}) satisfies z.ZodType<RuntimeOperatorParameterUpdate>

export const RuntimeOperatorParameterAckSchema = z.object({
  canonical_operator_id: z.string(),
  name: z.string(),
  type: z.string() as z.ZodType<ParameterSpecType>,
  value: z.union([z.number(), z.boolean(), z.string()]).nullable().optional(),
}) satisfies z.ZodType<RuntimeOperatorParameterAck>

const mountPathRegex = /^(\/|~\/)(?!.*(?:^|\/)\.\.(?:\/|$)).*$/

/**
 * Input validation schemas for form fields (string inputs)
 * These validate the raw string values from form inputs
 */
const parameterInputSchemas: Record<ParameterSpecType, z.ZodTypeAny> = {
  int: z.string().pipe(z.coerce.number().int("Must be an integer")),
  float: z.string().pipe(z.coerce.number()),
  bool: z.enum(["true", "false"]).transform((val) => val === "true"),
  str: z.string(),
  "str-enum": z.string(),
  mount: z.string().regex(mountPathRegex, "Invalid file path"),
}

/**
 * Get the validation schema for a parameter's string input
 * Handles enum validation for str-enum types
 */
export const getParameterInputSchema = (parameter: OperatorSpecParameter) => {
  let schema = parameterInputSchemas[parameter.type]

  if (parameter.type === "str-enum" && parameter.options) {
    schema = z.enum(parameter.options as [string, ...string[]])
  }

  return schema
}

/**
 * Validate a string input and return the parsed native value
 * Returns undefined if validation fails
 */
export const getParameterNativeValue = (
  parameter: OperatorSpecParameter,
  stringValue: string,
): number | boolean | string | undefined => {
  const schema = getParameterInputSchema(parameter)
  const result = schema.safeParse(stringValue)

  if (!result.success) {
    return undefined
  }

  return result.data
}
