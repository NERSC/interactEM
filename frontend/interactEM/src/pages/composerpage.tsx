import ListIcon from "@mui/icons-material/List"
import { Fab } from "@mui/material"
import { useState } from "react"
import AgentsArray from "../components/agentsarray"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { PipelineList } from "../components/pipelinelist"
import { useAgents } from "../hooks/useAgents"
import useOperators from "../hooks/useOperators"
import type { PipelineJSON } from "../pipeline"
import { usePipelineStore } from "../stores"

export default function ComposerPage() {
  const { operators } = useOperators()
  const { agents } = useAgents()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [selectedPipelineData, setSelectedPipelineData] =
    useState<PipelineJSON | null>(null)
  const currentPipelineId = usePipelineStore((state) => state.currentPipelineId)

  const handleToggleDrawer = () => {
    setIsDrawerOpen(!isDrawerOpen)
  }

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false)
  }

  const handlePipelineSelect = (pipelineData: PipelineJSON | null) => {
    console.log("Loading pipeline data:", pipelineData)
    setSelectedPipelineData(pipelineData)
  }

  return (
    <div className="composer-page">
      {/* Drawer Button */}
      <Fab
        color="primary"
        aria-label="open pipeline list"
        onClick={handleToggleDrawer}
        // TODO: remove manual spacing...
        sx={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
        }}
      >
        <ListIcon />
      </Fab>

      {/* Pipeline List Drawer */}
      <PipelineList
        open={isDrawerOpen}
        onClose={handleCloseDrawer}
        onPipelineSelect={handlePipelineSelect}
      />

      {/* Main Flow Area */}
      <div className="composer-flow">
        <ComposerPipelineFlow
          key={currentPipelineId ?? "empty"}
          pipelineId={currentPipelineId}
          pipelineData={selectedPipelineData}
        />
        {/* TODO: remove manual spacing... */}
        <div className="composer-agents-overlay" style={{ top: "80px" }}>
          {" "}
          <AgentsArray agents={agents} />
        </div>
      </div>

      {/* Operator Menu */}
      <div className="composer-operators">
        <OperatorMenu operators={operators ?? []} />
      </div>
    </div>
  )
}
