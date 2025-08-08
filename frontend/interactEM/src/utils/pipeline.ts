import { type Edge, Position, type XYPosition } from "@xyflow/react"
import type { CanonicalEdge, CanonicalOperator, CanonicalPort } from "../client"
import { zCanonicalPipelineData } from "../client/generated/zod.gen"
import { edgeOptions } from "../components/composerpipelineflow"
import type { ViewMode } from "../stores"
import { NodeType, PortType } from "../types/gen"
import {
  DisplayNodeType,
  type OperatorNodeTypes,
  displayNodeTypeFromImage,
} from "../types/nodes"
import type { PipelineJSON } from "../types/pipeline"

const position: XYPosition = {
  x: 0,
  y: 0,
}

export const fromPipelineJSON = (
  pipelineJSON: PipelineJSON,
  viewMode: ViewMode,
) => {
  const pipelineNodes: OperatorNodeTypes[] = []
  const pipelineEdges: Edge[] = []
  const portByID: Map<string, CanonicalPort> = new Map()

  for (const port of pipelineJSON.data.ports ?? []) {
    portByID.set(port.id, port)
  }

  for (const operatorJSON of pipelineJSON.data.operators ?? []) {
    let displayType = DisplayNodeType.operator
    if (viewMode === "runtime") {
      displayType = displayNodeTypeFromImage(operatorJSON.image)
    }
    const node: OperatorNodeTypes = {
      id: operatorJSON.id,
      type: displayType,
      position,
      data: {
        label: operatorJSON.label,
        description: operatorJSON.description,
        image: operatorJSON.image,
        inputs: operatorJSON.inputs,
        outputs: operatorJSON.outputs,
        parameters: operatorJSON.parameters,
        tags: operatorJSON.tags,
        parallel_config: operatorJSON.parallel_config,
        spec_id: operatorJSON.spec_id,
        node_type: NodeType.operator,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      handles: [],
    }

    pipelineNodes.push(node)
  }

  for (const edge of pipelineJSON.data.edges ?? []) {
    const inputPort = portByID.get(edge.input_id)
    const outputPort = portByID.get(edge.output_id)

    if (inputPort === undefined || outputPort === undefined) {
      continue
    }

    pipelineEdges.push({
      id: `${edge.input_id}->${edge.output_id}`,
      source: inputPort.canonical_operator_id,
      target: outputPort.canonical_operator_id,
      sourceHandle: edge.input_id,
      targetHandle: edge.output_id,
      ...edgeOptions,
    })
  }

  return { nodes: pipelineNodes, edges: pipelineEdges }
}

export const toJSON = (nodes: OperatorNodeTypes[], edges: Edge[]) => {
  const operatorsJSON: CanonicalOperator[] = []
  const portsJSON: CanonicalPort[] = []
  const edgesJSON: CanonicalEdge[] = []
  const portIDs: Set<string> = new Set<string>()

  // Generate the ports and operators
  for (const node of nodes) {
    const data = node.data
    const inputs = data.inputs
    const outputs = data.outputs
    const parameters = data.parameters
    const tags = data.tags

    // Ports
    for (const portID of inputs ?? []) {
      if (portIDs.has(portID)) {
        continue
      }
      portIDs.add(portID)

      const port: CanonicalPort = {
        id: portID,
        node_type: NodeType.port,
        canonical_operator_id: node.id,
        portkey: portID,
        port_type: PortType.input,
      }
      portsJSON.push(port)
    }

    for (const portID of outputs ?? []) {
      if (portIDs.has(portID)) {
        continue
      }
      portIDs.add(portID)

      const port: CanonicalPort = {
        id: portID,
        node_type: NodeType.port,
        canonical_operator_id: node.id,
        portkey: portID,
        port_type: PortType.output,
      }
      portsJSON.push(port)
    }

    // Operators
    const op: CanonicalOperator = {
      id: node.id,
      label: data.label,
      description: data.description,
      spec_id: data.spec_id,
      image: node.data.image,
      inputs: inputs,
      outputs: outputs,
      parameters: parameters,
      tags: tags,
      parallel_config: data.parallel_config,
    }
    operatorsJSON.push(op)
  }

  // Generate the edges
  for (const edge of edges) {
    if (edge.sourceHandle == null) {
      continue
    }

    if (edge.targetHandle == null) {
      continue
    }

    edgesJSON.push({
      input_id: edge.sourceHandle,
      output_id: edge.targetHandle,
    })
  }

  return zCanonicalPipelineData.parse({
    operators: operatorsJSON,
    ports: portsJSON,
    edges: edgesJSON,
  })
}
