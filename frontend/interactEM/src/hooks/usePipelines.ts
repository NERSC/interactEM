import { useEffect, useState } from "react"
import { z } from "zod"
import type {
  EdgeJSON,
  OperatorJSON,
  PipelineWithID,
  PortJSON,
} from "../pipeline"
import { useBucket } from "./useBucket"

const BackendPipelineJSONSchema = z.object({
  id: z.string(),
  operators: z.array(z.any()),
  ports: z.array(z.any()),
  edges: z.array(z.any()),
})

type BackendPipelineJSON = z.infer<typeof BackendPipelineJSONSchema>

export const usePipelines = () => {
  const [pipelines, setPipelines] = useState<PipelineWithID[]>([])
  const [error, setError] = useState<string | null>(null)
  const bucket = useBucket("pipelines")

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
              try {
                const data = entry.json()
                const parsed = BackendPipelineJSONSchema.safeParse(data)
                if (parsed.success) {
                  const backend: BackendPipelineJSON = parsed.data
                  return [
                    ...filtered,
                    {
                      id: key,
                      data: {
                        operators: backend.operators as OperatorJSON[],
                        ports: backend.ports as PortJSON[],
                        edges: backend.edges as EdgeJSON[],
                      },
                    },
                  ]
                }
                console.warn("Invalid pipeline data for key", key, parsed.error)
                return filtered
              } catch (e) {
                console.warn("Invalid pipeline data for key", key, e)
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
