import {
  type InfiniteData,
  type QueryFunctionContext,
  useInfiniteQuery,
} from "@tanstack/react-query"
import type { AxiosError } from "axios"
import type {
  PipelinePublic,
  PipelineRevisionPublic,
  PipelinesListPipelineRevisionsError,
  PipelinesPublic,
  PipelinesReadPipelinesError,
} from "../../client"
import {
  pipelinesListPipelineRevisions,
  pipelinesListPipelineRevisionsQueryKey,
  pipelinesReadPipelines,
  pipelinesReadPipelinesQueryKey,
  zPipelinePublic,
  zPipelinesPublic,
} from "../../client"
import { zPipelineRevisionPublic } from "../../client/generated/zod.gen"

const DEFAULT_LIMIT = 20

type PipelinesQueryKey = ReturnType<typeof pipelinesReadPipelinesQueryKey>
type RevisionsQueryKey = ReturnType<
  typeof pipelinesListPipelineRevisionsQueryKey
>

// TODO: Use hey-api generation for this. We may need to change endpoint names
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
      query: { offset: 0, limit: DEFAULT_LIMIT },
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

export const useInfinitePipelineRevisions = (pipelineId: string | null) => {
  const queryFn = async ({
    pageParam = 0,
    queryKey,
    signal,
  }: QueryFunctionContext<RevisionsQueryKey, number>): Promise<
    PipelineRevisionPublic[]
  > => {
    const options = queryKey[0]
    if (!options) {
      throw new Error("Query key options are missing.")
    }
    if (!options.path?.id) {
      throw new Error("pipelineId is required but missing in queryKey options.")
    }

    const specificOptions = {
      path: { id: options.path.id },
      query: { ...options.query, skip: pageParam, limit: DEFAULT_LIMIT },
      signal,
      throwOnError: true,
    }
    const result = await pipelinesListPipelineRevisions(specificOptions)

    if (!result || typeof result.data === "undefined") {
      throw new Error("API response did not contain revision data.")
    }
    return result.data
  }

  return useInfiniteQuery<
    PipelineRevisionPublic[],
    AxiosError<PipelinesListPipelineRevisionsError>,
    InfiniteData<PipelineRevisionPublic[], number>,
    RevisionsQueryKey,
    number
  >({
    queryKey: pipelinesListPipelineRevisionsQueryKey({
      path: { id: pipelineId ?? "no-pipeline" },
      query: { offset: 0, limit: DEFAULT_LIMIT },
    }),
    queryFn: queryFn,
    initialPageParam: 0,
    enabled: !!pipelineId,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      const currentCount = lastPage.length
      if (currentCount < DEFAULT_LIMIT) {
        return undefined
      }
      return lastPageParam + currentCount
    },
    select: (data) => {
      const validatedPages = data.pages.map((page) => {
        return page.filter((revision) => {
          const parsedRevision = zPipelineRevisionPublic.safeParse(revision)
          if (!parsedRevision.success) {
            console.warn(
              "Invalid pipeline revision data received:",
              parsedRevision.error,
              revision,
            )
            return false
          }
          return true
        })
      })
      return {
        pages: validatedPages,
        pageParams: data.pageParams,
      }
    },
  })
}
