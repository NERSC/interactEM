import {
  Controls,
  type Edge,
  type EdgeChange,
  type KeyCode,
  type NodeChange,
  ReactFlow,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useAgents } from "../hooks/useAgents"
import { usePipelines } from "../hooks/usePipelines"
import { layoutNodes } from "../layout"
import { fromPipelineJSON } from "../pipeline"
import {
  type AgentNodeType,
  type ImageNodeType,
  NodeType,
  type OperatorNodeType,
} from "../types/nodes"
import AgentNode from "./agentnode"
import ImageNode from "./imagenode"
import OperatorNode from "./operatornode"

type ViewerNode = AgentNodeType | OperatorNodeType | ImageNodeType

const ViewerPipelineFlow = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { agents } = useAgents()
  const { pipelines } = usePipelines()
  const [nodes, setNodes] = useState<ViewerNode[]>([])
  const [edges, setEdges] = useState<Edge[]>([])

  // On mount or when pipelines/agents change, load and layout the latest pipeline
  useEffect(() => {
    if (!pipelines || pipelines.length === 0) {
      setNodes([])
      setEdges([])
      return
    }
    const latestPipeline = pipelines[pipelines.length - 1]
    if (!latestPipeline) {
      setNodes([])
      setEdges([])
      return
    }
    const { nodes: importedNodes, edges: importedEdges } = fromPipelineJSON({
      data: latestPipeline.data,
    })

    // Build agent nodes
    let agentNodes: AgentNodeType[] = []
    if (agents && agents.length > 0) {
      agentNodes = agents.map((agent) => ({
        id: agent.uri.id,
        type: NodeType.agent,
        position: { x: 0, y: 0 },
        data: agent,
        zIndex: 0,
      }))
    }
    // Layout agent nodes
    const { nodes: layoutedAgentNodes } = layoutNodes(agentNodes)

    // Assign parentId to operator/image nodes if assigned to agent
    const agentAssignments = new Map<string, string>()
    for (const agent of agents ?? []) {
      if (agent.operator_assignments) {
        for (const opId of agent.operator_assignments) {
          agentAssignments.set(opId, agent.uri.id)
        }
      }
    }
    const operatorNodes = importedNodes.map((node) => {
      const assignedAgentId = agentAssignments.get(node.id)
      if (assignedAgentId) {
        return {
          ...node,
          parentId: assignedAgentId,
          extent: "parent",
        }
      }
      return node
    }) as (OperatorNodeType | ImageNodeType)[]

    setNodes([...layoutedAgentNodes, ...operatorNodes])
    setEdges(importedEdges)
  }, [pipelines, agents])

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) =>
      setNodes((nds) => applyNodeChanges(changes, nds) as ViewerNode[]),
    [],
  )
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const nodeTypes = useMemo(
    () => ({ operator: OperatorNode, image: ImageNode, agent: AgentNode }),
    [],
  )

  const deleteKeyCode: KeyCode = "Delete"
  const multiSelectionKeyCode: KeyCode = "Shift"
  const selectionKeyCode: KeyCode = "Space"

  return (
    <div className="pipelineflow">
      <div className="reactflow-wrapper" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          deleteKeyCode={deleteKeyCode}
          multiSelectionKeyCode={multiSelectionKeyCode}
          selectionKeyCode={selectionKeyCode}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 0, y: 0, zoom: 1.8 }}
          fitView
        >
          <Controls />
        </ReactFlow>
      </div>
    </div>
  )
}

export default ViewerPipelineFlow
