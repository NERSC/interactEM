import {
  type InfiniteData,
  type QueryFunctionContext,
  useInfiniteQuery,
} from "@tanstack/react-query"
import type { AxiosError } from "axios"
// Import the actual SDK functions
import {
  pipelinesListPipelineRevisions,
  pipelinesReadPipelines,
} from "../client"
import { zPipelinePublic, zPipelineRevision, zPipelinesPublic } from "../client"
import {
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesReadPipelinesQueryKey,
} from "../client/generated/@tanstack/react-query.gen"
import type {
  PipelinePublic,
  PipelineRevision,
  PipelinesListPipelineRevisionsError,
  PipelinesPublic,
  PipelinesReadPipelinesError,
} from "../client/generated/types.gen"

const DEFAULT_LIMIT = 20

type PipelinesQueryKey = ReturnType<typeof pipelinesReadPipelinesQueryKey>
type RevisionsQueryKey = ReturnType<
  typeof pipelinesListPipelineRevisionsQueryKey
>

export const useInfinitePipelines = () => {
  const queryFn = async ({
    pageParam = 0,
    queryKey,
    signal,
  }: QueryFunctionContext<
    PipelinesQueryKey,
    number
  >): Promise<PipelinesPublic> => {
    const options = queryKey[0]
    if (!options) {
      throw new Error("Query key options are missing.")
    }

    // Call the original queryFn, overriding skip with pageParam
    const specificOptions = {
      ...options,
      query: { ...options.query, skip: pageParam, limit: DEFAULT_LIMIT },
      signal,
      throwOnError: true,
    }

    const result = await pipelinesReadPipelines(specificOptions)

    if (!result || typeof result.data === "undefined") {
      throw new Error("API response did not contain data.")
    }
    return result.data
  }

  return useInfiniteQuery<
    PipelinesPublic,
    AxiosError<PipelinesReadPipelinesError>,
    InfiniteData<PipelinesPublic, number>,
    PipelinesQueryKey,
    number
  >({
    queryKey: pipelinesReadPipelinesQueryKey({
      query: { skip: 0, limit: DEFAULT_LIMIT },
    }),
    queryFn: queryFn,
    initialPageParam: 0,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      const currentCount = lastPage.data.length
      if (currentCount < DEFAULT_LIMIT) {
        return undefined
      }
      return lastPageParam + currentCount
    },
    select: (data) => {
      // Validate and structure data for infinite query
      const validatedPages = data.pages.map((page) => {
        const parsedPage = zPipelinesPublic.safeParse(page)
        if (parsedPage.success) {
          const validatedPipelines = parsedPage.data.data.filter((pipeline) => {
            const parsedPipeline = zPipelinePublic.safeParse(pipeline)
            if (!parsedPipeline.success) {
              console.warn(
                "Invalid pipeline data received:",
                parsedPipeline.error,
                pipeline,
              )
              return false
            }
            return true
          })
          return { ...parsedPage.data, data: validatedPipelines }
        }
        console.warn("Invalid pipelines page data received:", parsedPage.error)
        return { data: [] as PipelinePublic[], count: 0 }
      })
      return {
        pages: validatedPages,
        pageParams: data.pageParams,
      }
    },
  })
}
