import { useInfiniteQuery } from "@tanstack/react-query"
import {
  pipelinesListPipelineRevisionsInfiniteOptions,
  pipelinesReadPipelinesInfiniteOptions,
} from "../../client/generated/@tanstack/react-query.gen"

const DEFAULT_LIMIT = 20

export const useInfinitePipelines = () => {
  const allPipelinesQuery = useInfiniteQuery({
    ...pipelinesReadPipelinesInfiniteOptions({
      query: {
        limit: DEFAULT_LIMIT,
      },
    }),
    initialPageParam: 0,
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

  return allPipelinesQuery
}

export const useInfinitePipelineRevisions = (pipelineId: string | null) => {
  const allRevisionsQuery = useInfiniteQuery({
    ...pipelinesListPipelineRevisionsInfiniteOptions({
      path: { id: pipelineId ?? "no-pipeline" },
      query: {
        limit: DEFAULT_LIMIT,
      },
    }),
    initialPageParam: 0,
    enabled: !!pipelineId,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      if (!lastPage || !Array.isArray(lastPage)) {
        return undefined
      }
      const currentCount = lastPage.length
      if (currentCount < DEFAULT_LIMIT) {
        return undefined
      }
      return (lastPageParam as number) + currentCount
    },
  })

  return allRevisionsQuery
}
