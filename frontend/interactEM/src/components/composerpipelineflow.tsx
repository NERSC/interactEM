import { DownloadIcon } from "@radix-ui/react-icons"
import { useMutation, useQueryClient } from "@tanstack/react-query"
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
import type React from "react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { v4 as uuidv4 } from "uuid"
import {
  pipelinesAddPipelineRevisionMutation,
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesReadPipelineQueryKey,
  pipelinesReadPipelinesQueryKey,
} from "../client/generated/@tanstack/react-query.gen"
import { useDnD } from "../dnd/dndcontext"
import useOperators from "../hooks/useOperators"
import { layoutNodes } from "../layout"
import { fromPipelineJSON, toJSON } from "../pipeline"
import { NodeType, type OperatorNodeTypes } from "../types/nodes"
import ImageNode from "./imagenode"
import { LaunchPipelineFab } from "./launchpipelinefab"
import type { OperatorMenuItemDragData } from "./operatormenu"
import OperatorNode from "./operatornode"
import "@xyflow/react/dist/style.css"
import { toast } from "react-toastify"
import type { PipelineRevisionPublic } from "../client"
import { usePipelineStore } from "../stores"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const generateID = () => uuidv4()

interface ComposerPipelineFlowProps {
  pipelineData?: PipelineRevisionPublic | null
}

const ComposerPipelineFlow: React.FC<ComposerPipelineFlowProps> = ({
  pipelineData,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [nodes, setNodes] = useState<OperatorNodeTypes[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)
  const { screenToFlowPosition, fitView } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()
  const { operators } = useOperators()
  const queryClient = useQueryClient()

  const { currentPipelineId, setPipelineRevision } = usePipelineStore()

  // --- Revision Mutation Setup ---
  const addRevisionMutation = useMutation({
    ...pipelinesAddPipelineRevisionMutation(),
    onSuccess: (data) => {
      // Invalidate queries to refetch pipeline details and revisions
      setPipelineRevision(data)
      queryClient.invalidateQueries({
        queryKey: pipelinesReadPipelinesQueryKey(),
      })
      if (currentPipelineId) {
        queryClient.invalidateQueries({
          queryKey: pipelinesReadPipelineQueryKey({
            path: { id: currentPipelineId },
          }),
        })
        queryClient.invalidateQueries({
          queryKey: pipelinesListPipelineRevisionsQueryKey({
            path: { id: currentPipelineId },
          }),
        })
      }
    },
    onError: () => {
      toast.error("Failed to save pipeline revision. Please try again.")
    },
  })

  // --- Direct Save Revision Function ---
  const saveRevision = useCallback(
    (currentNodes: OperatorNodeTypes[], currentEdges: Edge[]) => {
      if (!currentPipelineId) {
        toast.error("Please select or create a pipeline.")
        return
      }
      const pipelineJson = toJSON(currentNodes, currentEdges)
      addRevisionMutation.mutate({
        path: { id: currentPipelineId },
        body: { data: pipelineJson.data },
      })
    },
    [currentPipelineId, addRevisionMutation],
  )

  useEffect(() => {
    if (!pipelineData) {
      setNodes([])
      setEdges([])
      setPipelineJSONLoaded(false)
      return
    }

    // TODO: type pipeline data!
    const { nodes: importedNodes, edges: importedEdges } =
      fromPipelineJSON(pipelineData)

    let layoutedNodes = importedNodes
    let layoutedEdges = importedEdges

    // Only layout on first render after mount
    const layoutResult = layoutNodes(importedNodes, importedEdges)
    layoutedNodes = layoutResult.nodes
    layoutedEdges = layoutResult.edges

    setNodes(layoutedNodes as OperatorNodeTypes[])
    setEdges(layoutedEdges)
    setPipelineJSONLoaded(true)
    setTimeout(() => {
      fitView({ duration: 300, padding: 0.1 })
    }, 100)
  }, [pipelineData, fitView])

  // --- Change Handlers ---

  const handleConnect: OnConnect = useCallback(
    (connection) => {
      setEdges((eds) => {
        const newEdges = addEdge(connection, eds)
        saveRevision(nodes, newEdges)
        return newEdges
      })
    },
    [nodes, saveRevision],
  )

  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      event.dataTransfer.dropEffect = "move"
    },
    [],
  )

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()

      if (!currentPipelineId) {
        toast.error(
          "Please select or create a pipeline before adding operators.",
        )
        return
      }

      if (event.dataTransfer.files.length > 0) {
        console.log("A file was dropped. Not doing anything...")
        return
      }
      if (!operatorDropData) return

      const { operatorID, offsetX, offsetY } = operatorDropData
      const op = operators?.find((op) => op.id === operatorID)
      if (!op) {
        console.error(`Operator type not found: ${operatorID}`)
        return
      }

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
          label: op.label,
          image: op.image,
          inputs: op.inputs?.map(() => uuidv4()),
          outputs: op.outputs?.map(() => uuidv4()),
          parameters: op.parameters?.map((param) => ({
            ...param,
            value: param.default,
          })),
          tags: op.tags ?? [],
          type: nodeType,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }
      setNodes((nds) => {
        const newNodes = nds.concat(newNode)
        saveRevision(newNodes, edges)
        return newNodes
      })
    },
    [
      screenToFlowPosition,
      operatorDropData,
      operators,
      edges,
      saveRevision,
      currentPipelineId,
    ],
  )

  const handleNodesChange: OnNodesChange<OperatorNodeTypes> = useCallback(
    (changes: NodeChange[]) => {
      // Check if any change affects topology (add, remove, replace) or data
      const affectsTopology = changes.some(
        (change) =>
          change.type === "add" ||
          change.type === "remove" ||
          change.type === "replace" ||
          !(
            change.type === "position" ||
            change.type === "dimensions" ||
            change.type === "select"
          ),
      )
      const nextNodes = applyNodeChanges(changes, nodes) as OperatorNodeTypes[]
      setNodes(nextNodes)

      // Trigger revision save if topology might have changed
      if (affectsTopology) {
        saveRevision(nextNodes, edges)
      }
    },
    [nodes, edges, saveRevision],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      // Check if any change affects topology (add, remove, replace), not just selection
      const affectsTopology = changes.some(
        (change) =>
          change.type === "add" ||
          change.type === "remove" ||
          change.type === "replace" ||
          (change.type === "select") === false, // Any change other than selection
      )

      // Apply changes first
      const nextEdges = applyEdgeChanges(changes, edges)
      setEdges(nextEdges)

      // Trigger revision save if topology changed
      if (affectsTopology) {
        saveRevision(nodes, nextEdges)
      }
    },
    [edges, nodes, saveRevision],
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
          fitView={pipelineJSONLoaded}
          fitViewOptions={{ duration: 300, padding: 0.1 }}
        >
          <Controls>
            <ControlButton onClick={handleDownloadClick}>
              <DownloadIcon />
            </ControlButton>
          </Controls>
          <LaunchPipelineFab />
        </ReactFlow>
      </div>
    </div>
  )
}

export default ComposerPipelineFlow
