import type { Node } from "@xyflow/react"
import type { OperatorParameter } from "../client"
import type { Agent } from "./agent"

export enum NodeType {
  operator = "operator",
  image = "image",
  agent = "agent",
}

export type OperatorNodeType = Node<
  {
    label: string
    image: string
    inputs?: string[]
    outputs?: string[]
    parameters?: OperatorParameter[]
  },
  NodeType.operator
>

export type ImageNodeType = Node<
  {
    label: string
    image: string
    inputs?: string[]
    outputs?: string[]
    parameters?: OperatorParameter[]
  },
  NodeType.image
>

export type AgentNodeType = Node<Agent, NodeType.agent>

export type AnyNodeType = OperatorNodeType | ImageNodeType | AgentNodeType
export type OperatorNodeTypes = OperatorNodeType | ImageNodeType
