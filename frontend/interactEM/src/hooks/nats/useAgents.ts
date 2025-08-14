import { useMemo } from "react"
import { useAgentStatusContext } from "../../contexts/nats/agentstatus"

export const useAgent = (id: string) => {
  const { agents, agentsLoading, agentsError } = useAgentStatusContext()

  const agent = useMemo(
    () => (id ? agents.find((a) => a.uri.id === id) || null : null),
    [agents, id],
  )

  return {
    agent,
    isLoading: agentsLoading,
    error: agentsError,
  }
}

export const useAllAgents = () => {
  const { agents, agentsLoading, agentsError } = useAgentStatusContext()

  return {
    agents,
    isLoading: agentsLoading,
    error: agentsError,
  }
}
