import BuildIcon from "@mui/icons-material/Build"
import VisibilityIcon from "@mui/icons-material/Visibility"
import { Box, IconButton } from "@mui/material"
import { useState } from "react"
import AgentsAccordion from "../components/agentsaccordion"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineHud } from "../components/pipelinehud"
import { useActivePipeline } from "../hooks/useActivePipeline"
import { useAgents } from "../hooks/useAgents"
import useOperators from "../hooks/useOperators"
import { usePipelineStore } from "../stores"

export default function ComposerPage() {
  const { operators } = useOperators()
  const { agents } = useAgents()
  const { revision } = useActivePipeline()
  const { currentPipelineId } = usePipelineStore()

  const [isEditMode, setIsEditMode] = useState(false)

  const toggleEditMode = () => {
    setIsEditMode(!isEditMode)
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
          {/* TODO: I think we should separate this into a button bar along with delete and launch buttons. */}
          <IconButton
            onClick={toggleEditMode}
            color="primary"
            sx={{
              bgcolor: "background.paper",
              borderRadius: 1,
              boxShadow: 1,
              alignItems: "center",
              justifyContent: "center",
              p: 1,
            }}
            size="medium"
            aria-label="toggle edit mode"
          >
            {isEditMode ? <VisibilityIcon /> : <BuildIcon />}
          </IconButton>
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
