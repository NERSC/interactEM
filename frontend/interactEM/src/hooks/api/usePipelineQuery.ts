import { useQuery } from "@tanstack/react-query"
import { pipelinesReadPipelineOptions } from "../../client/generated/@tanstack/react-query.gen"

export const usePipeline = (pipelineId: string) => {
  return useQuery({
    ...pipelinesReadPipelineOptions({
      path: { id: pipelineId },
    }),
  })
}

export const usePipelineName = (pipelineId: string) => {
  const { data: pipeline, isFetching } = usePipeline(pipelineId)

  if (isFetching) {
    return "Loading..."
  }

  // Return first 8 of uuid if no name available
  if (!pipeline || !pipeline.name) {
    return `${pipelineId.substring(0, 8)}`
  }

  return pipeline.name
}
