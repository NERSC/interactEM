import { BUCKET_STATUS, PIPELINES } from "../../constants/nats"
import type { PipelineRunVal } from "../../types/gen"
import { PipelineRunValSchema } from "../../types/pipeline"
import { useBucketWatch } from "./useBucketWatch"

export const useRunningPipelines = () => {
  const { items: pipelines, error } = useBucketWatch<PipelineRunVal>({
    bucketName: BUCKET_STATUS,
    schema: PipelineRunValSchema,
    keyFilter: `${PIPELINES}.>`,
  })

  return { pipelines, error }
}
