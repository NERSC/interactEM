import { Box } from "@mui/material"
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
          <AgentsAccordion agents={agents} />
        </Box>
      </Box>

      {/* Main Flow Area */}
      <div className="composer-flow">
        <ComposerPipelineFlow
          key={currentPipelineId}
          pipelineData={revision ?? null}
        />
      </div>

      {/* Operator Menu */}
      <div className="composer-operators">
        <OperatorMenu operators={operators ?? []} />
      </div>
    </div>
  )
}
