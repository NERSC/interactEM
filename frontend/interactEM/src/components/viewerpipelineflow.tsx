import { MagicWandIcon } from "@radix-ui/react-icons"
import {
  ControlButton,
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
import { useRunningPipelines } from "../hooks/useRunningPipelines"
import { layoutNodesWithELK as layoutNodes } from "../layout/elk"
import { type PipelineJSON, fromPipelineJSON } from "../pipeline"
import {
  type AgentNodeType,
  type AnyNodeType,
  type ImageNodeType,
  NodeType,
  type OperatorNodeType,
} from "../types/nodes"
import AgentNode from "./agentnode"
import ImageNode from "./imagenode"
import OperatorNode from "./operatornode"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const ViewerPipelineFlow = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { agents } = useAgents()
  const { pipelines } = useRunningPipelines()
  const [edges, setEdges] = useState<Edge[]>([])
  const [nodes, setNodes] = useState<AnyNodeType[]>([])

  const assignmentMap = useMemo(() => {
    const map = new Map<string, string>()
    if (agents) {
      for (const agent of agents) {
        if (agent.operator_assignments) {
          for (const opId of agent.operator_assignments) {
            map.set(opId, agent.uri.id)
          }
        }
      }
    }
    return map
  }, [agents])

  const latestPipeline = useMemo(() => {
    if (!pipelines || pipelines.length === 0) return undefined
    return pipelines[pipelines.length - 1]
  }, [pipelines])

  const imported = useMemo(() => {
    if (!latestPipeline) return { nodes: [], edges: [] }
    return fromPipelineJSON({
      data: latestPipeline.data as PipelineJSON["data"],
    })
  }, [latestPipeline])

  const agentNodes = useMemo(() => {
    if (!agents) return []
    return agents.map(
      (agent) =>
        ({
          id: agent.uri.id,
          type: NodeType.agent,
          position: { x: 0, y: 0 },
          data: agent,
          zIndex: 0,
        }) as AgentNodeType,
    )
  }, [agents])

  const operatorNodes = useMemo(() => {
    return imported.nodes.map((node) => {
      const assignedAgentId = assignmentMap.get(node.id)
      return {
        ...node,
        type: node.data.type,
        data: {
          ...node.data,
        },
        expandParent: true,
        zIndex: 1,
        ...(assignedAgentId
          ? { parentId: assignedAgentId, extent: "parent" }
          : {}),
      }
    }) as (OperatorNodeType | ImageNodeType)[]
  }, [imported.nodes, assignmentMap])

  const allNodes = useMemo(
    () => [...agentNodes, ...operatorNodes],
    [agentNodes, operatorNodes],
  )
  const allEdges = useMemo(() => imported.edges, [imported.edges])

  const mergeNodes = useCallback(
    (imported: AnyNodeType[], current: AnyNodeType[]): AnyNodeType[] => {
      const currentMap = new Map(current.map((n) => [n.id, n]))
      return imported.map((node) => {
        const existing = currentMap.get(node.id)
        if (existing) {
          return {
            ...node,
            position: existing.position,
            width: existing.width,
            height: existing.height,
            selected: existing.selected,
            dragging: existing.dragging,
          }
        }
        return node
      })
    },
    [],
  )

  useEffect(() => {
    setNodes((currentNodes) => mergeNodes(allNodes, currentNodes))
    setEdges(allEdges)
  }, [allNodes, allEdges, mergeNodes])

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) =>
      setNodes((nds) => applyNodeChanges(changes, nds) as AnyNodeType[]),
    [],
  )
  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const handleLayout = useCallback(async () => {
    try {
      const { nodes: layouted } = await layoutNodes(nodes, edges)
      setNodes(layouted)
    } catch (error) {
      console.error("Layout failed:", error)
    }
  }, [nodes, edges])

  const nodeTypes = useMemo(
    () => ({ operator: OperatorNode, image: ImageNode, agent: AgentNode }),
    [],
  )

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
          multiSelectionKeyCode={multiSelectionKeyCode}
          selectionKeyCode={selectionKeyCode}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 0, y: 0, zoom: 1.8 }}
          defaultEdgeOptions={edgeOptions}
          fitView
        >
          <Controls>
            <ControlButton onClick={handleLayout} title="Auto Layout">
              <MagicWandIcon />
            </ControlButton>
          </Controls>
        </ReactFlow>
      </div>
    </div>
  )
}

export default ViewerPipelineFlow
