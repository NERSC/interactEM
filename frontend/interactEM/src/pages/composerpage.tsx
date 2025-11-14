import { Box } from "@mui/material"
import AgentsAccordion from "../components/agents/accordion"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineHud } from "../components/pipelines/hud"
import { ViewSwitcher } from "../components/pipelines/viewswitcher"
import RunningPipelineFlow from "../components/runningpipelineflow"
import { useActivePipeline } from "../hooks/api/useActivePipeline"
import { ViewMode, useViewModeStore } from "../stores"

export default function ComposerPage() {
  const { pipeline, revision, runtimePipelineId } = useActivePipeline()
  const { viewMode } = useViewModeStore()

  return (
    <div className="composer-page">
      {/* Controls Container - Left Side */}
      <Box
        sx={{
          position: "absolute",
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: "none",
          alignItems: "flex-start",
          gap: 1,
          margin: 1,
        }}
      >
        {/* Pipeline HUD */}
        <Box
          sx={{
            position: "relative",
            pointerEvents: "auto",
          }}
        >
          <PipelineHud />
        </Box>

        {/* Agents Accordion */}
        <Box
          sx={{
            position: "relative",
            pointerEvents: "auto",
          }}
        >
          <AgentsAccordion />
        </Box>
      </Box>

      {/* View Switcher - Bottom Center */}
      <Box
        sx={{
          position: "absolute",
          bottom: 0,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 2,
          margin: 1,
          pointerEvents: "auto",
        }}
      >
        <ViewSwitcher />
      </Box>

      {/* Main Flow Area - Base layer */}
      <div className="composer-flow">
        {viewMode === ViewMode.Composer ? (
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
      {viewMode === ViewMode.Composer && (
        <div className="composer-operators">
          <OperatorMenu />
        </div>
      )}
    </div>
  )
}
