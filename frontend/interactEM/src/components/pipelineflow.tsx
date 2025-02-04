import { DownloadIcon } from "@radix-ui/react-icons"
import {
  ControlButton,
  Controls,
  type Edge,
  type KeyCode,
  type Node,
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
import { type DragEvent, useCallback, useMemo, useRef, useState } from "react"

import { v4 as uuidv4 } from "uuid"

import { type OperatorNodeData, type PipelineJSON, toJSON } from "../pipeline"
import ImageNode, { type ImageNode as ImageNodeType } from "./imagenode"
import { OperatorMenu, type OperatorMenuItemDragData } from "./operatormenu"
import OperatorNode, {
  type OperatorNode as OperatorNodeType,
} from "./operatornode"

import "@xyflow/react/dist/style.css"
import { useDnD } from "../dnd/dndcontext"
import useOperators from "../hooks/useOperators"
import { layoutElements } from "../layout"
import { fromPipelineJSON } from "../pipeline"
import { LaunchAgentFab } from "./launchagentfab"
import { LaunchPipelineFab } from "./launchpipelinefab"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const generateID = () => uuidv4()

export const PipelineFlow = () => {
  const reactFlowWrapper = useRef(null)
  const [nodes, setNodes] = useState<Node<OperatorNodeData>[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)
  const { screenToFlowPosition } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()
  const { operators, error } = useOperators()
  if (error) {
    console.error("Error loading operators:", error)
  }

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
      const { nodes, edges } = fromPipelineJSON(pipelineJSON)
      const { nodes: layoutedNodes, edges: layoutedEdges } = layoutElements(
        nodes,
        edges,
      )
      setNodes(layoutedNodes)
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

      const nodeType = op.label === "Image" ? "image" : "operator"

      const newNode: OperatorNodeType | ImageNodeType = {
        id: generateID(),
        type: nodeType,
        position,
        data: {
          label: op.label ?? "",
          image: op.image,
          inputs: op.inputs?.map((_) => uuidv4()),
          outputs: op.outputs?.map((_) => uuidv4()),
          parameters: op.parameters?.map((param) => ({
            ...param,
            value: param.default,
          })),
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }

      setNodes((nds) => nds.concat(newNode))
    },
    [screenToFlowPosition, operatorDropData, handlePipelineJSONDrop, operators],
  )

  const handleNodesChange: OnNodesChange<Node<OperatorNodeData>> = useCallback(
    // no need to nullify ID if we are just moving/selecting node
    (changes) => {
      setNodes((nds) => applyNodeChanges<Node<OperatorNodeData>>(changes, nds))
    },
    [],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
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

  const availableOperators = operators ?? []

  const deleteKeyCode: KeyCode = "Delete"
  const multiSelectionKeyCode: KeyCode = "Shift"
  const selectionKeyCode: KeyCode = "Space"

  const nodeTypes = useMemo(
    () => ({ operator: OperatorNode, image: ImageNode }),
    [],
  )

  return (
    <div className="pipelineflow">
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
          <LaunchAgentFab />
        </ReactFlow>
      </div>
      <OperatorMenu operators={availableOperators} />
    </div>
  )
}
