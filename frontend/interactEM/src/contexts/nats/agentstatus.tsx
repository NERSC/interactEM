import { type ReactNode, createContext, useContext, useMemo } from "react"
import { AGENTS, BUCKET_STATUS } from "../../constants/nats"
import { useBucketWatch } from "../../hooks/nats/useBucketWatch"
import { AgentValSchema } from "../../types/agent"
import type { AgentVal } from "../../types/gen"

interface AgentStatusContextType {
  agents: AgentVal[]
  agentsLoading: boolean
  agentsError: string | null
}

const AgentStatusContext = createContext<AgentStatusContextType>({
  agents: [],
  agentsLoading: true,
  agentsError: null,
})

export const AgentStatusProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const {
    items: agents,
    isLoading: agentsLoading,
    error: agentsError,
  } = useBucketWatch<AgentVal>({
    bucketName: BUCKET_STATUS,
    schema: AgentValSchema,
    keyFilter: `${AGENTS}.>`,
    stripPrefix: AGENTS,
  })

  const contextValue = useMemo(
    () => ({ agents, agentsLoading, agentsError }),
    [agents, agentsLoading, agentsError],
  )

  return (
    <AgentStatusContext.Provider value={contextValue}>
      {children}
    </AgentStatusContext.Provider>
  )
}

export const useAgentStatusContext = () => useContext(AgentStatusContext)
