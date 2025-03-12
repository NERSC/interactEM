import { type Edge, type Node, Position, type XYPosition } from "@xyflow/react"

import type { OperatorParameter, OperatorTag } from "../client"

import { edgeOptions } from "../components/pipelineflow"

const position: XYPosition = {
  x: 0,
  y: 0,
}

export type OperatorNodeData = {
  label: string
  image: string
  inputs?: string[]
  outputs?: string[]
  parameters?: OperatorParameter[]
  tags?: OperatorTag[]
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

type PortNodeType = "port"

export interface PortJSON {
  node_type: PortNodeType
  id: string
  operator_id: string
  portkey: string
  port_type: string

  [x: string | number | symbol]: unknown
}

interface PipelineData {
  operators: OperatorJSON[]
  ports: PortJSON[]
  edges: EdgeJSON[]
}

export interface PipelineJSON {
  data: PipelineData
}

export const fromPipelineJSON = (pipelineJSON: PipelineJSON) => {
  const pipelineNodes: Node<OperatorNodeData>[] = []
  const pipelineEdges: Edge[] = []
  const portByID: Map<string, PortJSON> = new Map()

  for (const port of pipelineJSON.data.ports) {
    portByID.set(port.id, port)
  }

  for (const operatorJSON of pipelineJSON.data.operators) {
    const node: Node<OperatorNodeData> = {
      id: operatorJSON.id,
      type: "operator",
      position,
      data: {
        label: operatorJSON.label ?? operatorJSON.image,
        image: operatorJSON.image,
        inputs: operatorJSON.inputs,
        outputs: operatorJSON.outputs,
        tags: operatorJSON.tags,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      handles: [],
    }

    pipelineNodes.push(node)
  }

  for (const edge of pipelineJSON.data.edges) {
    const inputPort = portByID.get(edge.input_id)
    const outputPort = portByID.get(edge.output_id)

    if (inputPort === undefined || outputPort === undefined) {
      continue
    }

    pipelineEdges.push({
      id: `${edge.input_id}->${edge.output_id}`,
      source: inputPort.operator_id,
      target: outputPort.operator_id,
      sourceHandle: edge.input_id,
      targetHandle: edge.output_id,
      ...edgeOptions,
    })
  }

  return { nodes: pipelineNodes, edges: pipelineEdges }
}

export const toJSON = (nodes: Node<OperatorNodeData>[], edges: Edge[]) => {
  const operatorsJSON: OperatorJSON[] = []
  const portsJSON: PortJSON[] = []
  const edgesJSON: EdgeJSON[] = []
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

      const port: PortJSON = {
        node_type: "port",
        id: portID,
        operator_id: node.id,
        portkey: portID,
        port_type: "input",
      }
      portsJSON.push(port)
    }

    for (const portID of outputs ?? []) {
      if (portIDs.has(portID)) {
        continue
      }
      portIDs.add(portID)

      const port: PortJSON = {
        node_type: "port",
        id: portID,
        operator_id: node.id,
        portkey: portID,
        port_type: "output",
      }
      portsJSON.push(port)
    }

    // Operators
    const op: OperatorJSON = {
      id: node.id,
      label: data.label,
      image: node.data.image,
      inputs: inputs,
      outputs: outputs,
      parameters: parameters,
      tags: tags,
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
      num_connections: 1,
    })
  }

  return {
    data: {
      operators: operatorsJSON,
      ports: portsJSON,
      edges: edgesJSON,
    },
  }
}
