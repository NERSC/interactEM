import AgentsArray from "../components/agentsarray"
import ComposerPipelineFlow from "../components/composerpipelineflow"
import { OperatorMenu } from "../components/operatormenu"
import { useAgents } from "../hooks/useAgents"
import useOperators from "../hooks/useOperators"

export default function ComposerPage() {
  const { operators } = useOperators()
  const { agents } = useAgents()

  return (
    <div className="composer-page">
      <div className="composer-flow">
        <ComposerPipelineFlow />
        <div className="composer-agents-overlay">
          <AgentsArray agents={agents} />
        </div>
      </div>
      <div className="composer-operators">
        <OperatorMenu operators={operators ?? []} />
      </div>
    </div>
  )
}
