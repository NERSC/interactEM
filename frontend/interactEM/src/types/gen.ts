/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

/**
 * Enables discriminated unions for runtime operator params
 *
 * We want to be able to discriminate on 'type' field like in spec parameters.
 */
export type RuntimeOperatorParameter =
  | RuntimeOperatorParameterString
  | RuntimeOperatorParameterMount
  | RuntimeOperatorParameterInteger
  | RuntimeOperatorParameterFloat
  | RuntimeOperatorParameterBoolean
  | RuntimeOperatorParameterStrEnum
export type OperatorSpecTriggerField =
  | OperatorSpecTriggerFieldString
  | OperatorSpecTriggerFieldInteger
  | OperatorSpecTriggerFieldFloat
  | OperatorSpecTriggerFieldBoolean
  | OperatorSpecTriggerFieldStrEnum

export interface AgentLog {
  agent_id: string
  host: string
  log_type: LogType
  level: string
  log: string
  module: string
  timestamp: string
}
export interface AgentVal {
  error_messages?: ErrorMessage[]
  name?: string | null
  uri: URI
  status: AgentStatus
  status_message?: string | null
  tags?: string[]
  networks: string[]
  current_deployment_id?: string | null
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
export interface ExportParameterSpecType {
  type: ParameterSpecType
}
export interface ExportTriggerSpecType {
  type: TriggerSpecType
}
export interface OperatorLog {
  agent_id: string
  deployment_id: string
  operator_id: string
  host: string
  level: string
  log: string
  log_type: LogType
  module: string
  timestamp: string
}
export interface OperatorVal {
  error_messages?: ErrorMessage[]
  id: string
  canonical_id: string
  status: OperatorStatus
  canonical_pipeline_id: string
  runtime_pipeline_id: string
}
export interface PortVal {
  id: string
  canonical_id: string
  uri?: URI | null
  status?: PortStatus | null
}
export interface RuntimeEdge {
  input_id: string
  output_id: string
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
  triggers?: OperatorSpecTrigger[] | null
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
export interface RuntimeOperatorParameterString {
  name: string
  label: string
  description: string
  type: Type
  default: string
  required: boolean
  value?: string | null
  [k: string]: unknown
}
export interface RuntimeOperatorParameterMount {
  name: string
  label: string
  description: string
  type: Type1
  default: string
  required: boolean
  value?: string | null
  [k: string]: unknown
}
export interface RuntimeOperatorParameterInteger {
  name: string
  label: string
  description: string
  type: Type2
  default: number
  required: boolean
  value?: number | null
  [k: string]: unknown
}
export interface RuntimeOperatorParameterFloat {
  name: string
  label: string
  description: string
  type: Type3
  default: number
  required: boolean
  value?: number | null
  [k: string]: unknown
}
export interface RuntimeOperatorParameterBoolean {
  name: string
  label: string
  description: string
  type: Type4
  default: boolean
  required: boolean
  value?: boolean | null
  [k: string]: unknown
}
export interface RuntimeOperatorParameterStrEnum {
  name: string
  label: string
  description: string
  type: Type5
  default: string
  required: boolean
  options: string[]
  value?: string | null
  [k: string]: unknown
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
export interface OperatorSpecTrigger {
  name: string
  label: string
  description?: string | null
  mode?: TriggerInvocationMode
  fields?: OperatorSpecTriggerField[] | null
  [k: string]: unknown
}
export interface OperatorSpecTriggerFieldString {
  name: string
  label: string
  description: string
  type: Type6
  required?: boolean
  default?: string | null
  [k: string]: unknown
}
export interface OperatorSpecTriggerFieldInteger {
  name: string
  label: string
  description: string
  type: Type7
  required?: boolean
  default?: number | null
  [k: string]: unknown
}
export interface OperatorSpecTriggerFieldFloat {
  name: string
  label: string
  description: string
  type: Type8
  required?: boolean
  default?: number | null
  [k: string]: unknown
}
export interface OperatorSpecTriggerFieldBoolean {
  name: string
  label: string
  description: string
  type: Type9
  required?: boolean
  default?: boolean | null
  [k: string]: unknown
}
export interface OperatorSpecTriggerFieldStrEnum {
  name: string
  label: string
  description: string
  type: Type10
  required?: boolean
  default?: string | null
  options: string[]
  [k: string]: unknown
}
export interface RuntimeOperatorParameterAck {
  canonical_operator_id: string
  name: string
  type: ParameterSpecType
  value?: number | boolean | string | null
}
export interface RuntimeOperatorParameterUpdate {
  canonical_operator_id: string
  name: string
  type: ParameterSpecType
  value: number | boolean | string
}
export interface RuntimePipeline {
  operators?: RuntimeOperator[]
  ports?: RuntimePort[]
  edges?: RuntimeEdge[]
  id: string
  revision_id: number
  canonical_id: string
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
export interface TriggerInvocation {
  canonical_operator_id: string
  trigger: string
  payload?: {
    [k: string]: unknown
  }
}
export interface TriggerInvocationRequest {
  trigger: string
  payload?: {
    [k: string]: unknown
  } | null
}
export interface TriggerInvocationResponse {
  status: TriggerInvocationResponseStatus
  message?: string | null
}

export enum LogType {
  agent = "agent",
  operator = "operator",
  vector = "vector",
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
  cleaning_operators = "cleaning_operators",
  operators_starting = "operators_starting",
  running_deployment = "running_deployment",
  deployment_error = "deployment_error",
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
export enum TriggerSpecType {
  str = "str",
  int = "int",
  float = "float",
  bool = "bool",
  "str-enum" = "str-enum",
}
export enum OperatorStatus {
  initializing = "initializing",
  running = "running",
  error = "error",
  shutting_down = "shutting_down",
}
export enum PortStatus {
  initializing = "initializing",
  idle = "idle",
  busy = "busy",
}
export enum Type {
  str = "str",
}
export enum Type1 {
  mount = "mount",
}
export enum Type2 {
  int = "int",
}
export enum Type3 {
  float = "float",
}
export enum Type4 {
  bool = "bool",
}
export enum Type5 {
  "str-enum" = "str-enum",
}
export enum ParallelType {
  none = "none",
  embarrassing = "embarrassing",
}
export enum TriggerInvocationMode {
  single = "single",
  drain = "drain",
}
export enum Type6 {
  str = "str",
}
export enum Type7 {
  int = "int",
}
export enum Type8 {
  float = "float",
}
export enum Type9 {
  bool = "bool",
}
export enum Type10 {
  "str-enum" = "str-enum",
}
export enum NodeType {
  operator = "operator",
  port = "port",
}
export enum NetworkMode {
  bridge = "bridge",
  none = "none",
  container = "container",
  host = "host",
  ns = "ns",
}

export enum PortType {
  input = "input",
  output = "output",
}
export enum TriggerInvocationResponseStatus {
  ok = "ok",
  error = "error",
}
