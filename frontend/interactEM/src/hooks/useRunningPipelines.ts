import { useEffect, useState } from "react"
import { z } from "zod"
import { PIPELINES_BUCKET } from "../constants/nats"
import { useBucket } from "./useBucket"

const PipelineRunVal = z.object({
  id: z.string().uuid(),
  revision_id: z.number().int(),
})

type PipelineRunVal = z.infer<typeof PipelineRunVal>

export const useRunningPipelines = () => {
  const [pipelines, setPipelines] = useState<PipelineRunVal[]>([])
  const [error, setError] = useState<string | null>(null)
  const bucket = useBucket(PIPELINES_BUCKET)

  useEffect(() => {
    if (!bucket) return

    const abortController = new AbortController()
    const signal = abortController.signal
    ;(async () => {
      try {
        const watch = await bucket.watch()
        const processWatch = async () => {
          for await (const entry of watch) {
            if (signal.aborted) {
              watch.stop()
              return
            }
            const key = entry.key
            setPipelines((prev) => {
              const filtered = prev.filter((p) => p.id !== key)
              if (entry.operation === "DEL" || entry.operation === "PURGE") {
                return filtered
              }
              if (!entry.value) {
                console.warn(`No value for key ${key}, skipping`)
                return filtered
              }
              try {
                const event = entry.json<PipelineRunVal>()
                const event_parsed = PipelineRunVal.safeParse(event)
                if (event_parsed.success) {
                  // Check if the pipeline with the same ID and data already exists
                  const existing = prev.find(
                    (p) =>
                      p.id === event_parsed.data.id &&
                      p.revision_id === event_parsed.data.revision_id,
                  )
                  if (existing) {
                    // No change, return previous array (no new object)
                    return prev
                  }
                  return [...filtered, event_parsed.data]
                }
                console.warn(
                  "Invalid pipeline data for key",
                  key,
                  event_parsed.error,
                )
                return filtered
              } catch (e) {
                console.warn("Error processing pipeline data for key", key, e)
                return filtered
              }
            })
          }
        }
        processWatch()
      } catch (err) {
        if (!signal.aborted) setError("Failed to watch pipelines")
      }
    })()

    return () => abortController.abort()
  }, [bucket])

  return { pipelines, error }
}
