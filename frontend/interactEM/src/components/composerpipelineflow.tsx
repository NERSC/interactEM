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
  type OnNodesDelete,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import type React from "react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "react-toastify"
import { v4 as uuidv4 } from "uuid"
import type { PipelineRevisionPublic } from "../client"
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
import { usePipelineStore } from "../stores"
import { NodeType, type OperatorNodeTypes } from "../types/nodes"
import ImageNode from "./nodes/image"
import OperatorNode from "./nodes/operator"
import TableNode from "./nodes/table"
import type { OperatorMenuItemDragData } from "./operatormenu"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

const generateID = () => uuidv4()

interface ComposerPipelineFlowProps {
  pipelineData?: PipelineRevisionPublic | null
  isEditMode: boolean
}

const ComposerPipelineFlow: React.FC<ComposerPipelineFlowProps> = ({
  pipelineData,
  isEditMode,
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
      if (!isEditMode || !currentPipelineId) {
        return
      }
      const pipelineJson = toJSON(currentNodes, currentEdges)
      addRevisionMutation.mutate({
        path: { id: currentPipelineId },
        body: { data: pipelineJson.data },
      })
    },
    [currentPipelineId, addRevisionMutation, isEditMode],
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
      // @ts-expect-error Ignore type mismatch between PipelineRevisionPublic and PipelineJSON
      fromPipelineJSON(pipelineData)

    let layoutedNodes = importedNodes
    let layoutedEdges = importedEdges

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
      if (!isEditMode) return
      setEdges((eds) => {
        const newEdges = addEdge(connection, eds)
        saveRevision(nodes, newEdges)
        return newEdges
      })
    },
    [nodes, saveRevision, isEditMode],
  )

  const handleDragOver = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (isEditMode) {
        event.dataTransfer.dropEffect = "move"
      } else {
        event.dataTransfer.dropEffect = "none"
      }
    },
    [isEditMode],
  )

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      if (!isEditMode) return

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

      const labelToNodeTypeMap: {
        [key: string]: NodeType.image | NodeType.table
      } = {
        Image: NodeType.image,
        Table: NodeType.table,
      }
      const nodeType: OperatorNodeTypes["type"] =
        labelToNodeTypeMap[op.label] ?? NodeType.operator

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
      isEditMode,
    ],
  )

  const handleNodesChange: OnNodesChange<OperatorNodeTypes> = useCallback(
    (changes: NodeChange[]) => {
      const allowedChanges = isEditMode
        ? changes
        : changes.filter(
            (change) =>
              change.type === "position" ||
              change.type === "dimensions" ||
              change.type === "select",
          )

      if (allowedChanges.length === 0) return

      const nextNodes = applyNodeChanges(
        allowedChanges,
        nodes,
      ) as OperatorNodeTypes[]
      setNodes(nextNodes)

      // Trigger revision save if topology might have changed
      // But exclude "remove" type changes as those are handled by onNodesDelete
      if (isEditMode) {
        const affectsTopology = allowedChanges.some(
          (change) => change.type === "add" || change.type === "replace",
        )
        if (affectsTopology) {
          saveRevision(nextNodes, edges)
        }
      }
    },
    [nodes, edges, saveRevision, isEditMode],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const allowedChanges = isEditMode
        ? changes
        : changes.filter((change) => change.type === "select")

      if (allowedChanges.length === 0) return

      const nextEdges = applyEdgeChanges(allowedChanges, edges)
      setEdges(nextEdges)

      if (isEditMode) {
        const affectsTopology = allowedChanges.some(
          (change) =>
            change.type === "add" ||
            change.type === "replace" ||
            change.type !== "remove",
        )
        if (affectsTopology) {
          saveRevision(nodes, nextEdges)
        }
      }
    },
    [edges, nodes, saveRevision, isEditMode],
  )

  const handleNodesDelete: OnNodesDelete = useCallback(
    (deletedNodes) => {
      if (!isEditMode) return

      // When nodes are deleted, we handle this as a single operation
      // that includes removing connected edges as well
      // This prevents duplicate saveRevision calls
      saveRevision(
        nodes.filter(
          (node) => !deletedNodes.some((deleted) => deleted.id === node.id),
        ),
        edges.filter(
          (edge) =>
            !deletedNodes.some(
              (node) => node.id === edge.source || node.id === edge.target,
            ),
        ),
      )
    },
    [nodes, edges, saveRevision, isEditMode],
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
    () => ({ operator: OperatorNode, image: ImageNode, table: TableNode }),
    [],
  )

  const deleteKeyCode: KeyCode | null = isEditMode ? "Delete" : null
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
          onNodesDelete={handleNodesDelete}
          deleteKeyCode={deleteKeyCode}
          multiSelectionKeyCode={multiSelectionKeyCode}
          selectionKeyCode={selectionKeyCode}
          defaultEdgeOptions={edgeOptions}
          nodeTypes={nodeTypes}
          fitView={pipelineJSONLoaded}
          fitViewOptions={{ duration: 300, padding: 0.1 }}
          nodesConnectable={isEditMode}
          noWheelClassName="no-wheel"
        >
          <Controls>
            <ControlButton onClick={handleDownloadClick}>
              <DownloadIcon />
            </ControlButton>
          </Controls>
        </ReactFlow>
      </div>
    </div>
  )
}

export default ComposerPipelineFlow
