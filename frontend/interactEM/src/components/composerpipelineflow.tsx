import { DownloadIcon } from "@radix-ui/react-icons"
import {
  ControlButton,
  Controls,
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
import { useCallback, useMemo, useRef } from "react"
import { toast } from "react-toastify"
import { v4 as uuidv4 } from "uuid"
import type { PipelineRevisionPublic } from "../client"
import { useDnD } from "../contexts/dnd"
import useOperatorSpecs from "../hooks/api/useOperatorSpecs"
import { usePipelineStore } from "../stores"
import { useSavePipelineRevision } from "../hooks/api/useSavePipelineRevision"
import {
  type OperatorNodeTypes,
  displayNodeTypeFromLabel,
} from "../types/nodes"
import { layoutNodes } from "../utils/layout"
import { fromPipelineJSON, toJSON } from "../utils/pipeline"
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
}

const ComposerPipelineFlow: React.FC<ComposerPipelineFlowProps> = ({
  pipelineData,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition, fitView } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()
  const { operatorSpecs } = useOperatorSpecs()

  const { currentPipelineId, setPipelineRevision } = usePipelineStore()

  // --- Revision Mutation Setup ---

  useEffect(() => {
    if (!pipelineData) {
      setNodes([])
      setEdges([])
      setPipelineJSONLoaded(false)
      return
    }

    const { nodes: importedNodes, edges: importedEdges } =
      fromPipelineJSON(pipelineData)

    let layoutedNodes = importedNodes
    let layoutedEdges = importedEdges
  const { saveRevision } = useSavePipelineRevision()

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

      const { specID, offsetX, offsetY } = operatorDropData
      const op = operatorSpecs?.find((op) => op.id === specID)
      if (!op) {
        console.error(`Operator type not found: ${specID}`)
        return
      }

      const screenPosition = {
        x: event.clientX - offsetX,
        y: event.clientY - offsetY,
      }
      const position = screenToFlowPosition(screenPosition)

      const nodeType = displayNodeTypeFromLabel(op.label)

      const newNode: OperatorNodeTypes = {
        id: generateID(),
        type: nodeType,
        position,
        zIndex: 1,
        data: {
          spec_id: op.id,
          label: op.label,
          description: op.description,
          image: op.image,
          inputs: op.inputs?.map(() => uuidv4()),
          outputs: op.outputs?.map(() => uuidv4()),
          parameters: op.parameters?.map((param) => ({
            ...param,
            value: param.default,
          })),
          tags: op.tags ?? [],
          node_type: "operator",
          parallel_config: op.parallel_config,
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
      operatorSpecs,
      edges,
      saveRevision,
      currentPipelineId,
    ],
  )

  const handleNodesChange: OnNodesChange<OperatorNodeTypes> = useCallback(
    (changes: NodeChange[]) => {
      if (changes.length === 0) return
      const nextNodes = applyNodeChanges(changes, nodes) as OperatorNodeTypes[]
      setNodes(nextNodes)

      // Trigger revision save if topology might have changed
      // But exclude "remove" type changes as those are handled by onNodesDelete

      const affectsTopology = changes.some(
        (change) => change.type === "add" || change.type === "replace",
      )
      if (affectsTopology) {
        saveRevision(nextNodes, edges)
      }
    },
    [nodes, edges, saveRevision],
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (changes.length === 0) return

      const nextEdges = applyEdgeChanges(changes, edges)
      setEdges(nextEdges)

      const affectsTopology = changes.some(
        (change) =>
          change.type === "add" ||
          change.type === "replace" ||
          change.type !== "remove",
      )
      if (affectsTopology) {
        saveRevision(nodes, nextEdges)
      }
    },
    [edges, nodes, saveRevision],
  )

  const handleNodesDelete: OnNodesDelete = useCallback(
    (deletedNodes) => {
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
    [nodes, edges, saveRevision],
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
          onNodesDelete={handleNodesDelete}
          deleteKeyCode={deleteKeyCode}
          multiSelectionKeyCode={multiSelectionKeyCode}
          selectionKeyCode={selectionKeyCode}
          defaultEdgeOptions={edgeOptions}
          nodeTypes={nodeTypes}
          fitView={pipelineJSONLoaded}
          fitViewOptions={{ duration: 300, padding: 0.1 }}
          nodesConnectable={true}
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
