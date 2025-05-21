import { PIPELINES_BUCKET } from "../../constants/nats"
import { type PipelineRun, PipelineRunSchema } from "../../types/pipeline"
import { useBucketWatch } from "./useBucketWatch"

export const useRunningPipelines = () => {
  const { items: pipelines, error } = useBucketWatch<PipelineRun>({
    bucketName: PIPELINES_BUCKET,
    schema: PipelineRunSchema,
  })

  return { pipelines, error }
}
