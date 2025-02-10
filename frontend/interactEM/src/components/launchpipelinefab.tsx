import { Navigation } from "@mui/icons-material"
import { Fab } from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import type { Edge, Node } from "@xyflow/react"
import { pipelinesCreateAndRunPipelineMutation } from "../client"
import { type OperatorNodeData, toJSON } from "../pipeline"

type CreatePipelineFabProps = {
  nodes: Node<OperatorNodeData>[]
  edges: Edge[]
}

export const LaunchPipelineFab = ({ nodes, edges }: CreatePipelineFabProps) => {
  const launchPipeline = useMutation({
    ...pipelinesCreateAndRunPipelineMutation(),
  })
  const onLaunchPipeline = () => {
    const pipelineData = toJSON(nodes, edges)
    launchPipeline.mutate({
      body: pipelineData,
    })
  }

  return (
    <Fab
      variant="extended"
      color="primary"
      aria-label="create"
      onClick={onLaunchPipeline}
      style={{ position: "relative", top: "90%", left: "8%" }}
    >
      <Navigation />
      Launch
    </Fab>
  )
}
