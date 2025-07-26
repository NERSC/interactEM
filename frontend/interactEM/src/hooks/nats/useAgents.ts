import { AGENTS_BUCKET } from "../../constants/nats"
import { AgentValSchema } from "../../types/agent"
import type { AgentVal } from "../../types/gen"
import { useBucketWatch } from "./useBucketWatch"

export const useAgents = () => {
  const { items: agents, error } = useBucketWatch<AgentVal>({
    bucketName: AGENTS_BUCKET,
    schema: AgentValSchema,
  })

  return { agents, error }
}
