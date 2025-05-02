import type { Node } from "@xyflow/react"
import type { OperatorNodeData } from "../pipeline"
import type { Agent } from "./agent"

export enum NodeType {
  operator = "operator",
  table = "table",
  image = "image",
  agent = "agent",
}

export type OperatorNodeType = Node<OperatorNodeData, NodeType.operator>

export type ImageNodeType = Node<OperatorNodeData, NodeType.image>

export type TableNodeType = Node<OperatorNodeData, NodeType.table>

export type AgentNodeType = Node<Agent, NodeType.agent>

export type AnyNodeType =
  | OperatorNodeType
  | ImageNodeType
  | TableNodeType
  | AgentNodeType
export type OperatorNodeTypes = OperatorNodeType | ImageNodeType | TableNodeType
