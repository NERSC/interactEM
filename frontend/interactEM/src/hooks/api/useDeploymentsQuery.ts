import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import type { PipelineDeploymentState } from "../../client"
import {
  deploymentsListPipelineDeploymentsInfiniteOptions,
  deploymentsReadPipelineDeploymentOptions,
} from "../../client/generated/@tanstack/react-query.gen"

const DEFAULT_LIMIT = 20
export const ACTIVE_DEPLOYMENT_STATES: PipelineDeploymentState[] = [
  "pending",
  "running",
  "assigned_agents",
]
export const RUNNING_STATE: PipelineDeploymentState = "running"

export const useInfiniteDeployments = (options?: {
  states?: PipelineDeploymentState[]
  pipelineId?: string | null
  enabled?: boolean
}) => {
  const { pipelineId, states, enabled = true } = options || {}

  const allDeploymentsQuery = useInfiniteQuery({
    ...deploymentsListPipelineDeploymentsInfiniteOptions({
      query: {
        limit: DEFAULT_LIMIT,
        ...(states && { states }),
        ...(pipelineId && { pipeline_id: pipelineId }),
      },
    }),
    initialPageParam: 0,
    enabled,
    refetchInterval: 5000,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      if (!lastPage || !lastPage.data) {
        return undefined
      }
      const currentCount = lastPage.data.length
      if (currentCount < DEFAULT_LIMIT) {
        return undefined
      }
      return (lastPageParam as number) + currentCount
    },
  })

  return allDeploymentsQuery
}

export const useInfinitePipelineDeployments = (
  pipelineId: string | null,
  states?: PipelineDeploymentState[],
  enabled = true,
) => {
  return useInfiniteDeployments({
    pipelineId,
    ...(states && { states }),
    enabled,
  })
}

// New hook specifically for active deployments
export const useInfiniteActiveDeployments = (enabled = true) => {
  return useInfiniteDeployments({
    states: ACTIVE_DEPLOYMENT_STATES,
    enabled,
  })
}

export const useDeployment = (deploymentId?: string | null) => {
  return useQuery({
    ...deploymentsReadPipelineDeploymentOptions({
      path: { id: deploymentId as string },
    }),
    enabled: !!deploymentId,
    refetchInterval: 5000,
  })
}
