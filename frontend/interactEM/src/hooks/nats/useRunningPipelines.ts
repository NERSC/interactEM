import { PIPELINES_BUCKET } from "../../constants/nats"
import type { PipelineRunVal } from "../../types/gen"
import { PipelineRunValSchema } from "../../types/pipeline"
import { useBucketWatch } from "./useBucketWatch"

export const useRunningPipelines = () => {
  const { items: pipelines, error } = useBucketWatch<PipelineRunVal>({
    bucketName: PIPELINES_BUCKET,
    schema: PipelineRunValSchema,
  })

  return { pipelines, error }
}
