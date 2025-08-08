/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export interface AgentVal {
  error_messages?: ErrorMessage[]
  name?: string | null
  uri: URI
  status: AgentStatus
  status_message?: string | null
  tags?: string[]
  networks: string[]
  pipeline_id?: string | null
  operator_assignments?: string[] | null
  uptime?: number
}
export interface ErrorMessage {
  message: string
  timestamp?: number
  [k: string]: unknown
}
export interface URI {
  id: string
  location: URILocation
  hostname: string
  comm_backend: CommBackend
  query?: {
    [k: string]: string[]
  }
  [k: string]: unknown
}
export interface OperatorVal {
  error_messages?: ErrorMessage[]
  id: string
  canonical_id: string
  status: OperatorStatus
  canonical_pipeline_id: string
  runtime_pipeline_id: string
}
export interface PipelineDeploymentEvent {
  type?: PipelineEventType
  canonical_id: string
  revision_id: number
  deployment_id: string
  data: {
    [k: string]: unknown
  }
}
export interface PipelineRunVal {
  id: string
  pipeline: RuntimePipeline
}
export interface RuntimePipeline {
  operators?: RuntimeOperator[]
  ports?: RuntimePort[]
  edges?: RuntimeEdge[]
  id: string
  revision_id: number
  canonical_id: string
}
export interface RuntimeOperator {
  id: string
  label: string
  description: string
  image: string
  inputs?: RuntimePortMap[]
  outputs?: RuntimePortMap[]
  parameters?: RuntimeOperatorParameter[] | null
  tags?: OperatorSpecTag[]
  parallel_config?: ParallelConfig | null
  spec_id: string
  node_type?: NodeType
  canonical_id: string
  parallel_index?: number
  env?: {
    [k: string]: string
  }
  command?: string | string[]
  network_mode?: NetworkMode | null
}
export interface RuntimePortMap {
  id: string
  canonical_id: string
  [k: string]: unknown
}
export interface RuntimeOperatorParameter {
  name: string
  label: string
  description: string
  type: ParameterSpecType
  default: string
  required: boolean
  options?: string[] | null
  value?: string | null
}
export interface OperatorSpecTag {
  value: string
  description?: string | null
  [k: string]: unknown
}
export interface ParallelConfig {
  type?: ParallelType
  [k: string]: unknown
}
export interface RuntimePort {
  id: string
  node_type?: NodeType
  port_type: PortType
  canonical_operator_id: string
  portkey: string
  canonical_id: string
  operator_id: string
  targets_canonical_operator_id?: string | null
}
export interface RuntimeEdge {
  input_id: string
  output_id: string
}
export interface PipelineStopEvent {
  type?: PipelineEventType
  deployment_id: string
}
export interface PortVal {
  id: string
  canonical_id: string
  uri?: URI | null
  status?: PortStatus | null
}
export interface RuntimeOperatorParameterAck {
  canonical_operator_id: string
  name: string
  value?: string | null
}
export interface RuntimeOperatorParameterUpdate {
  canonical_operator_id: string
  name: string
  value: string
}

export enum URILocation {
  operator = "operator",
  port = "port",
  agent = "agent",
  orchestrator = "orchestrator",
}
export enum CommBackend {
  zmq = "zmq",
  mpi = "mpi",
  nats = "nats",
}
export enum AgentStatus {
  initializing = "initializing",
  idle = "idle",
  busy = "busy",
  error = "error",
  shutting_down = "shutting_down",
}
export enum OperatorStatus {
  initializing = "initializing",
  running = "running",
  error = "error",
  shutting_down = "shutting_down",
}

export enum ParameterSpecType {
  str = "str",
  int = "int",
  float = "float",
  bool = "bool",
  mount = "mount",
  "str-enum" = "str-enum",
}
export enum ParallelType {
  none = "none",
  embarrassing = "embarrassing",
}

export enum NetworkMode {
  bridge = "bridge",
  none = "none",
  container = "container",
  host = "host",
  ns = "ns",
}

export enum PortStatus {
  initializing = "initializing",
  idle = "idle",
  busy = "busy",
}

export enum NodeType {
  operator = "operator",
  port = "port",
}

export enum PortType {
  input = "input",
  output = "output",
}

export enum PipelineEventType {
  pipeline_run = "pipeline_run",
  pipeline_stop = "pipeline_stop",
  pipeline_update = "pipeline_update",
}
