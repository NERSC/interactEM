import { useEffect, useState } from "react"
import { z } from "zod"
import { OPERATORS_BUCKET } from "../constants/nats"
import { useBucket } from "./useBucket"
import { useRunningPipelines } from "./useRunningPipelines"

// Schema for operator status validation
const OperatorStatusEnum = z.enum(["initializing", "running", "shutting_down"])
export type OperatorStatus = z.infer<typeof OperatorStatusEnum>

const OperatorValSchema = z.object({
  id: z.string().uuid(),
  status: OperatorStatusEnum,
  pipeline_id: z.string().uuid().nullable(),
})

type OperatorVal = z.infer<typeof OperatorValSchema>

export const useOperatorStatus = (operatorID: string) => {
  const [status, setStatus] = useState<OperatorStatus | null>(null)
  const [pipelineId, setPipelineId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const bucket = useBucket(OPERATORS_BUCKET)
  const { pipelines } = useRunningPipelines()

  // Check if the operator is part of a running pipeline
  const isActiveInRunningPipeline =
    pipelineId !== null &&
    pipelines.some((pipeline) => pipeline.id === pipelineId)

  // Get effective status - only return a status if the operator is part of a running pipeline
  const effectiveStatus = isActiveInRunningPipeline ? status : null

  useEffect(() => {
    if (!bucket) return

    const abortController = new AbortController()
    const signal = abortController.signal

    // Initial fetch of the operator status
    ;(async () => {
      try {
        const entry = await bucket.get(operatorID)
        if (entry?.value && !signal.aborted) {
          try {
            // Check if there's valid data before parsing
            if (entry.value.byteLength === 0) {
              console.warn(`Empty entry value for operator ${operatorID}`)
              setStatus(null)
              setPipelineId(null)
            } else {
              // Try to read the value as a string first to check validity
              const valueStr = new TextDecoder().decode(entry.value)
              if (!valueStr || valueStr.trim() === "") {
                console.warn(`Empty or invalid JSON for operator ${operatorID}`)
                setStatus(null)
                setPipelineId(null)
              } else {
                // Only attempt to parse if we have a non-empty string
                const data = JSON.parse(valueStr) as OperatorVal
                const parsedData = OperatorValSchema.safeParse(data)
                if (parsedData.success) {
                  setStatus(parsedData.data.status)
                  setPipelineId(parsedData.data.pipeline_id)
                } else {
                  console.warn(
                    `Invalid operator status data for ${operatorID}:`,
                    parsedData.error,
                  )
                  setStatus(null)
                  setPipelineId(null)
                }
              }
            }
          } catch (error) {
            console.error(
              `Error parsing operator status for ${operatorID}:`,
              error,
            )
            setStatus(null)
            setPipelineId(null)
          }
        } else {
          setStatus(null)
          setPipelineId(null)
        }
        if (!signal.aborted) {
          setIsLoading(false)
        }
      } catch (error) {
        if (!signal.aborted) {
          console.error(
            `Error fetching operator status for ${operatorID}:`,
            error,
          )
          setStatus(null)
          setPipelineId(null)
          setIsLoading(false)
        }
      }
    })()

    // Watch for changes to the operator's status
    ;(async () => {
      try {
        const watch = await bucket.watch({ key: operatorID })

        const processWatch = async () => {
          try {
            for await (const entry of watch) {
              // Exit if component unmounted
              if (signal.aborted) {
                watch.stop()
                return
              }

              // Handle deletion or purge - set to null (offline)
              if (entry.operation === "DEL" || entry.operation === "PURGE") {
                setStatus(null)
                setPipelineId(null)
                continue
              }

              // Skip if no value - set to null (offline)
              if (!entry.value) {
                setStatus(null)
                setPipelineId(null)
                continue
              }

              // Parse and validate the status update with improved error handling
              try {
                // Check if there's valid data before parsing
                if (entry.value.byteLength === 0) {
                  setStatus(null)
                  setPipelineId(null)
                  continue
                }

                // Try to read the value as a string first to check validity
                const valueStr = new TextDecoder().decode(entry.value)
                if (!valueStr || valueStr.trim() === "") {
                  setStatus(null)
                  setPipelineId(null)
                  continue
                }

                // Only attempt to parse if we have a non-empty string
                const data = JSON.parse(valueStr) as OperatorVal
                const parsedData = OperatorValSchema.safeParse(data)
                if (parsedData.success) {
                  setStatus(parsedData.data.status)
                  setPipelineId(parsedData.data.pipeline_id)
                } else {
                  setStatus(null)
                  setPipelineId(null)
                }
              } catch (error) {
                console.warn(
                  `Error parsing operator status update for ${operatorID}, setting to offline:`,
                  error,
                )
                setStatus(null)
                setPipelineId(null)
              }
            }
          } catch (watchErr) {
            if (!signal.aborted) {
              console.warn(
                `Watch error for operator ${operatorID}, setting to offline:`,
                watchErr,
              )
              setStatus(null)
              setPipelineId(null)
            }
          }
        }

        processWatch()
      } catch (watchSetupErr) {
        if (!signal.aborted) {
          console.warn(
            `Failed to watch operator ${operatorID}, setting to offline:`,
            watchSetupErr,
          )
          setStatus(null)
          setPipelineId(null)
        }
      }
    })()

    return () => {
      abortController.abort()
    }
  }, [bucket, operatorID])

  return { status: effectiveStatus, isLoading, pipelineId, rawStatus: status }
}
