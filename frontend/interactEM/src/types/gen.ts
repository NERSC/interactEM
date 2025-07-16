/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export interface CanonicalEdge {
  input_id: string;
  output_id: string;
}
export interface CanonicalInput {
  id: string;
  node_type?: NodeType;
  port_type?: PortType;
  operator_id: string;
  portkey: string;
}
export interface CanonicalOperator {
  id: string;
  node_type?: NodeType;
  image: string;
  parameters?: OperatorSpecParameter[] | null;
  inputs?: string[];
  outputs?: string[];
  tags?: OperatorSpecTag[];
  parallel_config?: ParallelConfig | null;
}
export interface OperatorSpecParameter {
  name: string;
  label: string;
  description: string;
  type: ParameterSpecType;
  default: string;
  required: boolean;
  value?: string | null;
  options?: string[] | null;
}
export interface OperatorSpecTag {
  value: string;
  description?: string | null;
}
export interface ParallelConfig {
  type?: ParallelType;
}
export interface CanonicalOutput {
  id: string;
  node_type?: NodeType;
  port_type?: PortType;
  operator_id: string;
  portkey: string;
}
export interface CanonicalPipeline {
  id: string;
  revision_id: number;
  operators?: CanonicalOperator[];
  ports?: CanonicalPort[];
  edges?: CanonicalEdge[];
}
export interface CanonicalPort {
  id: string;
  node_type?: NodeType;
  port_type: PortType;
  operator_id: string;
  portkey: string;
}
export interface OperatorSpec {
  id: string;
  label: string;
  description: string;
  image: string;
  inputs?: OperatorSpecInput[] | null;
  outputs?: OperatorSpecOutput[] | null;
  parameters?: OperatorSpecParameter[] | null;
  tags?: OperatorSpecTag[] | null;
  parallel_config?: ParallelConfig | null;
}
export interface OperatorSpecInput {
  label: string;
  description: string;
}
export interface OperatorSpecOutput {
  label: string;
  description: string;
}
export interface RuntimeEdge {
  input_id: string;
  output_id: string;
}
export interface RuntimeOperator {
  id: string;
  node_type?: NodeType;
  image: string;
  parameters?: OperatorSpecParameter[] | null;
  inputs?: string[];
  outputs?: string[];
  tags?: OperatorSpecTag[];
  parallel_config?: ParallelConfig | null;
  canonical_id: string;
  uri?: OperatorURI | null;
  parallel_index?: number;
  env?: {
    [k: string]: string;
  };
  command?: string | string[];
  network_mode?: NetworkMode | null;
}
/**
 * Format: operator://agent-uuid/pipeline-uuid/revision-id/runtime-id/operator-uuid/parallel-index
 */
export interface OperatorURI {
  pipeline_id: string;
  revision_id: number;
  runtime_id: number;
  operator_id: string;
  parallel_index: number;
  agent_id: string;
  [k: string]: unknown;
}
export interface RuntimePipeline {
  id: string;
  revision_id: number;
  operators?: RuntimeOperator[];
  ports?: RuntimePort[];
  edges?: RuntimeEdge[];
  canonical_id: string;
  uri?: PipelineURI | null;
}
export interface RuntimePort {
  id: string;
  node_type?: NodeType;
  port_type: PortType;
  operator_id: string;
  portkey: string;
  canonical_id: string;
  canonical_operator_id: string;
  uri?: PortURI | null;
}
/**
 * Format: port://agent-uuid/pipeline-uuid/revision-id/runtime-id/operator-uuid/parallel-index/port-uuid
 */
export interface PortURI {
  pipeline_id: string;
  revision_id: number;
  runtime_id: number;
  operator_id: string;
  parallel_index: number;
  port_id: string;
  agent_id: string;
  [k: string]: unknown;
}
/**
 * Format: pipeline:///pipeline-uuid/revision-id/runtime-id
 */
export interface PipelineURI {
  pipeline_id: string;
  revision_id: number;
  runtime_id: number;
  [k: string]: unknown;
}

export enum ParameterSpecType {
  str = "str",
  int = "int",
  float = "float",
  bool = "bool",
  mount = "mount",
  "str-enum" = "str-enum"
}
export enum ParallelType {
  none = "none",
  embarrassing = "embarrassing"
}

export enum NetworkMode {
  bridge = "bridge",
  none = "none",
  container = "container",
  host = "host",
  ns = "ns"
}

export enum NodeType {
  operator = "operator",
  port = "port"
}

export enum PortType {
  input = "input",
  output = "output"
}
