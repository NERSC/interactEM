import type { OperatorParameter, OperatorTag } from "../client"
import type { NodeType } from "./nodes"

export interface PipelineWithID {
  id: string
  data: PipelineJSON["data"]
}

export type OperatorNodeData = {
  label: string
  image: string
  inputs?: string[]
  outputs?: string[]
  parameters?: OperatorParameter[]
  tags?: OperatorTag[]
  type: NodeType
}

export interface OperatorJSON extends OperatorNodeData {
  id: string

  [x: string | number | symbol]: unknown
}

export interface EdgeJSON {
  input_id: string
  output_id: string

  [x: string | number | symbol]: unknown
}

export type PortNodeType = "port"

export interface PortJSON {
  node_type: PortNodeType
  id: string
  operator_id: string
  portkey: string
  port_type: string

  [x: string | number | symbol]: unknown
}

export interface PipelineData {
  operators: OperatorJSON[]
  ports: PortJSON[]
  edges: EdgeJSON[]
}

export interface PipelineJSON {
  data: PipelineData
}
