import type { Node } from "@xyflow/react"
import type { OperatorNodeData } from "../pipeline"
import type { Agent } from "./agent"

export enum NodeType {
  operator = "operator",
  image = "image",
  agent = "agent",
}

export type OperatorNodeType = Node<OperatorNodeData, NodeType.operator>

export type ImageNodeType = Node<OperatorNodeData, NodeType.image>

export type AgentNodeType = Node<Agent, NodeType.agent>

export type AnyNodeType = OperatorNodeType | ImageNodeType | AgentNodeType
export type OperatorNodeTypes = OperatorNodeType | ImageNodeType
