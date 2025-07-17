import type { Node } from "@xyflow/react"
import type { Agent } from "./agent"
import type { OperatorNodeData } from "./pipeline"

export enum DisplayNodeType {
  operator = "operator",
  table = "table",
  image = "image",
  agent = "agent",
}

export type OperatorNodeType = Node<OperatorNodeData, DisplayNodeType.operator>

export type ImageNodeType = Node<OperatorNodeData, DisplayNodeType.image>

export type TableNodeType = Node<OperatorNodeData, DisplayNodeType.table>

export type AgentNodeType = Node<Agent, DisplayNodeType.agent>

export type AnyNodeType =
  | OperatorNodeType
  | ImageNodeType
  | TableNodeType
  | AgentNodeType
export type OperatorNodeTypes = OperatorNodeType | ImageNodeType | TableNodeType
