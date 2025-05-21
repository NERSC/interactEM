import { AGENTS_BUCKET } from "../../constants/nats"
import { type AgentVal, AgentValSchema } from "../../types/agent"
import { useBucketWatch } from "./useBucketWatch"

export const useAgents = () => {
  const { items: agents, error } = useBucketWatch<AgentVal>({
    bucketName: AGENTS_BUCKET,
    schema: AgentValSchema,
  })

  return { agents, error }
}
