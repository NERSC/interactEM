import { Stack } from "@mui/material"
import AgentsArray from "../components/agentsarray"
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
      {/* Top Bar Area */}
      <Stack
        direction="row"
        spacing={2}
        sx={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
          alignItems: "center",
        }}
      >
        {/* Self-contained Pipeline HUD with integrated pipeline drawer */}
        <PipelineHud />
        <AgentsArray agents={agents} />
      </Stack>

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