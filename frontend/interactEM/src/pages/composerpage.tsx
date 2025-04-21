import ListIcon from "@mui/icons-material/List"
import { Fab, Stack } from "@mui/material"
import { useCallback, useState } from "react"
import AgentsArray from "../components/agentsarray"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { CurrentPipelineDisplay } from "../components/currentpipelinedisplay"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineList } from "../components/pipelinelist"
import { useActivePipeline } from "../hooks/useActivePipeline"
import { useAgents } from "../hooks/useAgents"
import useOperators from "../hooks/useOperators"
import { usePipelineStore } from "../stores"

export default function ComposerPage() {
  const { operators } = useOperators()
  const { agents } = useAgents()
  const [isPipelineDrawerOpen, setIsPipelineDrawerOpen] = useState(false)
  const { revision } = useActivePipeline()
  const { currentPipelineId } = usePipelineStore()

  const handleTogglePipelineDrawer = () => {
    setIsPipelineDrawerOpen(!isPipelineDrawerOpen)
  }

  const handleClosePipelineDrawer = useCallback(() => {
    setIsPipelineDrawerOpen(false)
  }, [])

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
        {/* Pipeline List Drawer Button */}
        <Fab
          color="primary"
          aria-label="open pipeline list"
          onClick={handleTogglePipelineDrawer}
          size="small"
        >
          <ListIcon />
        </Fab>

        {/* Current Pipeline Display */}
        <CurrentPipelineDisplay />
        <AgentsArray agents={agents} />
      </Stack>

      {/* Pipeline List Drawer */}
      <PipelineList
        open={isPipelineDrawerOpen}
        onClose={handleClosePipelineDrawer}
      />

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
