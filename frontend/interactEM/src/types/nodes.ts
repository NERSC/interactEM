import type { Node } from "@xyflow/react"
import type { AgentValType } from "./agent"
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

export type AgentNodeType = Node<AgentValType, DisplayNodeType.agent>

export type AnyNodeType =
  | OperatorNodeType
  | ImageNodeType
  | TableNodeType
  | AgentNodeType

export type OperatorNodeTypes = OperatorNodeType | ImageNodeType | TableNodeType

export type OperatorDisplayNodeTypes =
  | DisplayNodeType.operator
  | DisplayNodeType.image
  | DisplayNodeType.table

export const LABEL_TO_NODETYPE_MAP: {
  [key: string]: DisplayNodeType.image | DisplayNodeType.table
} = {
  Image: DisplayNodeType.image,
  Table: DisplayNodeType.table,
}

export function displayNodeTypeFromLabel(
  label: string,
): OperatorDisplayNodeTypes {
  return LABEL_TO_NODETYPE_MAP[label] || DisplayNodeType.operator
}

const IMAGE_NODETYPE_IMAGE = "ghcr.io/nersc/interactem/image-display:latest"
const TABLE_NODETYPE_IMAGE = "ghcr.io/nersc/interactem/table-display:latest"

export const IMAGE_TO_NODETYPE_MAP: {
  [key: string]:
    | DisplayNodeType.image
    | DisplayNodeType.table
    | DisplayNodeType.operator
} = {
  [IMAGE_NODETYPE_IMAGE]: DisplayNodeType.image,
  [TABLE_NODETYPE_IMAGE]: DisplayNodeType.table,
}

export function displayNodeTypeFromImage(
  imageType: string,
): OperatorDisplayNodeTypes {
  return IMAGE_TO_NODETYPE_MAP[imageType] || DisplayNodeType.operator
}
