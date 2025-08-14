import { Box, Typography } from "@mui/material"
import {
  Controls,
  type NodeChange,
  type OnNodesChange,
  ReactFlow,
  applyNodeChanges,
  useReactFlow,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import type React from "react"
import { useCallback, useMemo } from "react"
import type { PipelineRevisionPublic } from "../client"
import { usePipelineStatus } from "../hooks/nats/useRunningPipelines"
import { usePipelineGraph } from "../hooks/usePipelineGraph"
import type { OperatorNodeTypes } from "../types/nodes"
import ImageNode from "./nodes/image"
import OperatorNode from "./nodes/operator"
import TableNode from "./nodes/table"

interface RunningPipelineFlowProps {
  pipelineData?: PipelineRevisionPublic
  pipelineDeploymentId?: string
}

const RunningPipelineFlow: React.FC<RunningPipelineFlowProps> = ({
  pipelineData,
  pipelineDeploymentId,
}) => {
  const { fitView } = useReactFlow()
  const { pipeline } = usePipelineStatus(
    pipelineDeploymentId ? pipelineDeploymentId : null,
  )

  const { nodes, setNodes, edges, pipelineJSONLoaded } = usePipelineGraph(
    pipelineData,
    fitView,
  )

  const handleNodesChange: OnNodesChange<OperatorNodeTypes> = useCallback(
    (changes: NodeChange[]) => {
      const allowedChanges = changes.filter(
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
    },
    [nodes, setNodes],
  )

  const nodeTypes = useMemo(
    () => ({
      operator: OperatorNode,
      image: ImageNode,
      table: TableNode,
    }),
    [],
  )

  // Now handle conditional rendering after all hooks are called
  if (!pipelineDeploymentId) {
    return (
      <div className="pipelineflow">
        <Box
          sx={{
            height: "100%",
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography variant="h6" color="text.secondary">
            No deployment selected
          </Typography>
        </Box>
      </div>
    )
  }

  if (!pipeline) {
    return (
      <div className="pipelineflow">
        <Box
          sx={{
            height: "100%",
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Typography variant="h6" color="text.secondary">
            This deployment is not currently running
          </Typography>
        </Box>
      </div>
    )
  }

  return (
    <div className="pipelineflow">
      <div className="reactflow-wrapper">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          edgesReconnectable={false}
          nodeTypes={nodeTypes}
          fitView={pipelineJSONLoaded}
          fitViewOptions={{ duration: 300, padding: 0.1 }}
          nodesConnectable={false}
          nodesDraggable={false}
          edgesFocusable={false}
          elementsSelectable={true}
          deleteKeyCode={null}
        >
          <Controls />
        </ReactFlow>
      </div>
    </div>
  )
}

export default RunningPipelineFlow
