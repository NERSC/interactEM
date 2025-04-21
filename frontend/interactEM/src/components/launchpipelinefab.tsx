import { Navigation } from "@mui/icons-material"
import { Fab } from "@mui/material"
import { useMutation } from "@tanstack/react-query"
import { pipelinesRunPipelineMutation } from "../client"
import { usePipelineStore } from "../stores"

export const LaunchPipelineFab = () => {
  const { currentPipelineId, currentRevisionId } = usePipelineStore()
  const launchPipeline = useMutation({
    ...pipelinesRunPipelineMutation(),
  })
  const onLaunchPipeline = () => {
    launchPipeline.mutate({
      path: { id: currentPipelineId!, revision_id: currentRevisionId! },
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
