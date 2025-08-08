import { Box } from "@mui/material"
import AgentsAccordion from "../components/agents/accordion"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineHud } from "../components/pipelines/hud"
import RunningPipelineFlow from "../components/runningpipelineflow"
import { useActivePipeline } from "../hooks/api/useActivePipeline"
import { useViewModeStore } from "../stores"

export default function ComposerPage() {
  const { pipeline, revision, runtimePipelineId } = useActivePipeline()
  const { viewMode } = useViewModeStore()

  return (
    <div className="composer-page">
      <Box
        sx={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: 1,
        }}
      >
        {/* Pipeline HUD */}
        <Box
          sx={{
            flexShrink: 0,
            width: "100%",
            alignSelf: "flex-start",
          }}
        >
          <PipelineHud />
        </Box>

        {/* Agents Accordion */}
        <Box>
          <AgentsAccordion />
        </Box>
      </Box>

      {/* Main Flow Area */}
      <div className="composer-flow">
        {viewMode === "composer" ? (
          <ComposerPipelineFlow key={pipeline?.id} pipelineData={revision} />
        ) : (
          <RunningPipelineFlow
            key={runtimePipelineId}
            pipelineDeploymentId={runtimePipelineId || undefined}
            pipelineData={revision}
          />
        )}
      </div>

      {/* Operator Menu - Only show in composer mode */}
      {viewMode === "composer" && (
        <div className="composer-operators">
          <OperatorMenu />
        </div>
      )}
    </div>
  )
}
