import { DownloadIcon } from "@radix-ui/react-icons"
import {
  ControlButton,
  Controls,
  type Edge,
  type EdgeChange,
  type KeyCode,
  type NodeChange,
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
import { useCallback, useMemo, useRef, useState } from "react"
import { v4 as uuidv4 } from "uuid"
import { useDnD } from "../dnd/dndcontext"
import useOperators from "../hooks/useOperators"
import { layoutNodes } from "../layout"
import { type PipelineJSON, fromPipelineJSON, toJSON } from "../pipeline"
import { NodeType, type OperatorNodeTypes } from "../types/nodes"
import ImageNode from "./imagenode"
import { LaunchPipelineFab } from "./launchpipelinefab"
import type { OperatorMenuItemDragData } from "./operatormenu"
import OperatorNode from "./operatornode"
import "@xyflow/react/dist/style.css"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const generateID = () => uuidv4()

const ComposerPipelineFlow = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [nodes, setNodes] = useState<OperatorNodeTypes[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)

  const { screenToFlowPosition } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()
  const { operators, error: operatorsError } = useOperators()

  if (operatorsError) console.error("Error loading operators:", operatorsError)

  const handleConnect: OnConnect = useCallback((connection) => {
    setEdges((eds) => addEdge(connection, eds))
  }, [])

  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      event.dataTransfer.dropEffect = "move"
    },
    [],
  )

  const handlePipelineJSONDrop = useCallback(
    async (event: React.DragEvent<HTMLDivElement>) => {
      const files = event.dataTransfer.files
      const file = files[0]
      if (!file) return

      const pipelineJSON: PipelineJSON = JSON.parse(await file.text())
      const { nodes: importedNodes, edges: importedEdges } =
        fromPipelineJSON(pipelineJSON)
      // Only keep operator/image nodes
      const filteredNodes = importedNodes.filter(
        (n) => n.type === NodeType.operator || n.type === NodeType.image,
      ) as OperatorNodeTypes[]
      const { nodes: layoutedNodes, edges: layoutedEdges } = layoutNodes(
        filteredNodes,
        importedEdges,
      )
      setNodes(layoutedNodes as OperatorNodeTypes[])
      setEdges(layoutedEdges)
      setPipelineJSONLoaded(true)
    },
    [],
  )

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (event.dataTransfer.files.length > 0) {
        handlePipelineJSONDrop(event)
        return
      }
      if (!operatorDropData) return

      const { operatorID, offsetX, offsetY } = operatorDropData
      const op = operators?.find((op) => op.id === operatorID)
      if (!op) throw Error(`Operator type not found: ${operatorID}`)

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
          inputs: op.inputs?.map(() => uuidv4()),
          outputs: op.outputs?.map(() => uuidv4()),
          parameters: op.parameters?.map((param) => ({
            ...param,
            value: param.default,
          })),
          tags: op.tags ?? [],
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }
      setNodes((nds) => nds.concat(newNode))
    },
    [screenToFlowPosition, operatorDropData, handlePipelineJSONDrop, operators],
  )
  const handleNodesChange: OnNodesChange<OperatorNodeTypes> = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => applyNodeChanges(changes, nds) as OperatorNodeTypes[])
    },
    [],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes: EdgeChange[]) =>
      setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  )

  const handleDownloadClick = () => {
    const pipelineJSON = toJSON(nodes, edges)
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

  const nodeTypes = useMemo(
    () => ({ operator: OperatorNode, image: ImageNode }),
    [],
  )

  const deleteKeyCode: KeyCode = "Delete"
  const multiSelectionKeyCode: KeyCode = "Shift"
  const selectionKeyCode: KeyCode = "Space"

  return (
    <div className="composer-pipelineflow">
      <div className="reactflow-wrapper" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
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
          <LaunchPipelineFab nodes={nodes} edges={edges} />
        </ReactFlow>
      </div>
    </div>
  )
}

export default ComposerPipelineFlow
