import { DownloadIcon } from "@radix-ui/react-icons"
import {
  ControlButton,
  Controls,
  type Edge,
  type KeyCode,
  type OnConnect,
  type OnEdgesChange,
  type OnNodesChange,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
} from "@xyflow/react"
import {
  type DragEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { v4 as uuidv4 } from "uuid"
import { type PipelineJSON, fromPipelineJSON, toJSON } from "../pipeline"
import { OperatorMenu, type OperatorMenuItemDragData } from "./operatormenu"
import OperatorNode from "./operatornode"
import "@xyflow/react/dist/style.css"
import { useDnD } from "../dnd/dndcontext"
import { useAgents } from "../hooks/useAgents"
import useOperators from "../hooks/useOperators"
import { layoutNodes } from "../layout"
import {
  type AgentNodeType,
  type AnyNodeType,
  NodeType,
  type OperatorNodeTypes,
} from "../types/nodes"
import AgentNode from "./agentnode"
import ImageNode from "./imagenode"
import { LaunchAgentFab } from "./launchagentfab"
import { LaunchPipelineFab } from "./launchpipelinefab"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const generateID = () => uuidv4()

export const PipelineFlow = () => {
  const reactFlowWrapper = useRef(null)
  const [operatorNodes, setOperatorNodes] = useState<OperatorNodeTypes[]>([])
  const [agentNodes, setAgentNodes] = useState<AgentNodeType[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)

  // Add this after the savedOperatorPositions state declaration
  const { screenToFlowPosition } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()
  const { operators, error: operatorsError } = useOperators()
  const { agents, error: agentsError } = useAgents()

  if (operatorsError) console.error("Error loading operators:", operatorsError)
  if (agentsError) console.error("Error loading agents:", agentsError)

  // filter old/new agents
  useEffect(() => {
    if (!agents) return
    setAgentNodes((prevNodes) => {
      const currentAgentIds = new Set(agents.map((a) => a.uri.id))

      // Keep agents that are present in the agents KV
      const filteredAgentNodes = prevNodes.filter((node) => {
        return currentAgentIds.has(node.id)
      })

      // Update existing agent nodes with fresh agent data
      const updatedAgentNodes = filteredAgentNodes.map((node) => {
        const freshAgent = agents.find((a) => a.uri.id === node.id)
        if (freshAgent) {
          return {
            ...node,
            data: freshAgent,
          }
        }
        return node
      })

      const existingAgentIds = new Set(updatedAgentNodes.map((n) => n.id))

      // Create nodes for new agents
      const newAgentsInKV = agents.filter(
        (a) => !existingAgentIds.has(a.uri.id),
      )
      const newAgentNodes = newAgentsInKV.map(
        (agent) =>
          ({
            id: agent.uri.id,
            type: NodeType.agent,
            position: { x: 0, y: 0 },
            data: agent,
            zIndex: 0,
          }) as AgentNodeType,
      )

      if (newAgentNodes.length === 0) {
        return updatedAgentNodes // Return updated nodes even if no new ones
      }

      // Combine existing and new agent nodes
      const allAgentNodes = [...updatedAgentNodes, ...newAgentNodes]

      // Layout the agent nodes if there is a new one
      const { nodes: layoutedAgentNodes } = layoutNodes(allAgentNodes)

      return [...layoutedAgentNodes]
    })
  }, [agents])

  // memoize so we don't re-render on every agent KV state change
  const agentOperatorAssignments = useMemo(() => {
    if (!agents) return null

    const assignmentsMap = new Map<string, string>()
    for (const agent of agents) {
      if (agent.operator_assignments) {
        for (const operatorId of agent.operator_assignments) {
          assignmentsMap.set(operatorId, agent.uri.id)
        }
      }
    }

    return assignmentsMap
  }, [agents])

  // Do operator assignments
  useEffect(() => {
    if (!agentOperatorAssignments) return

    // Update operator nodes with parentId based on agent assignments
    setOperatorNodes((prevOperatorNodes) => {
      // Update each operator node with the parentId if assigned
      return prevOperatorNodes.map((node) => {
        const assignedAgentId = agentOperatorAssignments.get(node.id)
        if (assignedAgentId) {
          return {
            ...node,
            parentId: assignedAgentId,
            extent: "parent",
          }
        }
        return node
      })
    })
  }, [agentOperatorAssignments])

  const handleConnect: OnConnect = useCallback((connection) => {
    // any new connections should nullify the current pipeline ID
    setEdges((eds) => addEdge(connection, eds))
  }, [])

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = "move"
  }, [])

  const handlePipelineJSONDrop = useCallback(
    async (event: DragEvent<HTMLDivElement>) => {
      const files = event.dataTransfer.files
      const file = files[0]

      if (file === undefined) {
        return
      }

      const pipelineJSON: PipelineJSON = JSON.parse(await file.text())
      const { nodes: importedNodes, edges } = fromPipelineJSON(pipelineJSON)
      const { nodes: layoutedNodes, edges: layoutedEdges } = layoutNodes(
        importedNodes,
        edges,
      )
      setOperatorNodes(layoutedNodes as OperatorNodeTypes[])
      setEdges(layoutedEdges)
      setPipelineJSONLoaded(true)
    },
    [],
  )

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()

      // Are we dropping a pipeline file?
      if (event.dataTransfer.files.length > 0) {
        handlePipelineJSONDrop(event)
        return
      }

      // check if the dropped element is valid
      if (!operatorDropData) {
        return
      }

      const { operatorID, offsetX, offsetY } = operatorDropData

      const op = operators?.find((op) => op.id === operatorID)

      if (op === undefined) {
        throw Error("Operator type not found: {operatorID}")
      }

      // Adjust the position for the location the div as grabbed
      const screenPosition = {
        x: event.clientX - offsetX,
        y: event.clientY - offsetY,
      }

      const position = screenToFlowPosition(screenPosition)
      const nodeType = op.label === "Image" ? NodeType.image : NodeType.operator

      const newNode: OperatorNodeTypes = {
        id: generateID(),
        type: nodeType,
        position,
        zIndex: 1,
        data: {
          label: op.label ?? "",
          image: op.image,
          inputs: op.inputs?.map((_) => uuidv4()),
          outputs: op.outputs?.map((_) => uuidv4()),
          parameters: op.parameters?.map((param) => ({
            ...param,
            value: param.default,
          })),
          tags: op.tags ?? [],
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }

      setOperatorNodes((nds) => nds.concat(newNode) as OperatorNodeTypes[])
    },
    [screenToFlowPosition, operatorDropData, handlePipelineJSONDrop, operators],
  )

  const handleNodesChange: OnNodesChange<AnyNodeType> = useCallback(
    (changes) => {
      const nodeChanges = (nds: AnyNodeType[]) => {
        return applyNodeChanges(changes, nds) as AnyNodeType[]
      }

      setOperatorNodes((nds) => nodeChanges(nds) as OperatorNodeTypes[])
      setAgentNodes((nds) => nodeChanges(nds) as AgentNodeType[])
    },
    [],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const handleDownloadClick = () => {
    const pipelineJSON = toJSON(operatorNodes, edges)
    const blob = new Blob([JSON.stringify(pipelineJSON)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "pipeline.json"
    a.click()
    URL.revokeObjectURL(url)
  }

  const availableOperators = operators ?? []

  const deleteKeyCode: KeyCode = "Delete"
  const multiSelectionKeyCode: KeyCode = "Shift"
  const selectionKeyCode: KeyCode = "Space"

  const nodeTypes = useMemo(
    () => ({ operator: OperatorNode, image: ImageNode, agent: AgentNode }),
    [],
  )

  return (
    <div className="pipelineflow">
      <div className="reactflow-wrapper" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={[...agentNodes, ...operatorNodes]}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={handleConnect}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          deleteKeyCode={deleteKeyCode}
          multiSelectionKeyCode={multiSelectionKeyCode}
          selectionKeyCode={selectionKeyCode}
          defaultEdgeOptions={edgeOptions}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 0, y: 0, zoom: 1.8 }}
          fitView={pipelineJSONLoaded}
        >
          <Controls>
            <ControlButton onClick={handleDownloadClick}>
              <DownloadIcon />
            </ControlButton>
          </Controls>
          <LaunchPipelineFab nodes={operatorNodes} edges={edges} />
          <LaunchAgentFab />
        </ReactFlow>
      </div>
      <OperatorMenu operators={availableOperators} />
    </div>
  )
}
