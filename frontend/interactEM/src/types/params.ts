import { z } from "zod"
import type { OperatorSpecParameter } from "../client"
import type {
  ParameterSpecType,
  RuntimeOperatorParameter,
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

export type ParameterValue = NonNullable<RuntimeOperatorParameter["value"]>

export const parameterTypeSchemas: Record<
  ParameterSpecType,
  z.ZodType<ParameterValue>
> = {
  int: z.coerce
    .number({
      invalid_type_error: "Must be a number",
      required_error: "Value is required",
    })
    .int("Must be an integer"),
  float: z.coerce.number({
    invalid_type_error: "Must be a number",
    required_error: "Value is required",
  }),
  bool: z
    .union([
      z.boolean(),
      z.enum(["true", "false"]).transform((val) => val === "true"),
    ])
    .transform((val) => val as boolean),
  str: z.string(),
  "str-enum": z.string(),
  mount: z
    .string()
    .trim()
    .refine(
      (val) => val.startsWith("/") || val.startsWith("~/"),
      "Mount paths must start with / or ~/",
    )
    .refine(
      (val) => !val.split("/").includes(".."),
      "Mount paths cannot contain '..'",
    ),
}

export const getParameterSchema = (parameter: OperatorSpecParameter) => {
  let schema = parameterTypeSchemas[parameter.type]

  if (parameter.type === "str-enum" && parameter.options) {
    schema = z.enum(parameter.options as [string, ...string[]])
  }

  return schema as z.ZodType<ParameterValue>
}

export const stringifyParameterValue = (value: ParameterValue): string =>
  typeof value === "string" ? value : String(value)
