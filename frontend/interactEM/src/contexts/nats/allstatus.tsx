import type { ReactNode } from "react"
import { AgentStatusProvider } from "./agentstatus"
import { OperatorStatusProvider } from "./operatorstatus"
import { PipelineStatusProvider } from "./pipelinestatus"

export const StatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  return (
    <PipelineStatusProvider>
      <OperatorStatusProvider>
        <AgentStatusProvider>{children}</AgentStatusProvider>
      </OperatorStatusProvider>
    </PipelineStatusProvider>
  )
}
