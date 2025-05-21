import { z } from "zod"
import { PIPELINES_BUCKET } from "../../constants/nats"
import { useBucketWatch } from "./useBucketWatch"

const PipelineRunSchema = z.object({
  id: z.string().uuid(),
  revision_id: z.number().int(),
})

export type PipelineRun = z.infer<typeof PipelineRunSchema>

export const useRunningPipelines = () => {
  const { items: pipelines, error } = useBucketWatch<PipelineRun>({
    bucketName: PIPELINES_BUCKET,
    schema: PipelineRunSchema,
  })

  return { pipelines, error }
}
