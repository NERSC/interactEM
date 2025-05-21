import BuildIcon from "@mui/icons-material/Build"
import VisibilityIcon from "@mui/icons-material/Visibility"
import { Box, IconButton, Tooltip } from "@mui/material"
import { useEffect } from "react"
import AgentsAccordion from "../components/agents/accordion"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineHud } from "../components/pipelines/hud"
import { usePipelineContext } from "../contexts/pipeline"
import { useActivePipeline } from "../hooks/api/useActivePipeline"
import useOperators from "../hooks/api/useOperators"
import { useAgents } from "../hooks/nats/useAgents"
import { usePipelineStore } from "../stores"
import { useEditModeState } from "../stores/edit"

export default function ComposerPage() {
  const { operators } = useOperators()
  const { agents } = useAgents()
  const { revision } = useActivePipeline()
  const { currentPipelineId } = usePipelineStore()
  const { isEditMode, setIsEditMode, canEdit } = useEditModeState()
  const { isCurrentPipelineRunning } = usePipelineContext()

  useEffect(() => {
    if (isCurrentPipelineRunning && isEditMode) {
      setIsEditMode(false)
    }
  }, [isCurrentPipelineRunning, isEditMode, setIsEditMode])

  const toggleEditMode = () => {
    if (canEdit) {
      setIsEditMode(!isEditMode)
    }
  }

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
            display: "flex", // Make HUD and Toggle flex container
            alignItems: "center", // Align items vertically
            gap: 2, // Add gap between HUD and Toggle
          }}
        >
          <PipelineHud />
          <Tooltip
            title={
              !canEdit || isCurrentPipelineRunning
                ? "Cannot edit while pipeline is running"
                : "Toggle edit mode"
            }
          >
            <span>
              <IconButton
                onClick={toggleEditMode}
                color="primary"
                disabled={!canEdit || isCurrentPipelineRunning}
                sx={{
                  bgcolor: "background.paper",
                  borderRadius: 1,
                  boxShadow: 1,
                  alignItems: "center",
                  justifyContent: "center",
                  p: 1,
                  opacity: !canEdit || isCurrentPipelineRunning ? 0.5 : 1,
                }}
                size="medium"
                aria-label="toggle edit mode"
              >
                {isEditMode ? <VisibilityIcon /> : <BuildIcon />}
              </IconButton>
            </span>
          </Tooltip>
        </Box>

        {/* Agents Accordion */}
        <Box>
          <AgentsAccordion agents={agents} />
        </Box>
      </Box>

      {/* Main Flow Area */}
      <div className="composer-flow">
        <ComposerPipelineFlow
          key={currentPipelineId}
          pipelineData={revision ?? null}
          isEditMode={isEditMode}
        />
      </div>

      {/* Operator Menu */}
      {isEditMode && (
        <div className="composer-operators">
          <OperatorMenu operators={operators ?? []} />
        </div>
      )}
    </div>
  )
}
