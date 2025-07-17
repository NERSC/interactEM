import { AGENTS, BUCKET_STATUS } from "../../constants/nats"
import { AgentValSchema } from "../../types/agent"
import type { AgentVal } from "../../types/gen"
import { useBucketWatch } from "./useBucketWatch"

export const useAgents = () => {
  const { items: agents, error } = useBucketWatch<AgentVal>({
    bucketName: BUCKET_STATUS,
    schema: AgentValSchema,
    keyFilter: `${AGENTS}.>`,
    stripPrefix: AGENTS,
  })

  return { agents, error }
}
