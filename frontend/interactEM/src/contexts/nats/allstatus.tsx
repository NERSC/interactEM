import type { ReactNode } from "react"
import { AgentStatusProvider } from "./agentstatus"
import { OperatorStatusProvider } from "./operatorstatus"

export const StatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  return (
    <OperatorStatusProvider>
      <AgentStatusProvider>{children}</AgentStatusProvider>
    </OperatorStatusProvider>
  )
}
