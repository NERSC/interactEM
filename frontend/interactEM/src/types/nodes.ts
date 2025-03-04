import type { Node } from "@xyflow/react"
import type { OperatorParameter } from "../client"

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
export type OperatorNodeTypes = OperatorNodeType | ImageNodeType
