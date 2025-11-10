import { z } from "zod"
import type { CanonicalOperator, CanonicalPipelineData } from "../client"
import type {
  OperatorSpecTag,
  ParallelConfig,
  RuntimeEdge,
  RuntimeOperator,
  RuntimeOperatorParameter,
  RuntimePipeline,
  RuntimePort,
  RuntimePortMap,
} from "./gen"
import {
  NetworkMode,
  NodeType,
  ParallelType,
  ParameterSpecType,
  PortType,
} from "./gen"

export type OperatorNodeData = Omit<CanonicalOperator, "id">
export interface PipelineJSON {
  data: CanonicalPipelineData
}

export const OperatorSpecTagSchema = z.object({
  value: z.string(),
  description: z.string().nullable().optional(),
}) satisfies z.ZodType<OperatorSpecTag>

export const ParallelConfigSchema = z.object({
  type: z.nativeEnum(ParallelType).optional(),
}) satisfies z.ZodType<ParallelConfig>

export const RuntimeOperatorParameterSchema = z.object({
  name: z.string(),
  label: z.string(),
  description: z.string(),
  type: z.nativeEnum(ParameterSpecType),
  default: z.string(),
  required: z.boolean(),
  options: z.array(z.string()).nullable().optional(),
  value: z.string().nullable().optional(),
}) satisfies z.ZodType<RuntimeOperatorParameter>

export const RuntimePortMapSchema = z.object({
  id: z.string().uuid(),
  canonical_id: z.string().uuid(),
}) satisfies z.ZodType<RuntimePortMap>

export const RuntimeOperatorSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string(),
  image: z.string(),
  inputs: z.array(RuntimePortMapSchema).optional(),
  outputs: z.array(RuntimePortMapSchema).optional(),
  parameters: z.array(RuntimeOperatorParameterSchema).nullable().optional(),
  tags: z.array(OperatorSpecTagSchema).optional(),
  parallel_config: ParallelConfigSchema.nullable().optional(),
  spec_id: z.string().uuid(),
  node_type: z.nativeEnum(NodeType).optional(),
  canonical_id: z.string().uuid(),
  parallel_index: z.number().optional(),
  env: z.record(z.string()).optional(),
  command: z.union([z.string(), z.array(z.string())]).optional(),
  network_mode: z.nativeEnum(NetworkMode).nullable().optional(),
}) satisfies z.ZodType<RuntimeOperator>

export const RuntimePortSchema = z.object({
  id: z.string().uuid(),
  node_type: z.nativeEnum(NodeType).optional(),
  port_type: z.nativeEnum(PortType),
  canonical_operator_id: z.string().uuid(),
  portkey: z.string().uuid(),
  canonical_id: z.string().uuid(),
  operator_id: z.string().uuid(),
  targets_canonical_operator_id: z.string().uuid().nullable().optional(),
}) satisfies z.ZodType<RuntimePort>

export const RuntimeEdgeSchema = z.object({
  input_id: z.string().uuid(),
  output_id: z.string().uuid(),
}) satisfies z.ZodType<RuntimeEdge>

export const RuntimePipelineSchema = z.object({
  operators: z.array(RuntimeOperatorSchema).optional(),
  ports: z.array(RuntimePortSchema).optional(),
  edges: z.array(RuntimeEdgeSchema).optional(),
  id: z.string().uuid(),
  revision_id: z.number(),
  canonical_id: z.string(),
}) satisfies z.ZodType<RuntimePipeline>
