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
import { type DragEvent, useCallback, useRef, useState } from "react"

import { v4 as uuidv4 } from "uuid"

import { operatorByID } from "../operators"
import { type OperatorNodeData, type PipelineJSON, toJSON } from "../pipeline"
import { OperatorMenu, type OperatorMenuItemDragData } from "./operatormenu"
import OperatorNode from "./operatornode"

import "@xyflow/react/dist/style.css"

import { useDnD } from "../dnd/dndcontext"
import { layoutElements } from "../layout"
import { operators } from "../operators"
import { fromPipelineJSON } from "../pipeline"
import Fab from "@mui/material/Fab"
import NavigationIcon from "@mui/icons-material/Navigation"
import AddIcon from "@mui/icons-material/Add"
import { client } from "../client"
import {
  createPipelineMutation,
  readPipelineQueryKey,
  readPipelinesQueryKey,
  runPipelineMutation,
} from "../client/@tanstack/react-query.gen"
import { useMutation, useQueryClient } from "@tanstack/react-query"

export const edgeOptions = {
  type: "smoothstep",
  animated: true,
}

client.setConfig({
  baseURL: "http://localhost:80/",
})

client.instance.interceptors.request.use((config) => {
  config.headers.set("Authorization", "Bearer <token>")
  return config
})

const generateID = () => uuidv4()

export const PipelineFlow = () => {
  const reactFlowWrapper = useRef(null)
  const [nodes, setNodes] = useState<Node<OperatorNodeData>[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [pipelineJSONLoaded, setPipelineJSONLoaded] = useState(false)
  const { screenToFlowPosition } = useReactFlow()
  const [operatorDropData] = useDnD<OperatorMenuItemDragData>()

  const handleConnect: OnConnect = useCallback((connection) => {
    // any new connections should nullify the current pipeline ID
    setCurrentPipelineId(null)
    setEdges((eds) => addEdge(connection, eds))
  }, [])

  const [currentPipelineId, setCurrentPipelineId] = useState<string | null>(
    null,
  )
  const queryClient = useQueryClient()

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

      const op = operatorByID(operatorID)
      if (op === undefined) {
        throw Error("Operator type not found: {operatorID}")
      }

      // Adjust the position for the location the div as grabbed
      const screenPosition = {
        x: event.clientX - offsetX,
        y: event.clientY - offsetY,
      }

      const position = screenToFlowPosition(screenPosition)

      const newNode: OperatorNode = {
        id: generateID(),
        type: "operator",
        position,
        data: {
          label: op.label ?? "",
          image: op.image,
          inputs: op.inputs?.map((_) => uuidv4()),
          outputs: op.outputs?.map((_) => uuidv4()),
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }

      setNodes((nds) => nds.concat(newNode))
    },
    [screenToFlowPosition, operatorDropData, handlePipelineJSONDrop],
  )

  const handleNodesChange: OnNodesChange<Node<OperatorNodeData>> = useCallback(
    // no need to nullify ID if we are just moving/selecting node
    (changes) => {
      const hasMeaningfulChanges = changes.some(
        (change) => change.type !== "position" && change.type !== "select",
      )
      if (hasMeaningfulChanges) {
        setCurrentPipelineId(null)
      }
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

  const createPipeline = useMutation({
    ...createPipelineMutation(),
    onError: (error) => {
      console.error("Error creating pipeline:", error)
    },
    onSuccess: (data) => {
      console.log("Pipeline created:", data)
      setCurrentPipelineId(data.id)
      // Here we should invalidate the pipeline query to get up to date information from backend
      // Currently this is unused, keeping here for reference
      // The "queryKey" generated by hey-api is not very good, we may need to do this manually
      const queryKeyPipeline = readPipelineQueryKey({ path: { id: data.id } })
      queryClient.invalidateQueries({
        queryKey: [queryKeyPipeline[0]._id],
      })
      const queryKeyPipelines = readPipelinesQueryKey()
      queryClient.invalidateQueries({
        queryKey: [queryKeyPipelines[0]._id],
      })
    },
    onSettled: () => {
      console.log("Pipeline creation complete")
    },
  })

  const onCreatePipeline = () => {
    const pipelineData = toJSON(nodes, edges)
    createPipeline.mutate({
      body: pipelineData,
    })
  }

  const runPipeline = useMutation({
    ...runPipelineMutation(),
    onError: (error) => {
      console.error("Error running pipeline:", error)
    },
    onSuccess: (data) => {
      console.log("Pipeline launched:", data)
    },
    onSettled: () => {
      console.log("Pipeline launch settled.")
      // Here we should invalidate the pipeline query to get up to date information from backend
    },
  })

  const onRunPipeline = () => {
    if (currentPipelineId === null) {
      console.error("No pipeline ID to launch")
      return
    }
    console.log("Launching pipeline:", currentPipelineId)
    runPipeline.mutate({
      path: { id: currentPipelineId },
    })
  }

  const availableOperators = operators()

  const deleteKeyCode: KeyCode = "Delete"
  const multiSelectionKeyCode: KeyCode = "Shift"
  const selectionKeyCode: KeyCode = "Space"

  const nodeTypes = { operator: OperatorNode }

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
          <Fab
            variant="extended"
            color="primary"
            aria-label="launch"
            onClick={onCreatePipeline}
            style={{ position: "relative", top: "90%", left: "8%" }}
          >
            <AddIcon />
            Create
          </Fab>

          {currentPipelineId && (
            <Fab
              variant="extended"
              color="primary"
              aria-label="launch"
              onClick={onRunPipeline}
              style={{ position: "relative", top: "90%", left: "10%" }}
            >
              <NavigationIcon />
              Launch
            </Fab>
          )}
        </ReactFlow>
      </div>
      <OperatorMenu operators={availableOperators} />
    </div>
  )
}
