import { type Edge, type Node, Position, type XYPosition } from "@xyflow/react"
import { edgeOptions } from "../components/composerpipelineflow"
import type {
  EdgeJSON,
  OperatorJSON,
  OperatorNodeData,
  PipelineJSON,
  PortJSON,
} from "../types/pipeline"

const position: XYPosition = {
  x: 0,
  y: 0,
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
      type: operatorJSON.type,
      position,
      data: {
        label: operatorJSON.label ?? operatorJSON.image,
        image: operatorJSON.image,
        inputs: operatorJSON.inputs,
        outputs: operatorJSON.outputs,
        tags: operatorJSON.tags,
        type: operatorJSON.type,
        parameters: operatorJSON.parameters,
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
      type: node.data.type,
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
